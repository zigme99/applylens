"""ApplyLens — local job-search and application workspace."""
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import streamlit as st
import storage as store
from sources import DEFAULT_BOARDS, board_specs, discover, match
from resumes import extract, tailor, docx_bytes, tokens

st.set_page_config(page_title='ApplyLens · Your next move', page_icon='↗', layout='wide')
st.markdown('''<style>
.block-container{max-width:1240px;padding-top:2rem;padding-bottom:3rem}
h1{font-size:2.8rem!important;letter-spacing:-.055em;font-weight:750!important}
h2,h3{letter-spacing:-.025em} [data-testid="stSidebar"]{background:#102F2A}
[data-testid="stSidebar"] *{color:#EBF4F0} [data-testid="stSidebar"] .stCaption{color:#ADC9C0}
[data-testid="stMetric"]{background:white;border:1px solid #E2E8E5;border-radius:14px;padding:18px}
[data-testid="stMetricValue"]{font-size:2rem;color:#147D64}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px}
.stButton>button{border-radius:9px} .eyebrow{color:#147D64;letter-spacing:.14em;font-size:.75rem;font-weight:700}
</style>''', unsafe_allow_html=True)

DEFAULT_RULES = dict(roles='software engineer, data analyst, intern', locations='', remote_only=False,
                    employment='', excluded_titles='', min_overlap=2, max_days=7, required_terms='', excluded='', daily_limit=5, boards=DEFAULT_BOARDS)
profile = store.get('profile', {})
rules = store.get('rules', DEFAULT_RULES)
apps = store.rows()
enabled = store.get('enabled', False)

with st.sidebar:
    st.title('↗ ApplyLens')
    st.caption('YOUR NEXT MOVE, IN MOTION')
    st.divider()
    page = st.radio('Workspace', ['Overview', 'My resume', 'Job preferences', 'Discover jobs', 'Applications'], label_visibility='collapsed')
    st.divider()
    st.write('● Auto-apply enabled' if enabled else '○ Auto-apply paused')
    st.caption('Local workspace · Your data stays on this computer until an application is sent.')
    if enabled and st.button('Pause auto-apply', use_container_width=True):
        store.put('enabled', False); st.rerun()
    st.caption('Changing your resume or rules pauses automation.')

st.markdown('<div class="eyebrow">YOUR JOB SEARCH, WITH DIRECTION</div>', unsafe_allow_html=True)


def job_card(job, can_queue=True):
    with st.container(border=True):
        left, right = st.columns([4, 1])
        left.subheader(job['title'])
        left.caption(f"{job['company'].title()}  ·  {job['location'] or 'Location not supplied'}  ·  {job['source'].split(':')[0].title()}")
        right.markdown('**Remote**' if job['remote'] else '**See location**')
        right.caption('Published ' + job['posted'][:10] if job.get('posted') else 'Publication date unavailable')
        shared = sorted(tokens(profile.get('resume', '')) & tokens(job['description']))
        if shared:
            st.caption('Shared resume keywords: ' + ', '.join(shared[:12]))
        with st.expander('Job details & tailored resume'):
            st.text(job['description'][:25000])
            if profile.get('resume'):
                tailored, _ = tailor(profile['resume'], job['description'])
                st.caption('Tailoring reorders relevant bullets within their original sections. Every original line is preserved; no new qualifications are added.')
                st.download_button('Download tailored resume', docx_bytes(tailored), 'applylens-resume.docx', key='dl_' + job['id'])
        a, b = st.columns(2)
        a.link_button('View original listing ↗', job['url'], use_container_width=True)
        existing = next((x for x in apps if x['id'] == job['id'] and x['status'] != 'cancelled'), None)
        if b.button(existing['status'].replace('_', ' ').title() if existing else 'Add to application queue',
                    key='q_' + job['id'], disabled=bool(existing) or not can_queue or not profile.get('resume'), use_container_width=True):
            if not match(job, rules, resume=profile.get('resume')):
                store.enqueue(job, manual=True); st.rerun()

