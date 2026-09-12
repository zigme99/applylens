"""Fictional inputs and a hand-written example. No API calls or real personal data."""
from compare import Comparison, check_evidence

RESUME = '''Jordan Lee — Computer Science student, graduating May 2028.
Skills: Python, SQL, Git, pandas.
Built a Flask API for a campus book exchange and wrote unit tests with pytest.
Analyzed bike-share trips with pandas and presented findings to a student club.
Seeking a summer internship. No work-authorization details are provided here.'''

JOBS = [
    '''Harbor Labs — Backend Engineering Intern (fictional posting).
Required: Python and SQL. Experience building REST APIs is preferred.
Applicants must be enrolled in a computer science or related degree.
This is a hybrid position in Boston, three days per week on site.
Interns will help maintain backend services and write tests.''',
    '''Maple Analytics — Data Intern (fictional posting).
Required: Python and pandas. Familiarity with Tableau is preferred.
Applicants must graduate between December 2027 and June 2029.
This position is remote within the United States.
We do not offer employment visa sponsorship for this position.
Interns will clean datasets and explain findings to the analytics team.''',
]
LABELS = ['Harbor Labs · Backend intern', 'Maple Analytics · Data intern']


def example_comparison():
    jobs = []
    requirements = [
        [dict(requirement='Python and SQL', importance='required', status='evidence_found',
              job_quote='Required: Python and SQL.', resume_quote='Skills: Python, SQL, Git, pandas.',
              explanation='Both languages are explicitly listed; proficiency still needs to be demonstrated.'),
         dict(requirement='REST API experience', importance='preferred', status='evidence_found',
              job_quote='Experience building REST APIs is preferred.',
              resume_quote='Built a Flask API for a campus book exchange and wrote unit tests with pytest.',
              explanation='The Flask project is relevant evidence. Explain its API design in an interview.')],
        [dict(requirement='Python and pandas', importance='required', status='evidence_found',
              job_quote='Required: Python and pandas.', resume_quote='Skills: Python, SQL, Git, pandas.',
              explanation='The resume lists both, with a separate pandas project providing context.'),
         dict(requirement='Tableau', importance='preferred', status='not_shown',
              job_quote='Familiarity with Tableau is preferred.', resume_quote=None,
              explanation='Tableau is not mentioned. That is a resume evidence gap, not proof of missing ability.')],
    ]
    quotes = [
        {'enrollment': 'Applicants must be enrolled in a computer science or related degree.',
         'location': 'This is a hybrid position in Boston, three days per week on site.'},
        {'graduation': 'Applicants must graduate between December 2027 and June 2029.',
         'location': 'This position is remote within the United States.',
         'sponsorship': 'We do not offer employment visa sponsorship for this position.'},
    ]
    questions = {
        'enrollment': 'What enrollment status must be maintained during the internship?',
        'graduation': 'Does the employer accept your expected graduation date?',
        'work_authorization': 'What work authorization is required for the internship dates?',
        'sponsorship': 'What does the employer require regarding present or future sponsorship?',
        'location': 'Can you work from the specified location during the internship?',
    }
    for i in range(2):
        jobs.append(dict(job_number=i + 1,
            summary=['The resume has evidence for the listed technical requirements. Confirm the Boston schedule.',
                     'The pandas experience is relevant. Tableau is not shown, and sponsorship needs attention.'][i],
            requirements=requirements[i],
            eligibility=[dict(topic=topic, status='stated' if topic in quotes[i] else 'not_stated',
                              job_quote=quotes[i].get(topic), question_to_check=question)
                         for topic, question in questions.items()],
            next_steps=[['Prepare a brief walkthrough of the Flask project.', 'Confirm the on-site schedule.'],
                        ['Explain one finding from the bike-share analysis.', 'Clarify the sponsorship requirement before deciding.']][i]))
    return check_evidence(Comparison(jobs=jobs), RESUME, JOBS)
