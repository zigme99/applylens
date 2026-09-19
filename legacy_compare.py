"""Run with: streamlit run app.py"""
import hashlib
import os

import streamlit as st
from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from compare import MODEL, MAX_JOB, MAX_RESUME, compare_jobs, export_text, validate_inputs
from examples import LABELS, RESUME, JOBS, example_comparison

st.set_page_config(page_title='ApplyLens · Internship comparison', page_icon='🔎', layout='wide')
st.markdown('''<style>
    .block-container {max-width: 1120px; padding-top: 2.5rem;}
    h1 {letter-spacing: -0.045em; font-size: 3.3rem !important;}
    h2, h3 {letter-spacing: -0.025em;}
    [data-testid="stSidebar"] {background: #eff4fc;}
    .stButton>button[kind="primary"] {background: #2459dc; border-color: #2459dc;}
    [data-testid="stMetricValue"] {color: #2459dc;}
</style>''', unsafe_allow_html=True)


def show_results(result, labels, example=False):
    st.divider()
    st.subheader('Your comparison')
    if example:
        st.info('Prepared example using fictional data. These are hand-written results, not a live AI response.')
    st.caption('Supporting quotes are checked against the input. The interpretation still needs your review. '
               '“Not shown” means missing from the resume, not missing from your abilities.')
    cols = st.columns(len(result.jobs))
    for col, job in zip(cols, result.jobs):
        with col:
            with st.container(border=True):
                st.subheader(labels[job.job_number - 1])
                st.text(job.summary)
                supported = sum(r.status == 'evidence_found' for r in job.requirements)
                st.metric('Requirements with resume evidence', f'{supported} / {len(job.requirements)}')
                st.caption('Count of extracted requirements, not a fit score or an exhaustive checklist.')
                for req in job.requirements:
                    with st.expander(f'{req.requirement} · {req.status.replace("_", " ")}'):
                        st.caption(f'Posting importance: {req.importance}')
                        st.text(req.explanation)
                        st.caption('From the posting')
                        st.text(f'“{req.job_quote}”')
                        st.caption('From the resume')
                        st.text(f'“{req.resume_quote}”' if req.resume_quote else 'Not shown in the supplied resume.')
                st.markdown('**Eligibility to verify**')
                for item in job.eligibility:
                    with st.expander(f'{item.topic.replace("_", " ").capitalize()} · {item.status.replace("_", " ")}'):
                        st.text(f'“{item.job_quote}”' if item.job_quote else 'Not stated in the pasted posting.')
                        st.text(item.question_to_check)
                st.markdown('**Next steps**')
                for i, step in enumerate(job.next_steps, 1):
                    st.text(f'{i}. {step}')
    st.download_button('Download comparison', export_text(result, labels, example),
                       file_name='applylens-comparison.txt', mime='text/plain')


with st.sidebar:
    st.subheader('ApplyLens')
    st.caption('Version 0.1 · Built for students')
    mode = st.radio('Choose a workspace', ['Explore example', 'Compare my jobs'])
    st.divider()
    st.markdown('**A useful first pass**')
    st.write('Compare the evidence in your resume with what each posting actually says.')
    st.caption('Version 1 uses pasted text. It does not search for jobs, verify that listings are open, '
               'or submit applications.')
    if mode == 'Compare my jobs':
        st.divider()
        key = st.text_input('OpenAI API key', type='password', key='api_key',
                            help='Used for this session. Leave blank to use OPENAI_API_KEY on your local machine.')
        api_key = key or os.environ.get('OPENAI_API_KEY', '')
        st.caption('API usage is billed separately from ChatGPT Plus. No key is needed for the example.')
        st.caption(f'Model: {os.environ.get("OPENAI_MODEL", MODEL)}')

st.caption('LESS GUESSING. BETTER APPLICATION DECISIONS.')
st.title('Find the evidence.\nSee the gaps.')
st.write('One resume, up to three internships. Compare requirements and spot the details worth checking.')

if mode == 'Explore example':
    with st.expander('See the fictional resume and postings'):
        st.markdown('**Resume**')
        st.text(RESUME)
        for label, job in zip(LABELS, JOBS):
            st.markdown(f'**{label}**')
            st.text(job)
    show_results(example_comparison(), LABELS, example=True)
else:
    resume = st.text_area('Your resume', height=220, max_chars=MAX_RESUME,
                          placeholder='Paste resume text. Remove contact details you do not want to share.', key='resume')
    count = st.selectbox('Number of jobs', [1, 2, 3], index=1)
    jobs, labels = [], []
    for i, col in enumerate(st.columns(count)):
        with col:
            label = st.text_input(f'Job {i + 1} label', value=f'Job {i + 1}', key=f'label_{i}', max_chars=80)
            labels.append(label.strip() or f'Job {i + 1}')
            jobs.append(st.text_area(f'Job {i + 1} description', height=240, max_chars=MAX_JOB, key=f'job_{i}',
                                     placeholder='Paste the actual requirements and eligibility wording.'))
    consent = st.checkbox('Send this resume and these job descriptions to OpenAI for analysis.', key='consent')
    st.caption('This app does not write your inputs or key to disk. They remain in the active session. '
               'The API request uses store=False; provider data policies still apply. '
               'Eligibility notes are questions to verify, not work-authorization advice.')
    fingerprint = hashlib.sha256(repr((resume, jobs, labels)).encode()).hexdigest()
    if st.button('Compare internships', type='primary'):
        st.session_state.pop('comparison', None)
        try:
            validate_inputs(resume, jobs)
            if not api_key:
                raise ValueError('Add your OpenAI API key in the sidebar, or explore the example.')
            if not consent:
                raise ValueError('Confirm that you want to send this text to OpenAI.')
            with st.spinner('Comparing requirements and checking the supporting quotes…'):
                result = compare_jobs(resume, jobs, api_key, os.environ.get('OPENAI_MODEL', MODEL))
            st.session_state.comparison = (fingerprint, result)
        except AuthenticationError:
            st.error('The API key was not accepted. Check it in the sidebar.')
        except RateLimitError:
            st.error('The API account reached a rate or usage limit. Check your API billing and try later.')
        except APIConnectionError:
            st.error('Could not connect to OpenAI. Check your connection and try again.')
        except APIStatusError:
            st.error('OpenAI could not complete this request. Check model access or try again later.')
        except ValueError as exc:
            # Input/quote errors are local messages. Do not show arbitrary provider responses.
            if len(str(exc)) < 250:
                st.error(str(exc))
            else:
                st.error('The response could not be validated. Please try again.')
    saved = st.session_state.get('comparison')
    if saved and saved[0] == fingerprint:
        show_results(saved[1], labels)
    elif saved:
        st.info('Your inputs changed. Run a new comparison to see updated results.')

st.divider()
st.caption('Built as a learning project. Read the source quotes, check the original posting, and make your own decision.')