if page == 'Overview':
    st.title('Less searching. More possibilities.')
    st.write('Your resume, your rules, your next opportunity. Build your profile once and keep your applications moving.')
    st.write('')
    cols = st.columns(4)
    cols[0].metric('Matching jobs', sum(not match(j, rules, resume=profile.get('resume')) for j in store.get('jobs', [])))
    cols[1].metric('In your queue', sum(a['status'] in {'queued','preparing','submitting'} for a in apps))
    cols[2].metric('Submitted', sum(a['status'] == 'submitted' for a in apps))
    cols[3].metric('Needs your attention', sum(a['status'] == 'needs_attention' for a in apps))
    st.write('')
    left, right = st.columns([1.5, 1])
    with left, st.container(border=True):
        st.subheader('Make it your search')
        st.markdown(f"{'✓' if profile else '1.'} **Add your resume** — upload a PDF, DOCX, or text file.")
        st.markdown(f"{'✓' if store.get('rules') else '2.'} **Set your preferences** — roles, location, posting age, and exclusions.")
        st.markdown('3. **Find jobs & enable auto-apply** — the runner checks your rules before each attempt.')
        st.caption('Start with My resume in the sidebar. No API key needed for discovery or extractive resume tailoring.')
    with right, st.container(border=True):
        st.subheader('Built around your rules')
        st.write('Freshness filters · Company exclusions · Daily application limits · Duplicate prevention')
        st.caption('Live search covers your configured Ashby, Greenhouse, and Lever company boards. Automatic submission supports standard Lever forms; other forms open for manual completion.')
    st.subheader('Recent activity')
    if not apps:
        st.info('Your activity will appear here after you add jobs to your queue.')
    else:
        st.dataframe([{'Role': a['job']['title'], 'Company': a['job']['company'], 'Status': a['status'].replace('_',' ').title(), 'Updated': a['updated'][:16]} for a in apps[:8]], hide_index=True, use_container_width=True)

elif page == 'My resume':
    st.title('One profile. A stronger starting point.')
    st.write('Upload your resume, check the extracted text, and save the details applications should use.')
    uploaded = st.file_uploader('Resume', type=['pdf','docx','txt'])
    if uploaded is not None:
        import hashlib
        fingerprint = hashlib.sha256(uploaded.getvalue()).hexdigest()
        if st.session_state.get('uploaded_hash') != fingerprint:
            try:
                st.session_state['resume_text'] = extract(uploaded.name, uploaded.getvalue())
                st.session_state['uploaded_hash'] = fingerprint
            except ValueError as exc:
                st.error(str(exc))
    with st.form('profile_form'):
        c1, c2 = st.columns(2)
        name = c1.text_input('Full name', value=profile.get('name',''))
        email = c2.text_input('Email', value=profile.get('email',''))
        phone = c1.text_input('Phone (optional)', value=profile.get('phone',''))
        company = c2.text_input('Current company (optional)', value=profile.get('company',''))
        linkedin = c1.text_input('LinkedIn URL (optional)', value=profile.get('linkedin',''))
        github = c2.text_input('GitHub URL (optional)', value=profile.get('github',''))
        website = c1.text_input('Portfolio URL (optional)', value=profile.get('website',''))
        if 'resume_text' not in st.session_state:
            st.session_state['resume_text'] = profile.get('resume','')
        resume = st.text_area('Resume text — review and edit before saving', height=340, key='resume_text', max_chars=40000)
        st.caption('Saved locally in private_data. Original uploads are not retained. Extraction may lose layout; downloads use a clean document layout.')
        saved = st.form_submit_button('Save my profile', type='primary')
    if saved:
        if not name.strip() or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email.strip()) or len(resume.strip()) < 80:
            st.error('Enter your name, a valid email, and at least 80 characters of resume text.')
        else:
            store.save_configuration('profile', dict(name=name.strip(), email=email.strip(), phone=phone.strip(), company=company.strip(), linkedin=linkedin.strip(), github=github.strip(), website=website.strip(), resume=resume.strip()))
            st.success('Profile saved. Auto-apply is paused so you can review your rules.')

