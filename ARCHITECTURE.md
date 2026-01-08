# Project: IRIS Health FHIR Agentic Demo
## InterSystems IRIS for Health + CrewAI

---

## 0. Purpose of this File

This `ARCHITECTURE.md` file defines the **scope, architecture, execution model, data model,
and design principles** of this repository.

It guides any developer when modifying code so that the project remains:

- Simple
- Explainable
- Healthcare-realistic
- Demo- and workshop-oriented

This project is **not a production system**.  
It is a **reference demo** to explain *Agentic AI applied to healthcare workflows*
using **InterSystems IRIS for Health**.

---

## 1. Project Goal

The goal of this project is to demonstrate how **Agentic AI** can be applied to a real
healthcare scenario using **InterSystems IRIS for Health** as the clinical data platform.

The demo shows how an **abnormal laboratory result** (FHIR Observation):

- Triggers an automated workflow
- Collects patient clinical context
- Retrieves clinical evidence via RAG (Vector DB)
- Performs structured clinical reasoning
- Produces follow-up recommendations
- Persists explainable results in IRIS

Key message:

> This is not a chatbot.  
> This is event-driven, explainable, auditable Agentic AI for healthcare.

---

## 2. High-level Architecture

The architecture is intentionally **minimal and explicit**.

### Core components

- **InterSystems IRIS for Health**
  - Hosts a FHIR R4 repository that stores patient clinical context
  - Receives FHIR Observations that trigger an Interoperability Production flow
  - Orchestrates the entire workflow using Business Process (BPL)
  - Hosts the Vector Database for clinical guidelines
  - Persists AI results in SQL tables
  - Publishes FHIR DiagnosticReport results

- **CrewAI (Python library)**
  - Orchestrates agents
  - Performs reasoning and decision support
  - Returns structured JSON results

- **FastAPI REST Service**
  - Exposes CrewAI workflow via REST API
  - Called by IRIS Business Operation via HTTP
  - Returns JSON response to IRIS

---

## 3. Execution Model

CrewAI is used **strictly as a Python library**.

**Explicit rules:**
- Do NOT use `crewai init`
- Do NOT use `crewai run`
- Do NOT assume CrewAI project templates

### Primary execution mode: IRIS Interoperability Production

The workflow is triggered by **FHIR Observation** resources posted to IRIS and orchestrated by an **Interoperability Production**.

#### Architecture flow:

1. **FHIR Observation** posted to IRIS triggers Business Service
   → See example in [samples/fhir.http](./samples/fhir.http)

2. **Business Service** creates `ClinicalAgenticReq` message with observation reference

3. **Business Process** receives request and orchestrates three steps:
   - **Step 1**: Call Clinical Agentic Operation (HTTP POST to FastAPI)
     - FastAPI fetches FHIR Observation from IRIS
     - CrewAI executes agent workflow
     - Returns structured JSON response
   - **Step 2**: Persist response to SQL tables via Persistence Operation
   - **Step 3**: Publish FHIR DiagnosticReport asynchronously

4. **Production completes** with full audit trail in IRIS

#### Alternative modes (for development/testing):

**Mode 1: Direct CrewAI execution**
```bash
python clinical_ai/main.py --observation-id "Observation/12"
```

**Mode 2: CrewAI REST API only**
```bash
# Start the server
./run_api.sh
```
→ See sample requests in [samples/crewai.http](./samples/crewai.http)

### CrewAI workflow execution (via FastAPI)

When the Clinical Agentic Operation calls the FastAPI service:

1. Fetch the **FHIR Observation** from IRIS FHIR server
2. Parse observation data (test name, value, unit, status)
3. Execute the CrewAI workflow as a library
4. Return **structured JSON**
   → See example in [samples/output/crewai_api_reponse_sample.json](./samples/output/crewai_api_reponse_sample.json)

**Important notes:**
- CrewAI **does not own persistence**. IRIS is the **system of record**
- The FastAPI service is stateless and returns only JSON responses
- In the Interoperability Production, IRIS orchestrates persistence and FHIR publishing

---

## 4. Complete Workflow Diagram

