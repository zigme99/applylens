from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest

from compare import check_evidence, compare_jobs, contains_quote, export_text, validate_inputs
from examples import JOBS, LABELS, RESUME, example_comparison


def test_example_quotes_are_real():
    result = example_comparison()
    assert check_evidence(result, RESUME, JOBS) is result
    assert result.jobs[0].eligibility[3].status == 'not_stated'


def test_paste_whitespace_is_accepted():
    assert contains_quote('Python and SQL.', 'Required: Python\n  and SQL.')
    assert not contains_quote('', RESUME)


@pytest.mark.parametrize('resume,jobs', [('', JOBS), (RESUME, []),
    (RESUME, JOBS * 2), (RESUME, ['short']), ('x' * 15001, JOBS), (RESUME, ['x' * 12001])])
def test_input_limits(resume, jobs):
    with pytest.raises(ValueError):
        validate_inputs(resume, jobs)


def test_invented_resume_evidence_is_rejected():
    result = example_comparison()
    result.jobs[0].requirements[0].resume_quote = 'Five years of production Kubernetes experience.'
    with pytest.raises(ValueError, match='resume quote'):
        check_evidence(result, RESUME, JOBS)


def test_quote_from_wrong_job_is_rejected():
    result = example_comparison()
    result.jobs[0].requirements[0].job_quote = 'Required: Python and pandas.'
    with pytest.raises(ValueError, match='job quote'):
        check_evidence(result, RESUME, JOBS)


def test_invented_sponsorship_statement_is_rejected():
    result = example_comparison()
    item = next(e for e in result.jobs[0].eligibility if e.topic == 'sponsorship')
    item.status = 'stated'
    item.job_quote = 'We sponsor all applicants.'
    with pytest.raises(ValueError, match='eligibility quote'):
        check_evidence(result, RESUME, JOBS)


def test_duplicate_job_number_is_rejected():
    result = example_comparison()
    result.jobs[1].job_number = 1
    with pytest.raises(ValueError, match='every job'):
        check_evidence(result, RESUME, JOBS)


def test_missing_eligibility_topic_is_rejected():
    result = example_comparison()
    result.jobs[0].eligibility[0].topic = 'graduation'
    with pytest.raises(ValueError, match='eligibility topic'):
        check_evidence(result, RESUME, JOBS)


def test_live_adapter_with_mocked_provider():
    result = example_comparison()
    mock_client = MagicMock()
    mock_client.responses.parse.return_value = SimpleNamespace(output_parsed=result, status='completed')
    with patch('compare.OpenAI') as constructor:
        constructor.return_value.__enter__.return_value = mock_client
        assert compare_jobs(RESUME, JOBS, 'test-key') == result
    kwargs = mock_client.responses.parse.call_args.kwargs
    assert kwargs['store'] is False
    assert len(kwargs['input']) == 2


def test_refusal_does_not_become_a_result():
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(output_parsed=None, status='completed')
    with patch('compare.OpenAI') as constructor:
        constructor.return_value.__enter__.return_value = client
        with pytest.raises(ValueError, match='complete comparison'):
            compare_jobs(RESUME, JOBS, 'test-key')


def test_export_keeps_evidence_and_demo_label():
    text = export_text(example_comparison(), LABELS, example=True)
    assert 'not live AI output' in text
    assert 'Required: Python and SQL.' in text
    assert 'Not stated' in text


def test_app_example_and_missing_input():
    app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run()
    assert not app.exception
    assert len(app.metric) == 2
    app.radio[0].set_value('Compare my jobs').run()
    app.button[0].click().run()
    assert not app.exception
    assert 'Paste a resume' in app.error[0].value


def test_app_live_flow_with_mock_and_stale_result():
    app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run()
    app.radio[0].set_value('Compare my jobs').run()
    app.text_area(key='resume').set_value(RESUME)
    app.text_area(key='job_0').set_value(JOBS[0])
    app.text_area(key='job_1').set_value(JOBS[1])
    app.text_input(key='api_key').set_value('test-key')
    app.checkbox(key='consent').check()
    with patch('compare.compare_jobs', return_value=example_comparison()):
        app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 2
    app.text_area(key='resume').set_value(RESUME + '\nA new project.').run()
    assert len(app.metric) == 0
    assert any('inputs changed' in info.value for info in app.info)
