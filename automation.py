"""Conservative Lever hosted-form adapter. Other ATSs are explicit handoffs."""
from pathlib import Path
import re
from urllib.parse import urlparse

SUPPORTED_HOST = 'jobs.lever.co'
FIELD_MAP = {'name': 'name', 'email': 'email', 'phone': 'phone', 'org': 'company',
             'urls[LinkedIn]': 'linkedin', 'urls[GitHub]': 'github', 'urls[Portfolio]': 'website'}

class NeedsAttention(Exception):
    pass

def supported_url(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and parsed.hostname == SUPPORTED_HOST and
            not parsed.username and not parsed.password and parsed.port in (None, 443) and
            bool(re.fullmatch(r'/[A-Za-z0-9_-]+/[a-f0-9-]{36}/apply/?', parsed.path)))

def preflight(fields, profile, page_text, has_captcha=False):
    if has_captcha or re.search(r'\b(sign in to apply|log in to apply|verify you are human)\b', page_text, re.I):
        raise NeedsAttention('This form requires CAPTCHA, verification, or login. Open it to finish manually.')
    if re.search(r'by (?:submitting|clicking|applying).{0,180}(?:agree|consent|certify|terms)', page_text, re.I | re.S):
        raise NeedsAttention('The form includes an agreement or certification that needs your review.')
    names = [f['name'] for f in fields]
    if names.count('name') != 1 or names.count('email') != 1 or names.count('resume') != 1:
        raise NeedsAttention('This is not a supported standard Lever form. Open the original application.')
    for f in fields:
        if f['type'] in {'checkbox', 'radio'}:
            raise NeedsAttention('This form contains choices or consent questions. Complete those on the employer site.')
        if f['type'] not in {'submit', 'button', 'hidden'} and f['name'] not in {*FIELD_MAP, 'resume', 'comments'}:
            raise NeedsAttention('The form has a custom question. Complete it on the employer site.')
        if f['required'] and f['type'] not in {'submit', 'button', 'hidden'}:
            if f['name'] == 'resume' and f['type'] == 'file':
                continue
            key = FIELD_MAP.get(f['name'])
            if not key or not profile.get(key, '').strip():
                raise NeedsAttention('A required application answer is missing. Open the employer form to complete it.')

def apply_lever(job, profile, resume_path, authorize, still_enabled):
    if not supported_url(job['apply_url']):
        raise NeedsAttention('Automatic submission currently supports standard Lever forms. Open this application to finish manually.')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
        except Exception as exc:
            raise NeedsAttention('Browser runtime missing. Run: python -m playwright install chromium') from exc
        try:
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.goto(job['apply_url'], wait_until='domcontentloaded', timeout=30000)
            if not supported_url(page.url):
                raise NeedsAttention('The application redirected to an unsupported destination.')
            forms = page.locator('form').filter(has=page.locator('input[name="email"]'))
            if forms.count() != 1:
                raise NeedsAttention('The employer form could not be identified reliably.')
            form = forms.first
            action = form.get_attribute('action') or ''
            if action.startswith(('http:', 'https:', '//')):
                raise NeedsAttention('The form submits to a separate destination. Complete it manually.')
            # DOM inspection is confined to the application form. Unknown required fields block submission.
            fields = form.locator('input, textarea, select').evaluate_all('''els => els.map(e => ({
                name:e.name, type:e.type || e.tagName.toLowerCase(),
                required:e.required || e.getAttribute('aria-required') === 'true' ||
                !!e.closest('.required') || !!e.closest('[data-required="true"]')
            }))''')
            has_captcha = page.locator('iframe[src*="captcha"], .g-recaptcha, .h-captcha, [data-sitekey], input[name*="captcha"]').count() > 0
            preflight(fields, profile, page.locator('body').inner_text(), has_captcha)
            buttons = form.get_by_role('button', name=re.compile(r'^(Submit application|Submit your application|Apply)$', re.I))
            if buttons.count() != 1:
                raise NeedsAttention('The submission button could not be identified reliably.')
            # Persist a non-retryable attempt BEFORE upload or filling (some forms autosave).
            if not authorize():
                raise NeedsAttention('Auto-apply stopped, daily limit reached, or settings changed.')
            for field in fields:
                name = field['name']
                if name in FIELD_MAP and profile.get(FIELD_MAP[name]):
                    form.locator(f'[name="{name}"]').fill(profile[FIELD_MAP[name]])
            form.locator('input[name="resume"]').set_input_files(str(Path(resume_path).resolve()))
            if not still_enabled():
                raise NeedsAttention('Auto-apply was stopped. This application was not submitted by the runner.')
            if not form.evaluate('(f) => f.checkValidity()'):
                raise NeedsAttention('The application form has unanswered or invalid fields.')
            buttons.click()
            # A click or HTTP 200 is never counted as a successful application.
            try:
                form.wait_for(state='hidden', timeout=15000)
                page.get_by_text(re.compile(r'(application (?:has been |was )?(?:successfully )?(?:submitted|received)|thank you for applying)', re.I)).first.wait_for(timeout=15000)
            except Exception as exc:
                raise NeedsAttention('Submission outcome is uncertain. Check the employer before submitting again.') from exc
            return 'Employer displayed an application-received confirmation.'
        finally:
            browser.close()