### Production workflow (end-to-end)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. FHIR Observation Posted to IRIS                             │
│    └─> Triggers: clinicalai.bs.FHIRObservationIn               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Business Service → Business Process                          │
│    └─> Message: ClinicalAgenticReq(TriggerObservationRef)      │
│    └─> Target: clinicalai.bp.FollowUpAI                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Business Process Step 1: Agentic Evaluation                 │
│    └─> Call: clinicalai.bo.ClinicalAgenticOperation            │
│    └─> HTTP POST to FastAPI: /evaluate                         │
│         ┌──────────────────────────────────────────┐           │
│         │ FastAPI Service:                          │           │
│         │ - Fetch FHIR Observation from IRIS        │           │
│         │ - Execute CrewAI workflow                 │           │
│         │   • Context Agent                         │           │
│         │   • Guidelines Agent (RAG)                │           │
│         │   • Clinical Reasoning Agent              │           │
│         │ - Return JSON response                    │           │
│         └──────────────────────────────────────────┘           │
│    └─> Response: Ens.StringContainer(JSON)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Business Process Step 2: Persistence                        │
│    └─> Call: clinicalai.bo.ClinicalAiPersistence               │
│    └─> Persist to SQL tables:                                  │
│         • clinicalai_data.Cases                                │
│         • clinicalai_data.CaseRecommendations                  │
│         • clinicalai_data.CaseEvidences                        │
│    └─> Response: Ens.StringContainer(CaseId)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Business Process Step 3: FHIR Publishing (async)            │
│    └─> Call: clinicalai.bo.ClinicalReportPublisher             │
│    └─> Create FHIR DiagnosticReport:                           │
│         • Subject: Patient reference                           │
│         • Result: Trigger Observation                          │
│         • Conclusion: Risk level + reasoning                   │
│         • PresentedForm: Recommendations (Base64)              │
│         • Extensions: Case ID, confidence, model metadata      │
│    └─> POST to IRIS FHIR Server: /DiagnosticReport             │
│    └─> Response: Ens.StringContainer(ResourceId)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Workflow Complete                                            │
│    └─> Full audit trail in IRIS message log                    │
│    └─> Results queryable via SQL                               │
│    └─> DiagnosticReport available via FHIR API                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key integration points

1. **IRIS → FastAPI**: Business Operation calls Python service via HTTP
2. **FastAPI → IRIS**: Queries FHIR resources and Vector DB
3. **IRIS Persistence**: Stores structured results in SQL
4. **IRIS FHIR**: Publishes DiagnosticReport to FHIR repository

---

## 5. Repository Structure (Guidance)

The repository must remain **flat, readable, and demo-friendly**.

### Actual structure

```text
iris-health-fhir-agentic-demo/
├── README.md
├── ARCHITECTURE.md
├── docker-compose.yml
├── requirements.txt
│
├── iris/
│   ├── init/
│   │   └── schema.sql            # SQL schema for persistence tables
│   ├── src/
│   │   └── clinicalai/
│   │       ├── ClinicalEventOrchestration.cls  # Interoperability Production
│   │       ├── bs/
│   │       │   └── FHIRObservationIn.cls      # Business Service (inbound)
│   │       ├── bp/
│   │       │   └── FollowUpAI.cls             # Business Process (BPL orchestration)
│   │       ├── bo/
│   │       │   ├── ClinicalAgenticOperation.cls    # HTTP call to FastAPI
│   │       │   ├── ClinicalAiPersistence.cls       # SQL persistence
│   │       │   └── ClinicalReportPublisher.cls     # FHIR DiagnosticReport
│   │       └── msg/
│   │           ├── ClinicalAgenticReq.cls     # Request message
│   │           └── ClinicalReportReq.cls      # Report request message
│   └── vector/
│       └── guidelines/
│
├── clinical_ai/                  # Python package
│   ├── __init__.py
│   ├── main.py                   # CLI entrypoint (dev/testing)
│   ├── api.py                    # FastAPI REST service
│   ├── crew.py                   # CrewAI orchestration
│   ├── agents.py                 # Agent definitions
│   ├── tasks.py                  # Task definitions
│   ├── prompts.py                # Agent prompts
│   ├── schemas.py                # Pydantic output schemas
│   ├── iris_client.py            # IRIS SQL/FHIR client
│   ├── fhir_utils.py             # Shared FHIR utilities
│   └── tools/                    # Agent tools
│       ├── __init__.py
│       ├── fetch_patient_context.py
│       ├── search_clinical_guidelines.py
│       └── analyze_lab_trend.py
│
└── samples/
```

### Key structural principles

1. **IRIS Interoperability components**
   - Production class defines the complete workflow
   - Business Service receives FHIR Observation triggers
   - Business Process orchestrates the three-step workflow using BPL
   - Business Operations handle external calls, persistence, and FHIR publishing
   - Message classes define the contract between components

2. **clinical_ai is a Python package**
   - Contains `__init__.py` files
   - Uses relative imports (e.g., `from .crew import LabFollowupCrew`)
   - Can be run as script or imported as module

3. **Shared utilities avoid duplication**
   - `fhir_utils.py` contains shared FHIR operations
   - Used by both `main.py` and `api.py`
   - Single source of truth for common functionality

4. **Tools are in a subdirectory**
   - Agent tools are grouped under `clinical_ai/tools/`
   - Each tool is a separate, focused module

---

## 6. Minimal Persistence Model

This demo intentionally uses a **very small and clear SQL model**.

### Tables used (schema: `clinicalai_data`)

#### Table 1: `Cases`

One row per agent evaluation.

**Stores:**
- Patient reference
- Trigger Observation reference
- Risk level and confidence
- Short reasoning summary
- Optional raw JSON output

