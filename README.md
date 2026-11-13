# Lab-to-Care Platform

A comprehensive platform that turns laboratory results into actionable health information.

## Quick Start

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload









## Physician-facing Doctor Assistant

The Doctor Assistant is integrated into the existing FastAPI backend. It consumes the
latest normalized OCR JSON for a `processed_file_id`, retrieves relevant passages from
both bundled laboratory-medicine knowledge bases, asks Gemini to produce a structured
physician-facing review, and stores the response in SQLite.

### API

- `POST /api/doctor-assistant/{processed_file_id}` — generate or refresh the interpretation.
- `GET /api/doctor-assistant/{processed_file_id}` — retrieve the saved interpretation.
- `POST /api/doctor-assistant/{processed_file_id}/regenerate` — explicit regeneration alias.
- `GET /api/doctor-assistant/{processed_file_id}/evidence` — inspect retrieved reference passages without calling Gemini.
- `GET /api/doctor-assistant/health` — not currently exposed; use `/health` for API health.

The `processed_file_id` is the page-level ID returned by the existing preprocessing route.
The assistant uses the latest OCR result associated with that page's parent document.
For multi-page reports, every page points to the same document-level normalized JSON.

### Install and run

From the `backend` directory:

```bash
python -m venv .venv
# Activate the virtual environment for your operating system
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Set a Gemini API key in the backend process environment:

```bash
export GEMINI_API_KEY="YOUR_KEY"
export GEMINI_MODEL="gemini-2.5-flash"  # optional
```

For backward compatibility, `~/API_key.txt` is also accepted. Environment variables are
recommended for deployment; do not commit API keys.

### Retrieval design

The current retrieval implementation is deliberately dependency-light: it lazily indexes
Markdown passages from both directories under `knowledgeBaseForLabAI`, applies lexical
BM25-style ranking, and returns excerpts with stable source IDs and repository-relative
paths. The evidence is attached to the generated response, and source IDs emitted by the
model are filtered against the retrieved set.

This is a transparent baseline retriever, not a validated clinical search engine. Before
clinical deployment, evaluate retrieval quality on a curated test set and consider adding
a persistent vector/hybrid index, clinician review, and an approved/current guideline
corpus. The two bundled textbooks are reference material, not a substitute for current
guidelines.

### Clinical safety and operational notes

The feature is clinician-facing decision support, not autonomous diagnosis or prescribing.
It does not calculate universal critical-value thresholds; it uses the report's own
reference ranges and asks the model to state uncertainty where ranges/context are absent.
All outputs require physician verification. The API currently mirrors the existing
project's access pattern and does not add authentication/authorization; do not expose it
to untrusted users until document ownership checks and authentication are implemented.
