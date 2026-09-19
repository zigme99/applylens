from collections import Counter
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from streamlit.testing.v1 import AppTest
import storage as store
from sources import match, board_specs, fetch_board, discover, stamp
from resumes import extract, tailor, docx_bytes
from automation import supported_url, preflight, NeedsAttention
from worker import run_cycle

RESUME = 'Jordan Lee\nEXPERIENCE\nExample Company, Intern, 2025\n- Built Java tools for a school project.\n- Built Python APIs with SQL storage.\nEDUCATION\nExample University, Computer Science, 2027'
RULES = dict(roles='engineer, intern', locations='', remote_only=False, employment='', max_days=7, required_terms='', excluded='', daily_limit=1, boards='lever:example')
JOB = dict(id='lever:example:12345678-1234-1234-1234-123456789abc', source='lever:example', company='example', title='Software Engineer', location='New York, United States', remote=True, employment='Full-time', posted=datetime.now(timezone.utc).isoformat(), description='Build Python APIs with SQL storage.', url='https://jobs.lever.co/example/12345678-1234-1234-1234-123456789abc', apply_url='https://jobs.lever.co/example/12345678-1234-1234-1234-123456789abc/apply')
PROFILE = dict(name='Jordan Lee', email='jordan@example.com', resume=RESUME)

@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path / 'data')

def setup():
    store.save_configuration('profile', PROFILE)
    store.save_configuration('rules', RULES)
    store.put('enabled', True)

def fields():
    return [dict(name=n, type=t, required=True) for n,t in [('name','text'), ('email','email'), ('resume','file')]]

def test_filters_and_unknown_dates():
    assert match(JOB, RULES) == []
    assert match(JOB | {'posted': None}, RULES) == ['Publication date unavailable']
    assert not match(JOB | {'posted':None}, RULES | {'max_days':0})
    old = (datetime.now(timezone.utc)-timedelta(days=9)).isoformat()
    assert 'Outside posting-age limit' in match(JOB | {'posted':old}, RULES)
    assert 'Location does not match' in match(JOB, RULES | {'locations':'Canada'})
    assert 'Excluded company' in match(JOB, RULES | {'excluded':'example'})
    assert 'Required keyword missing' in match(JOB, RULES | {'required_terms':'Kubernetes'})
    assert 'Not explicitly remote' in match(JOB | {'remote':False}, RULES | {'remote_only':True})

def test_feed_identifiers_cannot_inject_urls():
    with pytest.raises(ValueError):
        board_specs('lever:../../evil')
    assert board_specs('lever:example\nlever:example') == ['lever:example']

def test_greenhouse_does_not_use_updated_as_posted():
    with patch('sources.get_json', return_value={'jobs':[dict(id=123,title='Engineer',location={'name':'Remote'},content='<p>Python</p>',updated_at='2026-09-19T00:00:00Z',absolute_url='https://boards.greenhouse.io/example/jobs/123')]}):
        job = fetch_board('greenhouse:example')[0]
    assert job['posted'] is None
    assert job['description'] == 'Python'

def test_ashby_unlisted_excluded():
    with patch('sources.get_json', return_value={'jobs':[{'isListed':False}]}):
        assert fetch_board('ashby:example') == []

def test_partial_feed_failure_keeps_good_results():
    def fetch(spec):
        if spec == 'lever:bad': raise ValueError()
        return [JOB]
    with patch('sources.fetch_board', side_effect=fetch):
        jobs, errors = discover('lever:example\nlever:bad')
    assert len(jobs) == len(errors) == 1

def test_tailoring_preserves_facts_and_context():
    text, shared = tailor(RESUME, 'Python APIs SQL')
    assert Counter(text.splitlines()) == Counter(RESUME.splitlines())
    assert text.index('- Built Python') < text.index('- Built Java')
    assert text.index('Example Company') < text.index('- Built Python') < text.index('EDUCATION')
    assert 'python' in shared

def test_resume_roundtrip_and_bad_input():
    data = docx_bytes(RESUME)
    assert 'Jordan Lee' in extract('resume.docx', data)
    assert extract('resume.txt', RESUME.encode()) == RESUME
    with pytest.raises(ValueError): extract('bad.pdf', b'not a pdf')
    with pytest.raises(ValueError): extract('big.txt', b'x' * (5*1024*1024+1))
    with pytest.raises(ValueError): extract('scan.txt', b'')

def test_duplicate_and_cancel_rules():
    setup()
    assert store.enqueue(JOB)
    assert not store.enqueue(JOB)
    store.update(JOB['id'], 'cancelled', 'Cancelled by you')
    assert not store.enqueue(JOB)
    assert store.enqueue(JOB, manual=True)
    store.update(JOB['id'], 'submitted', 'confirmed')
    assert not store.enqueue(JOB, manual=True)

