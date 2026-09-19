"""Public job feeds. No login, scraping, or employer credentials required."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from html import unescape
import re
from urllib.parse import urlparse
import requests

DEFAULT_BOARDS = 'ashby:linear\nashby:notion\nlever:sep\ngreenhouse:figma\ngreenhouse:stripe'

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def plain(value):
    parser = PlainText(); parser.feed(unescape(value or ''))
    return ' '.join(' '.join(parser.parts).split())

def stamp(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 10**11 else value, timezone.utc).isoformat()
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None

def safe_url(value):
    p = urlparse(value or '')
    return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password and p.port in (None, 443)

def board_specs(text):
    specs = []
    for line in text.splitlines():
        line = line.strip().lower()
        if not line:
            continue
        if not re.fullmatch(r'(ashby|lever|greenhouse):[a-z0-9_-]{1,80}', line):
            raise ValueError('Use one board per line: ashby:company, lever:company, or greenhouse:company.')
        if line not in specs:
            specs.append(line)
    if len(specs) > 20:
        raise ValueError('Use at most 20 company boards per search.')
    return specs

def get_json(url):
    response = requests.get(url, timeout=(5, 20), headers={'User-Agent': 'ApplyLens/0.2'}, allow_redirects=False)
    response.raise_for_status()
    if response.is_redirect:
        raise ValueError('The feed redirected; check its board identifier.')
    return response.json()

def fetch_board(spec):
    provider, board = spec.split(':')
    jobs = []
    if provider == 'ashby':
        data = get_json(f'https://api.ashbyhq.com/posting-api/job-board/{board}').get('jobs', [])
        for j in data:
            if j.get('isListed', True):
                jobs.append(dict(id=f'ashby:{board}:{j["id"]}', title=j['title'], company=board,
                    location=j.get('location', ''), remote=bool(j.get('isRemote')), employment=j.get('employmentType', ''),
                    posted=stamp(j.get('publishedAt')), description=j.get('descriptionPlain') or plain(j.get('descriptionHtml')),
                    url=j.get('jobUrl', ''), apply_url=j.get('applyUrl', '')))
    elif provider == 'lever':
        data = get_json(f'https://api.lever.co/v0/postings/{board}?mode=json')
        for j in data:
            cat = j.get('categories', {})
            desc = j.get('descriptionPlain') or plain(j.get('description'))
            desc += '\n' + '\n'.join(x.get('text', '') + '\n' + plain(x.get('content')) for x in j.get('lists', []))
            desc += '\n' + (j.get('additionalPlain') or plain(j.get('additional')))
            jobs.append(dict(id=f'lever:{board}:{j["id"]}', title=j['text'], company=board,
                location=cat.get('location', ''), remote=j.get('workplaceType') == 'remote', employment=cat.get('commitment', ''),
                posted=stamp(j.get('createdAt')), description=desc, url=j.get('hostedUrl', ''), apply_url=j.get('applyUrl', '')))
    else:
        data = get_json(f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true').get('jobs', [])
        for j in data:
            # updated_at is NOT a publication date. Keep unknown dates honest.
            location = (j.get('location') or {}).get('name', '')
            jobs.append(dict(id=f'greenhouse:{board}:{j["id"]}', title=j['title'], company=board,
                location=location, remote='remote' in location.lower(), employment='', posted=stamp(j.get('first_published')),
                description=plain(j.get('content')), url=j.get('absolute_url', ''), apply_url=j.get('absolute_url', '')))
    for job in jobs:
        job['source'] = spec
    return [j for j in jobs if safe_url(j['url']) and safe_url(j['apply_url'])]

def discover(boards):
    specs = board_specs(boards)
    jobs, errors = {}, []
    with ThreadPoolExecutor(max_workers=5) as pool:
        pending = {pool.submit(fetch_board, spec): spec for spec in specs}
        for future in as_completed(pending):
            try:
                for job in future.result():
                    jobs[job['id']] = job
            except (requests.RequestException, ValueError, KeyError, TypeError):
                errors.append(f'{pending[future]} could not be read. Check the board name or try again later.')
    return list(jobs.values()), errors

def title_matches(term, title):
    term = term.strip().lower()
    pattern = r'intern(?:ship)?s?' if term == 'intern' else re.escape(term)
    return bool(re.search(r'(?<!\w)' + pattern + r'(?!\w)', title.lower()))

def match(job, rules, now=None, resume=None):
    """Hard filters return reasons. Unknown data cannot pass an explicit hard filter."""
    now = now or datetime.now(timezone.utc)
    reasons = []
    title = job['title'].lower()
    if not any(title_matches(x, title) for x in rules['roles'].split(',') if x.strip()):
        reasons.append('Role title does not match')
    excluded = [x.strip().lower() for x in rules.get('excluded', '').split(',') if x.strip()]
    if any(x in job['company'].lower() for x in excluded):
        reasons.append('Excluded company')
    locations = [x.strip().lower() for x in rules.get('locations', '').split(',') if x.strip()]
    if locations and not any(x in job['location'].lower() for x in locations):
        reasons.append('Location does not match')
    if rules.get('remote_only') and not job['remote']:
        reasons.append('Not explicitly remote')
    if rules.get('employment') and re.sub(r'[^a-z]', '', rules['employment'].lower()) not in re.sub(r'[^a-z]', '', (job['employment'] + ' ' + title).lower()):
        reasons.append('Employment type not confirmed')
    if rules.get('max_days'):
        posted = stamp(job.get('posted'))
        if not posted:
            reasons.append('Publication date unavailable')
        else:
            age = (now - datetime.fromisoformat(posted)).total_seconds() / 86400
            if age < -1 or age > rules['max_days']:
                reasons.append('Outside posting-age limit')
    terms = [x.strip().lower() for x in rules.get('required_terms', '').split(',') if x.strip()]
    if any(x not in job['description'].lower() for x in terms):
        reasons.append('Required keyword missing')
    if any(title_matches(x, title) for x in rules.get('excluded_titles', '').split(',') if x.strip()):
        reasons.append('Excluded title keyword')
    if resume is not None and rules.get('min_overlap', 0):
        from resumes import tokens
        if len(tokens(resume) & tokens(job['description'])) < rules['min_overlap']:
            reasons.append('Too few shared resume keywords')
    return reasons