elif page == 'Job preferences':
    st.title('Good opportunities. On your terms.')
    st.write('These are hard filters. Jobs with missing information cannot pass a filter that requires it.')
    with st.form('rules_form'):
        c1, c2 = st.columns(2)
        roles = c1.text_input('Role titles — comma separated', value=rules['roles'])
        locations = c2.text_input('Locations — comma separated; blank means any', value=rules['locations'])
        remote = c1.checkbox('Remote only', value=rules['remote_only'])
        employment = c2.selectbox('Employment type', ['', 'Intern', 'FullTime', 'PartTime', 'Contract'], index=['', 'Intern', 'FullTime', 'PartTime', 'Contract'].index(rules['employment']), format_func=lambda x: x or 'Any')
        days = c1.selectbox('Posted within', [1,3,7,14,30,0], index=[1,3,7,14,30,0].index(rules['max_days']), format_func=lambda x: f'{x} days' if x else 'Any time (includes unknown dates)')
        limit = c2.number_input('Maximum application attempts per day (UTC)', 1, 50, rules['daily_limit'])
        excluded_titles = c1.text_input('Exclude title keywords — e.g. senior, staff, director', value=rules.get('excluded_titles',''))
        min_overlap = c2.number_input('Minimum shared resume keywords', 0, 20, rules.get('min_overlap',2), help='A transparent keyword filter, not a qualification or eligibility score.')
        required = c1.text_input('All of these keywords must appear in the posting', value=rules['required_terms'])
        excluded = c2.text_input('Exclude companies — comma separated', value=rules['excluded'])
        st.caption('Remote roles can still have country restrictions. Set a location filter when needed. Salary and sponsorship are not inferred or used as automatic filters in this version.')
        boards = st.text_area('Company job boards to search', value=rules['boards'], height=160,
            help='One per line: ashby:company, lever:company, or greenhouse:company. Use the company identifier from its hosted careers URL.')
        st.caption('Search uses public company feeds, not all jobs on the internet. Boards are configurable; missing publication dates are excluded when an age limit is selected.')
        saved = st.form_submit_button('Save my rules', type='primary')
    if saved:
        try:
            if not any(x.strip() for x in roles.split(',')) or not board_specs(boards):
                raise ValueError('Add at least one role and one company board.')
            store.save_configuration('rules', dict(roles=roles, locations=locations, remote_only=remote, employment=employment,
                max_days=days, excluded_titles=excluded_titles, min_overlap=int(min_overlap), daily_limit=int(limit), required_terms=required, excluded=excluded, boards=boards))
            st.success('Rules saved. Review the matching jobs, then enable auto-apply in Applications.')
        except ValueError as exc:
            st.error(str(exc))

