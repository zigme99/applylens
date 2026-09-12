# ApplyLens

Compare your resume with up to three internship descriptions. See which requirements have supporting evidence, what is not shown, and which eligibility details need checking.

This is version 1 of a student project. It uses pasted text and a single structured LLM request. It is **not an autonomous job-search agent yet**.

## What it does

- Shows technical requirements with quotes from the posting and resume.
- Separates required and preferred qualifications when the text supports it.
- Marks absent resume evidence as **not shown**, rather than assuming you lack a skill.
- Surfaces enrollment, graduation, location, work-authorization, and sponsorship wording. Missing details stay **not stated**.
- Gives practical next steps and a downloadable text comparison.
- Includes a fictional, hand-written example that works without an API key.

There are no fit percentages, automatic applications, or claims that you qualify for a visa or job. The app does not fetch links or verify whether a listing is still open.

## Try it locally

Python 3.10 or newer is required.

```bash
git clone https://github.com/zigme99/applylens.git
cd applylens
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

The app opens on **Explore example**. Choose **Compare my jobs** to paste your own text. Add an OpenAI API key in the password field or set `OPENAI_API_KEY` in your environment. The app does not load `.env` files automatically.

The default model is `gpt-4.1-mini`; `OPENAI_MODEL` can select another Responses API model supporting structured outputs. API access and billing are separate from ChatGPT Plus. Click Compare only after reviewing the text-sharing notice.

## How it works

```text
Resume + 1–3 descriptions
        ↓
Input length checks
        ↓
OpenAI structured response → Pydantic models
        ↓
Check quoted evidence against the original text
        ↓
Side-by-side comparison and text download
```

`app.py` handles the Streamlit interface. `compare.py` contains the response models, prompt, API call, quote checks, and export. `examples.py` holds fictional sample content. `test_compare.py` tests the validation, mocked API flow, and interface.

The quote checker accepts whitespace differences from pasting, but rejects quotations absent from the relevant source. It also checks job ordering and the five eligibility topics. This catches invented quotes; **it does not prove that the model interpreted them correctly or extracted every requirement**. Always review the source text.

## Run the checks

```bash
python -m pytest -q
```

Initial checks: **18 tests passed** on Python 3.12, including Streamlit interaction tests. The application also started locally.

Tests use fictional data and mocked provider responses. They do not consume API credits or establish real-model accuracy. A live API request has not been verified during initial development because no API key was configured.

## Data handling

The app keeps inputs and results in the current Streamlit session. It does not intentionally write resumes, descriptions, or keys to disk, and it does not cache provider calls. Live mode sends the pasted documents to OpenAI using `store=False`; this setting does not mean all provider retention is disabled. Review [OpenAI's data controls](https://developers.openai.com/api/docs/guides/your-data) and remove personal details you do not need to share.

The example uses invented people and companies. No real resume is bundled. `.gitignore` excludes common secret files. This version is intended for local use: before running a public hosted service, add access controls, request limits, and a clear privacy policy. Never expose an unrestricted server-funded API key to public traffic.

## What I want to learn next

1. Evaluate comparisons against a small manually reviewed dataset.
2. Add a search tool and a bounded agent loop for finding accessible postings.
3. Save a shortlist and application status in SQLite.
4. Add workflow state with LangGraph if the research process needs it.

For now, the focus is a small comparison tool that is easy to understand and improve. Built with Python, Streamlit, Pydantic, and the OpenAI API, with AI-assisted development.

API references: [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