def test_revision_disarms_and_cancels():
    setup(); store.enqueue(JOB)
    store.save_configuration('profile', PROFILE | {'name':'Jordan'})
    assert not store.get('enabled')
    assert store.rows()[0]['status'] == 'cancelled'

def test_atomic_quota_and_attempt_never_retried():
    setup(); store.enqueue(JOB)
    item = store.claim(1)
    assert store.reserve_submission(JOB['id'],item['revision'],1)
    assert not store.reserve_submission(JOB['id'],item['revision'],1)
    store.recover()
    assert store.rows()[0]['status'] == 'needs_attention'
    assert not store.enqueue(JOB)
    store.enqueue(JOB | {'id':'second'})
    assert store.claim(1) is None

def test_pause_and_revision_prevent_transmission():
    setup(); store.enqueue(JOB); item=store.claim(5)
    store.put('enabled', False)
    assert not store.reserve_submission(JOB['id'],item['revision'],5)
    store.put('enabled', True)
    assert not store.reserve_submission(JOB['id'],item['revision']-1,5)

def test_adapter_scope():
    assert supported_url(JOB['apply_url'])
    assert not supported_url(JOB['apply_url'].replace('jobs.lever.co', 'jobs.lever.co.evil.com'))
    assert not supported_url(JOB['apply_url'].replace('https:', 'http:'))

def test_form_preflight():
    preflight(fields(), PROFILE, 'Apply for this job')
    for extra in [dict(name='why',type='textarea',required=True), dict(name='agree',type='checkbox',required=False)]:
        with pytest.raises(NeedsAttention): preflight(fields()+[extra], PROFILE, '')
    with pytest.raises(NeedsAttention): preflight(fields(), PROFILE, '', True)
    with pytest.raises(NeedsAttention): preflight(fields(), PROFILE, 'By submitting you agree to our terms')
    with pytest.raises(NeedsAttention): preflight(fields()[1:], PROFILE, '')

def test_worker_closed_job_never_submits():
    setup(); store.enqueue(JOB); store.put('last_search_epoch', 10**12)
    with patch('worker.fetch_board', return_value=[]), patch('worker.apply_lever') as apply:
        run_cycle(); apply.assert_not_called()
    assert store.rows()[0]['status'] == 'closed'

def test_worker_confirmed_and_paused():
    setup(); store.enqueue(JOB); store.put('last_search_epoch', 10**12)
    def submit(job, profile, path, authorize, still_enabled):
        assert path.exists() and authorize() and still_enabled()
        return 'Confirmed by employer'
    with patch('worker.fetch_board', return_value=[JOB]), patch('worker.apply_lever', side_effect=submit):
        run_cycle()
    assert store.rows()[0]['status'] == 'submitted'
    assert not list(store.DATA.glob('*.docx'))
    store.put('enabled', False)
    with patch('worker.discover') as search:
        run_cycle(); search.assert_not_called()

def test_worker_unknown_outcome_is_not_submitted():
    setup(); store.enqueue(JOB); store.put('last_search_epoch', 10**12)
    with patch('worker.fetch_board', return_value=[JOB]), patch('worker.apply_lever', side_effect=NeedsAttention('Check employer')):
        run_cycle()
    assert store.rows()[0]['status'] == 'needs_attention'

def test_all_ui_pages_render_and_disabled_autorun():
    app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run()
    assert not app.exception
    assert len(app.metric) == 4
    for page in ['My resume','Job preferences','Discover jobs','Applications']:
        app.radio[0].set_value(page).run()
        assert not app.exception
    assert next(b for b in app.button if b.label == 'Enable auto-apply').disabled

def test_live_search_ui_mocked():
    setup()
    app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run()
    app.radio[0].set_value('Discover jobs').run()
    with patch('sources.discover', return_value=([JOB], [])):
        next(b for b in app.button if b.label == 'Search live jobs').click().run()
    assert not app.exception
    assert store.get('jobs')[0]['id'] == JOB['id']

def test_role_boundaries_and_resume_filter():
    assert 'Role title does not match' in match(JOB | {'title':'Internal Audit Lead'}, RULES)
    assert 'Role title does not match' not in match(JOB | {'title':'Software Internship'}, RULES)
    assert 'Too few shared resume keywords' in match(JOB, RULES | {'min_overlap': 3}, resume='Cooking and baking pastries')
    assert not match(JOB, RULES | {'min_overlap': 3}, resume=RESUME)
    assert 'Excluded title keyword' in match(JOB | {'title':'Senior Software Engineer'}, RULES | {'excluded_titles':'senior'})

def test_timezone_offsets_are_preserved():
    assert stamp('2026-09-19T10:00:00-05:00') == '2026-09-19T15:00:00+00:00'

def test_employment_normalizes_hyphens():
    assert not match(JOB, RULES | {'employment':'FullTime'})
