# NaqshaCheck MVP

NaqshaCheck is an AI-assisted, applicant-side building-plan pre-submission checker. It compares **human-confirmed measurements** with a **versioned, architect-reviewed rule pack**, highlights likely problems, and produces an advisory report before official submission.

> **NaqshaCheck provides an advisory pre-submission review. It does not issue official approval, replace a licensed architect or guarantee acceptance by any authority.**

The deterministic rule engine makes application-level preflight decisions. Groq AI is optional and may suggest visible measurements, draft candidate rules for professional review, or explain deterministic findings. AI never activates rules or independently declares legal compliance.

## Architecture

### Layer 1 — optional AI assistance

`src/ai_agent.py` provides isolated Groq features:

- visible plan-label / dimension extraction from a resized first-page image;
- confidence scores and uncertainty reporting;
- candidate regulation-rule extraction for `ingest.py`;
- explanation of already-computed deterministic findings;
- Pydantic validation, structured JSON/schema output, timeout/error handling, rate-limit handling, and one controlled retry for malformed responses.

AI measurements remain suggestions until a user explicitly confirms/corrects and applies them. AI-generated regulation rules are always marked `AI-DRAFT` and `HUMAN_REVIEW_REQUIRED` at the draft-pack level.

### Layer 2 — deterministic compliance engine

- `src/models.py` — validated project/rule/finding contracts.
- `src/rules.py` — loads versioned YAML rule packs.
- `src/checks.py` — deterministic comparisons only; no LLM calls.
- `src/plan_reader.py` — first-page rendering and basic PDF text-layer dimension discovery.
- `src/annotations.py` — advisory plan overlay.
- `src/report.py` — advisory PDF with rule version and citation.

The intended trust boundary is:

```text
Human-confirmed measurements
+ architect-reviewed, versioned authority rules
= deterministic preflight result
```

## Current Groq models

Verified against Groq's official model documentation on **29 September 2026**:

- Text / structured reasoning default: `openai/gpt-oss-20b`
- Vision default: `qwen/qwen3.8-27b` — currently a **Preview** multimodal model

Both support Structured Outputs / JSON Schema mode according to Groq's current documentation. Because preview availability can change, the vision model is configurable and isolated from the deterministic engine.

Official references:

- https://console.groq.com/docs/models
- https://console.groq.com/docs/model/openai/gpt-oss-20b
- https://console.groq.com/docs/model/qwen/qwen3.8-27b
- https://console.groq.com/docs/structured-outputs
- https://console.groq.com/docs/vision

## Repository structure

```text
naqshacheck-mvp/
├── app.py
├── ingest.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── data/rules/
│   └── lda_5_marla_residential.yaml
├── docs/
│   └── ui-concept.png
├── src/
│   ├── __init__.py
│   ├── models.py
│   ├── rules.py
│   ├── checks.py
│   ├── plan_reader.py
│   ├── annotations.py
│   ├── report.py
│   └── ai_agent.py
├── tests/
│   ├── test_app.py
│   ├── test_checks.py
│   └── test_ai_agent.py
└── .github/workflows/
    └── test.yml
```

## Local setup

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows cmd
.venv\Scripts\activate.bat

