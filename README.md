# EnvelopeAI – Document Intelligence Pipeline

> A Python-based API that validates document data, uses AI to resolve low-confidence fields, and routes decisions with a fully auditable pipeline.

A modular, configuration-driven FastAPI document intelligence pipeline that processes shipment execution envelopes through structured validation, LLM-based commodity code matching (using Gemini API), routing workflows, and an audit trail.

The system is configuration-driven, where validation thresholds and routing logic are dynamically controlled by the input envelope.

## Setup Instructions

1. Configure `.env` with your API key if you want real LLM responses (a mock is used automatically if none is provided). Create an `.env` file in the root containing:
   `GEMINI_API_KEY=your_key_here`
2. Install dependencies (requires Python 3.11+):
   ```bash
   pip install -r requirements.txt
   ```
3. Run the fast development server:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Run tests:
   ```bash
   pytest
   ```

## Project Structure

```text
app/
  models/        # Pydantic models
  services/      # business logic
  api/           # endpoints
tests/           # test cases
```

## Endpoints

- `POST /validate`: Validates envelope schemas, confidence metrics, datasets and produces decision routes and an audit trail.
- `POST /match`: Checks your commodity descriptors against an in-memory catalog using a Gemini-powered async LLM workflow.
- `POST /process`: Executes the full pipeline (validate → conditional matching → decision routing → audit logging).

## Pipeline Flow

1. Validate input data against business rules and confidence thresholds  
2. Route decision (auto_approve / hitl_review / rejected)  
3. Trigger LLM-based matching if required  
4. Enrich envelope with results  
5. Maintain complete audit trail  

## Tech Stack

- **Python 3.11+**
- **FastAPI** -> Asynchronous API delivery.
- **Pydantic v2** -> Deep JSON schema validation & configuration bounds.
- **HTTPX** -> Async LLM networking.
- **Gemini API** -> Generative matching.
- **Pytest** -> Component behavioral checks.

## Implemented Features
- All assignment requirements (validation, matching, audit, routing) have been implemented.
- Asynchronous HTTP calls dynamically adjusting prompts using `gemini-1.5-flash`.
- Global 422 standard exception handler preventing 500 runtime crashes.
- `AuditEntry` payload format matches the required specification format.
- Graceful fallback: If LLM fails, the system avoids crashes and routes to human-in-the-loop (hitl_review).

## Design Principles

- Configuration-driven logic (no hardcoded thresholds)
- Separation of concerns (models, services, API)
- Fault-tolerant AI integration
- Fully auditable processing pipeline

## What I Would Improve

- Add persistent storage for audit logs
- Improve LLM prompt tuning for better accuracy
- Introduce async task queue for scaling
