# ApplyLens

**A resume-to-internship comparison tool for students.**

Paste your resume and up to three job descriptions. ApplyLens brings the requirements, supporting resume evidence, and unanswered eligibility questions into one comparison, so you can decide what to clarify and how to prepare an application.

[Quick start](#quick-start) · [Example](#example-comparison) · [How it works](#how-it-works) · [Roadmap](#roadmap)

## Why this project

Comparing internships means repeatedly checking the same things: required skills, preferred experience, graduation dates, location, and work-authorization wording. A requirement missing from your resume also does not necessarily mean you lack that skill.

ApplyLens makes those distinctions visible and keeps the original wording beside the analysis. The goal is to help students make informed application decisions, without an unexplained match percentage.

## Features

- **Compare 1–3 postings:** review each role alongside the same resume.
- **Inspect supporting evidence:** expand a requirement to see quotes from the posting and resume.
- **Identify resume gaps:** distinguish evidence found from qualifications not shown in the supplied text.
- **Check eligibility details:** surface enrollment, graduation, work authorization, sponsorship, and location wording. Unspecified details remain “not stated.”
- **Prepare next actions:** review suggested questions and application preparation steps.
- **Export the comparison:** download a plain-text copy.
- **Try a free example:** explore fictional inputs and a prepared comparison without an API key.

## Example comparison

The bundled example uses fictional student Jordan Lee and two fictional companies:

| Posting requirement | Resume evidence | Result |
|---|---|---|
| Python and SQL | Both are listed in the skills section | Evidence found |
| REST API experience preferred | A Flask API project is described | Relevant evidence found |
| Tableau preferred | Tableau is not mentioned | Not shown in the resume |
| Sponsorship policy | No policy appears in the first posting | Not stated; ask the employer |

The example is **hand-written sample output**, not a live model response. It demonstrates the interface and evidence format without sending data to an API.

## Tech stack

| Tool | Purpose |
|---|---|
| Python | Application and comparison logic |
| Streamlit | Input forms, comparison view, and downloads |
| OpenAI Responses API | Structured analysis of the supplied text |
| Pydantic | Response schemas and validation |
| pytest + Streamlit AppTest | Validation, mocked API, and interface tests |

**Version 1 uses one structured model request.** It is the comparison component of a future internship-search assistant; autonomous search and tool-calling workflows are planned, not implemented.

## Quick start

### 1. Clone and create an environment

Requires **Python 3.10+**. Development checks were run on Python 3.12.

```bash
git clone https://github.com/zigme99/applylens.git
cd applylens
python -m venv .venv
```

Activate the environment:

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Install and run

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open the local URL printed in your terminal. The app starts in **Explore example**, which needs no API key.

### 3. Compare your own postings

1. Choose **Compare my jobs** in the sidebar.
2. Enter an OpenAI API key in the password field, or configure `OPENAI_API_KEY` in your environment.
3. Paste your resume and select one, two, or three jobs.
4. Add a label and the full description for each job.
5. Review the data-sharing notice, select the consent checkbox, and click **Compare internships**.
6. Expand the evidence and eligibility sections, then download the comparison if useful.

Changing the input hides the previous comparison until you run it again.

### Configuration

| Setting | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | None | Optional environment alternative to the sidebar password field |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Must support the Responses API and structured outputs |
| Resume length | 80–15,000 characters | Paste text; PDF parsing is not included |
| Each job description | 80–12,000 characters | One to three descriptions per comparison |

The app does not automatically load `.env` files. OpenAI API usage requires separate API access and billing; a ChatGPT Plus subscription does not cover these requests.

## How it works

```text
Resume + job descriptions
          |
     Validate inputs
          |
  Request structured analysis
          |
   Validate response schema
          |
 Check quotes against source text
          |
  Display and export comparison
```

The prompt asks the model to treat pasted documents as data and extract relevant requirements. Pydantic checks the response structure. Local checks then verify job ordering, eligibility topics, and whether each supporting quote exists in the correct source.

Quote checks normalize whitespace introduced by copying and pasting. A quote that is absent from its source causes the comparison to be rejected.

**A verified quote is not a verified conclusion.** These checks do not establish that the model interpreted the evidence correctly or extracted every important requirement. Review the original posting before acting on the analysis.

## Project structure

```text
applylens/
├── app.py            # Streamlit interface and session state
├── compare.py        # Schemas, prompt, API call, evidence checks, export
├── examples.py       # Fictional inputs and prepared example output
├── test_compare.py   # Unit and interface tests
├── requirements.txt  # Pinned direct dependencies
├── .gitignore
└── README.md
```

## Testing

```bash
python -m pytest -q
```

**Initial validation: 18 tests passed.** Tests cover input limits, invented or misplaced quotes, missing eligibility topics, provider refusal handling, exports, and Streamlit interactions. The application also started locally.

Provider responses are mocked in the tests. **A live API comparison has not yet been verified**, and real-model accuracy has not been measured.

## Privacy and current limits

- Inputs, keys, and results are held in the active Streamlit session. The app does not intentionally save them to disk or cache API calls.
- Live analysis sends the pasted resume and descriptions to OpenAI. Requests use `store=False`, which does not disable every form of provider retention. Review [OpenAI's data controls](https://developers.openai.com/api/docs/guides/your-data) and remove unnecessary personal details before submitting.
- The sample contains no real resumes. Common secret files are excluded by `.gitignore`.
- Version 1 is designed for local use. Public hosting would need access controls, usage limits, and an appropriate privacy policy.
- The app does not search job boards, check whether listings are open, submit applications, or determine work authorization. Eligibility notes identify questions to verify.

## Roadmap

- [ ] Test model output against a small, manually reviewed set of resume/posting pairs.
- [ ] Add a search tool and bounded agent loop for researching accessible postings.
- [ ] Save shortlists and application progress with SQLite.
- [ ] Introduce resumable workflow state if the research process needs it.

## Feedback

Found a confusing comparison or a missing check? [Open an issue](https://github.com/zigme99/applylens/issues) with a short description and a fictional or redacted example. Do not include API keys or private resume details.

Built with AI-assisted development as a practical learning project in structured LLM outputs, evidence validation, and Python application development.
