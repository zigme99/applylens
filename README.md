# ApplyLens ↗

**Upload your resume. Set your rules. Keep your job search moving.**

ApplyLens is a local, single-user job-search and application workspace. It replaces the original paste-and-compare screen with a resume profile, live job discovery, tailored document downloads, an application queue, and a background runner.

## What works today

- **Resume upload:** PDF, DOCX, and TXT, with editable extracted text and a saved applicant profile.
- **Live discovery:** searches configurable company boards using the public Ashby, Greenhouse, and Lever feeds. Default boards are included; this is not an internet-wide job index.
- **Your rules:** role titles, excluded title keywords, location, remote-only, employment type, posting age, required posting keywords, minimum shared resume keywords, excluded companies, and daily attempt limits.
- **Truthful tailoring:** relevant bullet points move earlier *within their original section*. Every original line is preserved. Download an editable DOCX. This is extractive tailoring, not AI rewriting or a claim of qualification.
- **Application queue:** durable SQLite state, duplicate protection, current-listing revalidation, cancellation, pause, and CSV history export.
- **Background runner:** checks configured boards every 30 minutes and processes queued jobs while enabled and the computer is awake.
- **Limited auto-submission:** a browser adapter for standard hosted Lever forms with recognized applicant fields. It uploads the tailored resume and submits only after the user enables auto-apply. Employer confirmation text is required to record success.

## Important scope

This is an initial local product, not a universal application bot. **Real employer submission has not been end-to-end verified.** Automated tests use mocked employer responses and form metadata. Ashby and Greenhouse discovery work, but their application forms currently require manual completion. Lever forms with CAPTCHA, login, custom questions, consent choices, or agreements also move to **Needs attention**. The runner does not bypass those steps, invent answers, or automatically retry an uncertain submission.

It does not yet support salary/sponsorship inference, arbitrary job-board search, semantic qualification scoring, AI resume rewriting, cover letters, LinkedIn/Indeed/Workday automation, email inbox tracking, or multi-user hosting. A keyword match is not an eligibility decision. A remote listing can still restrict where you live.

## Run locally (macOS / Linux)

Python 3.10+ required. The background runner uses a POSIX process lock.

```bash
git clone https://github.com/zigme99/applylens.git
cd applylens
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

1. Open **My resume**, upload a file, review the text, and save your profile.
2. Open **Job preferences** and save your filters and company boards.
3. Open **Discover jobs** and search live listings. Inspect postings and download tailored resumes or add jobs to the queue.
4. In **Applications**, read the scope, authorize sending your profile and resume to matching employers, and enable auto-apply. The UI starts the local worker. Leave the computer awake.
5. Review **Needs attention** items and complete unsupported forms on the employer site.

Use the sidebar pause button to stop new attempts. Editing your profile or rules also pauses automation and cancels queued work made under old settings. Pausing cannot retract a request already sent. The daily UTC limit counts attempts that began transmitting data, including uncertain outcomes; it is not a promise of a number of successful submissions.

You can also start the worker yourself:

```bash
python worker.py
# Or process one cycle, for diagnostics:
python worker.py --once
```

Only one worker can hold the data-directory lock. An interrupted submission is never silently retried after restart.

## Job sources

Use up to 20 boards, one per line, using the company identifier from the hosted careers URL:

```text
ashby:linear
ashby:notion
lever:sep
greenhouse:figma
greenhouse:stripe
```

Data comes from [Ashby's public posting API](https://developers.ashbyhq.com/docs/public-job-posting-api), [Lever's public posting API](https://github.com/lever/postings-api), and [Greenhouse's job board API](https://docs.greenhouse.io/job-board.html). No employer API keys are required for listing discovery. Missing publication dates remain unknown and fail an active age filter. Greenhouse `updated_at` is never treated as a publication date.

## Privacy and storage

Profiles, extracted resume text, preferences, listings, and application history are stored in `private_data/applylens.db` on your computer. Original uploads are not retained. Temporary application DOCX files are removed after each attempt. The folder is excluded from Git. It is **not encrypted at rest**; use your device's account and disk protections. Set `APPLYLENS_DATA_DIR` to choose a different local storage folder.

The new workflow does not send documents to an AI provider and needs no API key. Enabling auto-apply permits sending your saved contact fields and tailored resume to matching supported employer forms. Browser processes are ephemeral; saved browser credentials are not used. Keep the server on loopback; the app has no multi-user authentication and is not ready for public hosting.

The earlier API comparison experiment is retained separately as `legacy_compare.py` for reference and its existing tests. It is not part of the main application workflow.

## Validation

```bash
python -m pytest -q
```

Tests cover source normalization, partial feed failure, freshness and hard filters, document import, faithful tailoring, duplicate and cancellation behavior, revision changes, pause and daily quota enforcement, interrupted submissions, unsupported forms, worker transitions, and all five UI pages. No real applications are sent by the test suite.

## Structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit product UI |
| `sources.py` | Public feeds and hard filters |
| `resumes.py` | Resume extraction, bullet ordering, DOCX export |
| `storage.py` | SQLite state, atomic quota reservation, audit events |
| `worker.py` | Persistent local discovery and application runner |
| `automation.py` | Limited Lever adapter and manual handoff conditions |
| `test_product.py` | New product tests |
| `legacy_compare.py`, `compare.py`, `examples.py` | Original comparison experiment |