**Purpose:** "What happened and what was concluded."

---

#### Table 2: `CaseRecommendations`

One or more rows per case.

**Stores:**
- Action type (repeat_test, med_review, monitor, etc.)
- Human-readable action text
- Optional timeframe

**Purpose:** "What should be done next."

---

#### Table 3: `CaseEvidences`

One or more rows per case.

**Stores:**
- Guideline identifier
- Chunk identifier
- Similarity score
- Text excerpt

**Purpose:** "Why the agent made this recommendation."

---

#### Table 4: `GuidelineChunks`

Stores the **textual knowledge base** used for RAG.

**Stores:**
- Guideline ID
- Section
- Chunk text

**Note:** Embeddings are handled by IRIS Vector Search. This table exists for **traceability and explainability**, not vector storage.

---

## 7. Agents Overview

### 1. Context Agent
Retrieves patient context from IRIS FHIR repository.

**Examples:**
- Previous creatinine values
- CKD diagnosis
- Active medications

### 2. Clinical Guidelines Agent (RAG)
Queries IRIS Vector DB for relevant clinical evidence.

**Capabilities:**
- Retrieves relevant guideline chunks
- Returns chunk IDs and similarity scores
- Provides evidence-based recommendations

### 3. Clinical Reasoning Agent
Combines context and evidence to produce recommendations.

**Capabilities:**
- Identifies trends and risk factors
- Produces follow-up recommendations
- Provides structured reasoning

**Important constraints:**
- Does NOT diagnose
- Does NOT prescribe
- Provides **decision support only**

---

## 8. Explainability Principle

Explainability is a **core requirement**.

For every evaluation, the system must be able to answer:

- What triggered the evaluation?
- What recommendation was produced?
- Which guideline text was used?
- Why this recommendation was suggested?

The SQL tables are designed to make this **explicit and queryable**.

---

## 9. Coding Principles

When generating or modifying code:

- Prefer clarity over cleverness
- Keep files small and focused
- Use explicit domain names
- Avoid hidden side effects
- Avoid excessive abstractions

This code must be explainable **live during a demo**.

### Code organization rules

1. **No duplicate code**
   - Shared functions go in utility modules (e.g., `fhir_utils.py`)
   - Both `main.py` and `api.py` import from shared utilities

2. **IRIS owns orchestration, Python owns AI**
   - IRIS Production orchestrates the complete workflow
   - Business Process (BPL) defines the execution sequence
   - Python FastAPI service is stateless and focused on AI execution
   - IRIS handles all persistence and FHIR operations

3. **Pre-workflow vs. agent operations**
   - Pre-workflow: Fetch trigger observation → `fhir_utils.py`
   - Agent operations: Clinical context, RAG, reasoning → agent tools
   - Don't confuse orchestration with agent capabilities

4. **API wrappers are thin**
   - API-specific logic only converts exceptions to HTTP responses
   - Business logic stays in shared utilities or crew/agents

---

## 10. API Design (Production Component)

The FastAPI service (`api.py`) is the **production interface** called by IRIS Business Operations.

### API Endpoints

#### `GET /` - Health check
Returns service status and version.

#### `GET /health` - Detailed health
Returns IRIS connection configuration (does not test connectivity).

#### `POST /evaluate` - Execute workflow
Accepts:
```json
{
  "TriggerObservationRef": "Observation/12"
}
```

Returns: Same structured JSON as CLI mode.

### API Design Principles

1. **Stateless service**
   - API only executes AI workflow and returns JSON
   - No persistence or FHIR publishing (handled by IRIS)
   - Called by IRIS Business Operation via HTTP

2. **Error handling**
   - 404: Observation not found in FHIR server
   - 502: FHIR server communication error
   - 503: Cannot connect to FHIR server
   - 500: Workflow execution error

3. **No authentication required (demo)**
   - Production systems would add auth/authorization
   - Out of scope for this demo

4. **Synchronous execution**
   - Request waits for full workflow completion
   - No async/background processing
   - Simple, explainable behavior
   - IRIS Business Process handles timeout (500 seconds)

---

## 11. AI Safety and Healthcare Constraints

- Do not generate medical diagnoses
- Frame outputs as recommendations
- Use conservative clinical language
- Assume demo data only
- Do not store real patient data

---

## 12. Explicitly Out of Scope

- Production-grade security
- Autonomous clinical decisions
- Full UI applications
- Real patient deployment
- Complex DevOps setups

---

## 13. Success Criteria

This project is successful if:

- Agentic AI concepts are clearly understood
- IRIS for Health leveraged as the platform 
- Explainability is demonstrated via SQL queries
- The demo can be run in under 15 minutes
- The flow is easy to explain end-to-end

---

## 14. Final Guiding Principle

> If a feature makes the demo harder to explain, it does not belong here.

Keep it simple.  
Keep it explainable.  
Keep it healthcare-realistic.