elif page == 'Discover jobs':
    st.title('Find your next move.')
    st.write('Search live company boards. Your saved rules filter the results before anything enters the queue.')
    if st.button('Search live jobs', type='primary'):
        with st.spinner('Checking company job boards…'):
            jobs, errors = discover(rules['boards'])
            store.put('jobs', jobs); store.put('search_errors', errors); store.put('last_search', store.now())
    for error in store.get('search_errors', []):
        st.warning(error)
    jobs = store.get('jobs', [])
    matches = [j for j in jobs if not match(j, rules, resume=profile.get('resume'))]
    matches.sort(key=lambda j: j.get('posted') or '', reverse=True)
    st.caption(f"{len(matches)} matching · {len(jobs)} live listings checked · Last search: {store.get('last_search', 'not run')[:19]}")
    if not profile:
        st.info('You can explore jobs now. Save your resume to create tailored documents and queue applications.')
    if jobs and not matches:
        st.info('No jobs meet every rule. Try broader role titles, different company boards, or a longer posting-age window.')
    if jobs:
        with st.expander('Why other jobs were filtered out'):
            st.dataframe([{'Role': j['title'], 'Company': j['company'], 'Reasons': '; '.join(match(j, rules, resume=profile.get('resume')))} for j in jobs if match(j, rules, resume=profile.get('resume'))], hide_index=True)
    page_number = st.number_input('Results page', 1, max(1, (len(matches)+9)//10), 1)
    for job in matches[(page_number-1)*10:page_number*10]:
        job_card(job)
    if not jobs:
        st.info('Click Search live jobs to fetch listings. No sample listings or fabricated application counts are shown.')

elif page == 'Applications':
    st.title('Your applications, moving forward.')
    st.write('Enable the local runner to find matching jobs every 30 minutes and process your application queue.')
    with st.container(border=True):
        st.subheader('Auto-apply controls')
        st.write(f"Daily limit: **{rules['daily_limit']} attempts** · Current state: **{'Enabled' if enabled else 'Paused'}**")
        heartbeat = store.get('heartbeat')
        alive = bool(heartbeat and (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat)).total_seconds() < 60)
        st.caption('Runner connected' if alive else 'Runner is not connected. Enabling auto-apply starts it on this computer.')
        if store.get('runner_error'):
            st.warning(store.get('runner_error'))
        consent = st.checkbox('Automatically send my saved profile and tailored resume to employers matching my saved rules, up to my daily limit.')
        if st.button('Enable auto-apply', type='primary', disabled=not consent or not profile or not store.get('rules')):
            store.put('enabled', True)
            if not alive:
                subprocess.Popen([sys.executable, str(Path(__file__).with_name('worker.py'))], cwd=Path(__file__).parent,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            st.rerun()
        if st.button('Pause auto-apply now', disabled=not enabled):
            store.put('enabled', False); st.rerun()
        st.caption('The computer must remain awake. Standard Lever forms can be submitted automatically. CAPTCHA, login, agreements, custom questions, and other job sites require your attention. Pausing cannot undo an application already sent.')
    if st.button('Refresh application status'):
        st.rerun()
    status = st.selectbox('Show', ['All','queued','preparing','submitting','submitted','needs_attention','cancelled','closed'])
    visible = [a for a in apps if status == 'All' or a['status'] == status]
    if not visible:
        st.info('No applications here yet. Add matching jobs from Discover jobs, or enable auto-apply to discover and queue them automatically.')
    for a in visible:
        with st.container(border=True):
            st.subheader(a['job']['title'])
            st.caption(a['job']['company'].title() + ' · ' + a['status'].replace('_',' ').title())
            st.write(a['note'])
            st.link_button('Open employer application ↗', a['job']['apply_url'])
            if a['resume']:
                st.download_button('Download this application’s resume', docx_bytes(a['resume']), 'applylens-resume.docx', key='resume_'+a['id'])
            if a['status'] == 'queued' and st.button('Cancel this application', key='cancel_'+a['id']):
                store.update(a['id'], 'cancelled', 'Cancelled by you.'); st.rerun()
    if apps:
        import csv, io
        output = io.StringIO(); writer = csv.writer(output)
        writer.writerow(['Role','Company','Status','Application URL','Updated','Note'])
        for a in apps:
            # Guard spreadsheet formula execution in untrusted job titles.
            writer.writerow([("'"+str(v)) if str(v).startswith(('=','+','-','@')) else v for v in [a['job']['title'],a['job']['company'],a['status'],a['job']['apply_url'],a['updated'],a['note']]])
        st.download_button('Export application history', output.getvalue(), 'applylens-applications.csv', 'text/csv')

st.divider()
st.caption('ApplyLens · A local workspace for your job search. You control the profile, the rules, and the pause button.')