# macOS/Linux
source .venv/bin/activate
```

Then install and run:

```bash
pip install -r requirements.txt
pytest -q
streamlit run app.py
```

The application works without Groq. In that mode, deterministic checking, report generation, PDF rendering, and manual measurements remain available.

## Groq setup

Never commit an API key. `.streamlit/secrets.toml` is ignored by Git.

For local development, create `.streamlit/secrets.toml` from the example:

```toml
GROQ_API_KEY = "user-key"
```

You can also configure the key as an environment variable. Optional model overrides are:

```text
GROQ_TEXT_MODEL=openai/gpt-oss-20b
GROQ_VISION_MODEL=qwen/qwen3.8-27b
```

If no key is available, AI actions are not offered and no Groq import/runtime failure should block deterministic checking.

## Plan-analysis workflow

1. Upload PDF, JPG, JPEG, or PNG (MVP upload limit: 25 MB).
2. PDFs are rendered from page 1; raster images are opened in memory.
3. If Groq is configured, choose **Analyze visible plan labels with AI**.
4. The image is resized/compressed before transmission.
5. Groq returns structured observations, confidence, evidence, and uncertainties.
6. Review each candidate, correct it if necessary, and explicitly check **I confirm this measurement candidate**.
7. Choose **Apply confirmed candidates to measurement form**.
8. Run the deterministic compliance check from the confirmed form values.

Uploaded plans are processed in memory by this MVP and are not intentionally persisted by NaqshaCheck. Deployment/provider logs and transport should still be covered by a production privacy review before handling real confidential plans.

## Regulation ingestion

Text-only draft creation remains the default:

```bash
python ingest.py path/to/regulations.pdf --authority LDA --output data/rules/lda_draft.yaml
```

Optional AI-assisted candidate extraction:

```bash
python ingest.py path/to/regulations.pdf --authority LDA --output data/rules/lda_ai_draft.yaml --ai-draft
```

`--ai-draft` requires `GROQ_API_KEY`. The command includes page labels in extracted chunks and asks Groq only for explicit numerical requirements. Every generated rule is `AI-DRAFT`; the output metadata sets `status: HUMAN_REVIEW_REQUIRED` and `activation_allowed: false`. Nothing is copied into the active rule pack automatically.

Use `--max-ai-chunks N` to cap AI calls/cost for long regulation PDFs.

## GitHub deployment

1. Create a GitHub repository, for example `naqshacheck-mvp`.
2. Copy this repository's files into it while preserving folders.
3. Confirm `.streamlit/secrets.toml` is **not** present in the commit. Only `secrets.toml.example` should be committed.
4. From the repository root:

```bash
git init
git add .
git status
git commit -m "Add optional Groq AI assistance with deterministic compliance boundary"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/naqshacheck-mvp.git
git push -u origin main
```

5. Open the GitHub **Actions** tab and confirm the `test` workflow passes.

## Streamlit Community Cloud deployment

1. Sign in to Streamlit Community Cloud.
2. Choose **Create app** and select the GitHub repository.
3. Branch: `main`.
4. Main file: `app.py`.
5. Open **App settings → Secrets** and add:

```toml
GROQ_API_KEY = "your-real-key"
```

6. Deploy/reboot the app.
7. Confirm the sidebar says optional Groq AI assistance is configured.
8. Test once with no secret (or a local no-key run) to confirm deterministic checking still works independently.
9. Test AI extraction with a non-confidential sample plan before using real project material.

## Rule-pack safety

The included `data/rules/lda_5_marla_residential.yaml` is still explicitly marked `DEMO_NOT_LEGAL_SOURCE`. Before real-world use:

1. obtain the current official authority regulation;
2. record source URL, effective date, amendments, applicability, and exceptions;
3. have a licensed architect verify every rule and citation;
4. add tests for boundary values and missing-information behavior;
5. freeze a reviewed rule-pack version;
6. keep draft and active rule packs separate.

## Tests

`tests/test_ai_agent.py` uses mocked Groq responses. It makes **no real paid API requests**. It verifies structured validation, one malformed-response retry, no-key behavior, and forced `AI-DRAFT` status.

```bash
pytest -q
```

## Production blockers / next steps

- Replace demo LDA rules with professionally reviewed current rules.
- Add explicit missing-information states to the deterministic engine rather than relying on fully populated manual fields.
- Add authentication, encrypted storage, retention controls, and audit history before retaining any real plans.
- Add a measurement canvas / scale calibration workflow for reliable geometry.
- Validate extraction and compliance performance against de-identified plans reviewed by licensed architects.
- Complete privacy, liability, professional-indemnity, and authority-branding review.


## Gemini vision setup

NaqshaCheck uses Gemini for architectural-plan image extraction and keeps the deterministic
rule engine authoritative. Gemini is also used for explanations of deterministic findings; Groq is no longer required by the MVP.

1. Create a Gemini API key in Google AI Studio.
2. In Streamlit Community Cloud, open **App settings → Secrets**.
3. Add:

```toml
GEMINI_API_KEY = "your-real-key"
GEMINI_VISION_MODEL = "gemini-3.8-flash"

```

Never commit real API keys to GitHub.

Gemini returns advisory measurement candidates, confidence, evidence and (when available)
normalized evidence boxes. Blue boxes in the UI indicate unconfirmed AI extraction candidates.
They are not compliance findings. Only human-confirmed measurements are sent to the deterministic
checker. Compliance status remains controlled by reviewed YAML rules and Python checks.

## Professionally reviewed LDA residential rule packs

The MVP now includes activated, professionally reviewed rule packs for the selected ordinary residential categories:

- `data/rules/lda_5_marla_residential.yaml`
- `data/rules/lda_10_marla_residential.yaml`

Each active pack must contain `activation_allowed: true`. The loader rejects draft/unreviewed packs from deterministic checking. The supplied draft-amendment source is not activated. Parking remains project information but is not encoded as a mandatory numeric violation in these reviewed ordinary residential packs. For the 10-Marla pack, the reviewed side-space requirement is implemented as at least 5 ft on either the left or right side.

NaqshaCheck remains an advisory pre-submission checker. Rule applicability and current authority requirements should continue to be reviewed when source regulations change.
