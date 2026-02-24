# OrthoAssist — Fully Agentic Backend Plan
### Stack: FastAPI + LangGraph + LangChain + MCP (Python SDK) + LangSmith

---

## Table of Contents
1. [Why the Current System is NOT Agentic](#1-why-the-current-system-is-not-agentic)
2. [What True Agentic + MCP Means](#2-what-true-agentic--mcp-means)
3. [New System Architecture Overview](#3-new-system-architecture-overview)
4. [Agent & Tool Breakdown (Complete Tables)](#4-agent--tool-breakdown-complete-tables)
5. [Clean Backend Directory Structure](#5-clean-backend-directory-structure)
6. [File-by-File Responsibilities](#6-file-by-file-responsibilities)
7. [LangGraph State & Graph Design](#7-langgraph-state--graph-design)
8. [MCP Server Design](#8-mcp-server-design)
9. [LangSmith Integration](#9-langsmith-integration)
10. [Phase-by-Phase Build Plan](#10-phase-by-phase-build-plan)
11. [Full Dependency List](#11-full-dependency-list)
12. [Environment Configuration](#12-environment-configuration)
13. [Behavior Comparison: Old vs New](#13-behavior-comparison-old-vs-new)

---

## 1. Why the Current System is NOT Agentic

The current `Agentic-AI/` directory has the right domain logic but the wrong architecture for true agentic behavior. Here's the exact problem list:

| Problem | Current Behavior | What Agentic Should Be |
|---------|-----------------|----------------------|
| **Predefined pipeline** | Router → Hand/Leg → Diagnosis → Triage → Hospital → PDF, every time, always | LLM decides which tools to call, in what order, based on context |
| **Fake MCP server** | `main.py` wraps HTTP API with stdio loop — not a real MCP server | Proper `@mcp.tool()` registered tools callable from Claude Desktop/Cursor |
| **Passive LLM** | Groq is only called to format text output | LLM reads state, chooses next tool, re-evaluates after every tool result |
| **No state machine** | `OrchestratorService` uses hardcoded `StepName` enums | LangGraph `StateGraph` with dynamic conditional edges |
| **Class wrappers ≠ agents** | `HandAgent`, `TriageAgent` are functions disguised as classes | Tools are pure async functions; agents are LLM nodes in LangGraph |
| **No observability** | Logs only, no trace of LLM decisions | LangSmith traces every node, tool call, token, latency |
| **No memory** | Each request is stateless | LangGraph `MemorySaver` checkpointing per session |

---

## 2. What True Agentic + MCP Means

### Agentic = LLM controls the execution flow

```
Old: Code decides what runs next
New: LLM decides what runs next
```

The LLM reads the current state (what it knows so far), picks a tool, gets back structured data, then re-evaluates. This loop continues until the LLM determines it has enough to answer. No hardcoded order.

### MCP = Tools callable from ANY MCP client

```
Old: Tools are private Python functions nobody else can call
New: Tools are registered on an MCP server — Claude Desktop, Cursor, any MCP client can call them
```

The MCP server exposes every tool as a named endpoint. LangGraph also uses the same tools internally. One tool definition, two consumers.

### LangSmith = Full observability over agent reasoning

```
Old: You only see logs — you have no idea why the LLM chose a particular response
New: LangSmith shows every step: token input/output, tool calls, latency, cost per trace
```

---

## 3. New System Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                               │
│     Next.js Frontend    │    Claude Desktop    │    Cursor IDE      │
└──────────────┬──────────┴──────────┬───────────┴──────────┬────────┘
               │ HTTP/REST           │ MCP Protocol         │ MCP
               ▼                     ▼                       ▼
┌──────────────────────┐   ┌─────────────────────────────────────────┐
│   FastAPI Server     │   │          MCP Server (stdio/SSE)         │
│   /api/analyze       │   │   Exposes 22 tools via @mcp.tool()      │
│   /api/chat          │   │   Namespaced: vision.*, clinical.*      │
│   /api/reports       │   └────────────────┬────────────────────────┘
└──────────┬───────────┘                     │
           │ both call                        │ both use same
           ▼                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    LangGraph StateGraph                          │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  Supervisor │───▶│ Tool Executor│───▶│ Response Builder │   │
│  │   (brain)   │◀───│  (ToolNode)  │    │  (final answer) │   │
│  └─────────────┘    └──────────────┘    └──────────────────┘   │
│         │                                                        │
│  routes to sub-agents:                                           │
│  vision_agent │ clinical_agent │ knowledge_agent                 │
│  report_agent │ hospital_agent                                   │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Tool Implementations                          │
│  YOLO Models │ Groq LLM │ ReportLab PDF │ Storage │ Cloudinary  │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                  LangSmith Observability                         │
│         Traces │ Evaluations │ Dashboards │ Latency Metrics      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Agent & Tool Breakdown (Complete Tables)

### Core Concept

| Term | Definition |
|------|-----------|
| **Agent** | An LLM node in LangGraph with a specific role, persona, and a curated set of tools bound via `bind_tools()` |
| **Tool** | An atomic `@tool` decorated async function that does ONE thing, returns structured data, and is also registered on the MCP server |
| **MCP Server** | Exposes all tools as a flat callable list accessible to any MCP client |

---

### Agent 1 — Supervisor Agent

| Property | Value |
|----------|-------|
| **LangGraph Node** | `supervisor` |
| **Role** | Central brain — reads full conversation state and decides which sub-agent to delegate to, or whether to respond directly |
| **LLM** | `llama-3.3-70b-versatile` (strongest reasoning, best for orchestration) |
| **Tools** | Routing/handoff tools only (see below) |

**Supervisor Routing Tools:**

| Tool Name | Input | Output |
|-----------|-------|--------|
| `route_to_vision_agent` | `image_base64: str, reason: str` | `{routed: bool, agent: "vision"}` |
| `route_to_clinical_agent` | `detections: list, symptoms: str` | `{routed: bool, agent: "clinical"}` |
| `route_to_knowledge_agent` | `query: str` | `{routed: bool, agent: "knowledge"}` |
| `route_to_report_agent` | `full_context: dict` | `{routed: bool, agent: "report"}` |
| `route_to_hospital_agent` | `triage_level: str, location: str` | `{routed: bool, agent: "hospital"}` |

**MCP Exposed:** No — supervisor is internal LangGraph logic only.

---

### Agent 2 — Vision Agent

| Property | Value |
|----------|-------|
| **LangGraph Node** | `vision_agent` |
| **Role** | Owns all computer vision — body part classification, fracture detection, image annotation |
| **LLM** | `llama-3.1-8b-instant` (fast; reasoning here is minimal) |
| **Source Code (migrate from)** | `agents/router.py`, `agents/hand.py`, `agents/leg.py`, `services/body_part_detector.py` |

**Vision Agent Tools:**

| Tool Name | Input | Output | Source File |
|-----------|-------|--------|-------------|
| `detect_body_part` | `image_base64: str` | `{body_part: str, confidence: float, rationale: str}` | `agents/router.py` |
| `detect_hand_fracture` | `image_base64: str, threshold: float` | `{detections: list, confidence_map: dict, raw_boxes: list}` | `agents/hand.py` |
| `detect_leg_fracture` | `image_base64: str, threshold: float` | `{detections: list, confidence_map: dict, raw_boxes: list}` | `agents/leg.py` |
| `annotate_xray_image` | `image_base64: str, detections: list` | `{annotated_image_base64: str}` | `agents/hand.py` / `agents/leg.py` |
| `upload_image_to_storage` | `image_base64: str, filename: str, patient_id: str` | `{image_url: str, public_id: str, storage_path: str}` | `services/cloudinary_service.py` |

**MCP Exposed:** All 5 tools under namespace `vision.*`

---

### Agent 3 — Clinical Agent

| Property | Value |
|----------|-------|
| **LangGraph Node** | `clinical_agent` |
| **Role** | Medical reasoning — converts raw detections into clinical judgements (diagnosis + triage + multi-study trends) |
| **LLM** | `llama-3.3-70b-versatile` (deep medical reasoning required) |
| **Source Code (migrate from)** | `agents/diagnosis.py`, `agents/triage.py`, `agents/clinical_analysis.py` |

**Clinical Agent Tools:**

| Tool Name | Input | Output | Source File |
|-----------|-------|--------|-------------|
| `generate_diagnosis` | `detections: list, symptoms: str, body_part: str` | `{finding: str, severity: str, patient_summary: str, confidence: float}` | `agents/diagnosis.py` |
| `assess_triage` | `diagnosis: dict, detections: list, patient_vitals: str` | `{level: RED/AMBER/GREEN, rationale: str, urgency_score: float, recommended_timeframe: str}` | `agents/triage.py` |
| `analyze_patient_symptoms` | `symptoms: str, body_part: str, age: int` | `{risk_factors: list, possible_conditions: list, red_flags: list}` | `services/mcp_tools.py` |
| `analyze_multiple_studies` | `studies: list, patient_id: str` | `{longitudinal_analysis: str, trend: str, deterioration_flag: bool, recommendations: list}` | `agents/clinical_analysis.py` |
| `get_patient_history` | `patient_id: str` | `{past_studies: list, study_count: int, last_visit: str}` | `services/storage.py` |

**MCP Exposed:** All 5 tools under namespace `clinical.*`

---

### Agent 4 — Knowledge Agent

| Property | Value |
|----------|-------|
| **LangGraph Node** | `knowledge_agent` |
| **Role** | Pure medical knowledge — answers text-only questions without needing an image |
| **LLM** | `llama-3.1-8b-instant` (fast; knowledge retrieval is LLM-native) |
| **Source Code (migrate from)** | `services/mcp_tools.py` (all 5 existing knowledge tools) |

**Knowledge Agent Tools:**

| Tool Name | Input | Output | Source File |
|-----------|-------|--------|-------------|
| `lookup_orthopedic_condition` | `condition_name: str` | `{description: str, symptoms: list, treatment_options: list, prognosis: str}` | `mcp_tools.py → condition_lookup_tool` |
| `get_treatment_recommendations` | `diagnosis: str, triage_level: str, patient_age: int` | `{immediate_steps: list, long_term: list, medications: list, restrictions: list}` | `mcp_tools.py → treatment_recommendations_tool` |
| `get_anatomical_reference` | `body_part: str, region: str` | `{anatomy_info: str, common_injuries: list, xray_landmarks: list}` | `mcp_tools.py → anatomical_reference_tool` |
| `classify_fracture_type` | `description: str, location: str, mechanism: str` | `{fracture_type: str, AO_classification: str, severity: str, notes: str}` | `mcp_tools.py → fracture_classifier_tool` |
| `get_orthopedic_knowledge` | `query: str` | `{answer: str, references: list, confidence: float}` | `mcp_tools.py → orthopedic_knowledge_tool` |

**MCP Exposed:** All 5 tools under namespace `knowledge.*`

---

### Agent 5 — Report Agent

| Property | Value |
|----------|-------|
| **LangGraph Node** | `report_agent` |
| **Role** | Document generation — creates patient-friendly and clinician PDFs, manages report storage and retrieval |
| **LLM** | `llama-3.1-8b-instant` (just formatting logic, no deep reasoning) |
| **Source Code (migrate from)** | `agents/pdf_report.py`, `agents/report.py`, `services/storage.py` |

**Report Agent Tools:**

| Tool Name | Input | Output | Source File |
|-----------|-------|--------|-------------|
| `generate_patient_pdf` | `diagnosis: dict, triage: dict, patient_info: dict, recommendations: list` | `{pdf_base64: str, pdf_url: str, report_id: str}` | `agents/pdf_report.py` |
| `generate_clinician_pdf` | `detections: list, triage: dict, images: dict, metadata: dict` | `{pdf_base64: str, pdf_url: str, report_id: str}` | `agents/report.py` |
| `save_report_to_storage` | `report_data: dict, patient_id: str, report_type: str` | `{report_id: str, saved_path: str, timestamp: str}` | `services/storage.py` |
| `retrieve_report` | `report_id: str` | `{report_data: dict, pdf_url: str, created_at: str}` | `services/storage.py` |

**MCP Exposed:** All 4 tools under namespace `report.*`

---

### Agent 6 — Hospital Agent

| Property | Value |
|----------|-------|
| **LangGraph Node** | `hospital_agent` |
| **Role** | Geolocation and referral — finds appropriate hospitals based on urgency level and patient location |
| **LLM** | `llama-3.1-8b-instant` (light — ranks and narrates results) |
| **Source Code (migrate from)** | `agents/hospitals.py`, `services/mcp_tools.py → hospital_finder_tool` |

**Hospital Agent Tools:**

| Tool Name | Input | Output | Source File |
|-----------|-------|--------|-------------|
| `find_nearby_hospitals` | `location: str, urgency: str, specialty: str` | `{hospitals: list, ranked_by_relevance: bool, count: int}` | `agents/hospitals.py` |
| `get_hospital_details` | `hospital_id: str` | `{name: str, address: str, services: list, phone: str, rating: float, er_available: bool}` | `agents/hospitals.py` |
| `get_emergency_contacts` | `location: str` | `{emergency_number: str, ambulance: str, poison_control: str}` | new — static lookup |

**MCP Exposed:** All 3 tools under namespace `hospital.*`

---

### Master Summary Table

| Agent | Node Name | LLM | Tools Count | MCP Namespace | Primary Responsibility |
|-------|-----------|-----|-------------|---------------|----------------------|
| Supervisor | `supervisor` | llama-3.3-70b | 5 (routing) | Not exposed | Decides execution flow |
| Vision | `vision_agent` | llama-3.1-8b | 5 | `vision.*` | Detection + annotation |
| Clinical | `clinical_agent` | llama-3.3-70b | 5 | `clinical.*` | Diagnosis + triage |
| Knowledge | `knowledge_agent` | llama-3.1-8b | 5 | `knowledge.*` | Text medical Q&A |
| Report | `report_agent` | llama-3.1-8b | 4 | `report.*` | PDF generation |
| Hospital | `hospital_agent` | llama-3.1-8b | 3 | `hospital.*` | Hospital referrals |
| **TOTAL** | | | **27 tools** | **22 on MCP** | |

---

## 5. Clean Backend Directory Structure

```
ortho-backend/
│
├── main.py                          # FastAPI app entry point
├── pyproject.toml                   # Dependencies (uv/poetry)
├── .env                             # All secrets/config
├── .env.example                     # Template for secrets
│
├── core/
│   ├── __init__.py
│   ├── config.py                    # Pydantic Settings (env vars, model paths, thresholds)
│   ├── logging.py                   # Loguru + LangSmith log bridge
│   └── exceptions.py                # Custom exception hierarchy
│
├── graph/
│   ├── __init__.py
│   ├── state.py                     # AgentState TypedDict — single source of truth
│   ├── graph.py                     # StateGraph definition (nodes + edges)
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── supervisor.py            # Supervisor node — LLM picks next action
│   │   ├── tool_executor.py         # ToolNode — runs whatever tool supervisor picked
│   │   ├── response_builder.py      # Formats final answer to user
│   │   └── error_handler.py         # Retry logic and graceful degradation
│   └── checkpointer.py              # LangGraph MemorySaver for session persistence
│
├── agents/
│   ├── __init__.py
│   ├── vision.py                    # Vision agent — LLM + vision tools bound
│   ├── clinical.py                  # Clinical agent — LLM + clinical tools bound
│   ├── knowledge.py                 # Knowledge agent — LLM + knowledge tools bound
│   ├── report.py                    # Report agent — LLM + report tools bound
│   └── hospital.py                  # Hospital agent — LLM + hospital tools bound
│
├── tools/
│   ├── __init__.py
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── body_part_detector.py    # detect_body_part tool
│   │   ├── hand_detector.py         # detect_hand_fracture tool
│   │   ├── leg_detector.py          # detect_leg_fracture tool
│   │   ├── annotator.py             # annotate_xray_image tool
│   │   └── uploader.py              # upload_image_to_storage tool
│   ├── clinical/
│   │   ├── __init__.py
│   │   ├── diagnosis.py             # generate_diagnosis tool
│   │   ├── triage.py                # assess_triage tool
│   │   ├── symptoms.py              # analyze_patient_symptoms tool
│   │   ├── multi_study.py           # analyze_multiple_studies tool
│   │   └── history.py               # get_patient_history tool
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── condition_lookup.py      # lookup_orthopedic_condition tool
│   │   ├── treatment.py             # get_treatment_recommendations tool
│   │   ├── anatomy.py               # get_anatomical_reference tool
│   │   ├── fracture_classifier.py   # classify_fracture_type tool
│   │   └── ortho_knowledge.py       # get_orthopedic_knowledge tool
│   ├── report/
│   │   ├── __init__.py
│   │   ├── patient_pdf.py           # generate_patient_pdf tool
│   │   ├── clinician_pdf.py         # generate_clinician_pdf tool
│   │   ├── save_report.py           # save_report_to_storage tool
│   │   └── retrieve_report.py       # retrieve_report tool
│   └── hospital/
│       ├── __init__.py
│       ├── finder.py                # find_nearby_hospitals tool
│       ├── details.py               # get_hospital_details tool
│       └── emergency.py             # get_emergency_contacts tool
│
├── mcp/
│   ├── __init__.py
│   ├── server.py                    # MCP server — registers all 22 tools via @mcp.tool()
│   └── registry.py                  # Central tool registry (single import point)
│
├── api/
│   ├── __init__.py
│   ├── router.py                    # All FastAPI route registrations
│   ├── middleware.py                # CORS, security, rate limiting
│   ├── endpoints/
│   │   ├── __init__.py
│   │   ├── analyze.py               # POST /api/analyze → calls LangGraph agent
│   │   ├── chat.py                  # POST /api/chat → calls LangGraph agent
│   │   ├── reports.py               # GET/POST /api/reports
│   │   ├── health.py                # GET /api/health
│   │   └── metrics.py               # GET /api/metrics
│   └── schemas/
│       ├── __init__.py
│       ├── requests.py              # Pydantic request models
│       └── responses.py             # Pydantic response models
│
├── services/
│   ├── __init__.py
│   ├── groq_llm.py                  # ChatGroq client factory (replaces GroqService)
│   ├── storage.py                   # File storage (local + Cloudinary)
│   └── session.py                   # Session management (Redis-backed or in-memory)
│
├── models/
│   ├── hand_yolo.pt                 # YOLO model — hand fracture detection
│   └── leg_yolo.pt                  # YOLO model — leg fracture detection
│
└── storage/
    ├── raw/                         # Original uploaded images
    ├── annotated/                   # Annotated X-ray images
    └── reports/                     # Generated PDF reports
```

---

## 6. File-by-File Responsibilities

### `core/config.py`
- Pydantic `BaseSettings` loads all env vars
- Model paths, YOLO thresholds, Groq API key, LangSmith key, Cloudinary URL
- Single `config` singleton imported everywhere

### `graph/state.py`
The `AgentState` TypedDict is the **single source of truth** for everything the agent knows at any point:

```python
class AgentState(TypedDict):
    # Input
    session_id: str
    user_message: str
    image_data: Optional[str]          # base64
    symptoms: Optional[str]
    patient_id: Optional[str]
    location: Optional[str]

    # Discovered during execution
    body_part: Optional[str]
    detections: Optional[list]
    diagnosis: Optional[dict]
    triage_result: Optional[dict]
    hospitals: Optional[list]
    report_url: Optional[str]

    # LangGraph internals
    messages: Annotated[list[BaseMessage], add_messages]  # full LLM chain
    tool_calls_made: list[str]         # prevents infinite loops
    current_agent: Optional[str]       # which sub-agent is active
    iteration_count: int               # safety counter
    error: Optional[str]
    final_response: Optional[str]
```

### `graph/graph.py`
Defines the `StateGraph` with these nodes and edges:

```
Nodes:
  supervisor        → LLM reads state, outputs tool call or FINISH
  tool_executor     → LangGraph ToolNode — runs the tool, returns ToolMessage
  response_builder  → Formats final user-facing answer
  error_handler     → Handles exceptions, decides retry or graceful fail

Edges:
  START → supervisor
  supervisor → tool_executor      (when supervisor outputs tool_calls)
  supervisor → response_builder   (when supervisor outputs FINISH)
  supervisor → error_handler      (on exception)
  tool_executor → supervisor      (always loops back)
  error_handler → supervisor      (retry if iteration_count < max)
  error_handler → response_builder (give up after max retries)
  response_builder → END
```

### `tools/*/` directory
Each file contains exactly ONE `@tool` decorated async function. This makes them:
- Importable as LangChain tools into agents
- Registrable as `@mcp.tool()` on the MCP server
- Testable in isolation without LangGraph

### `mcp/server.py`
Uses the official `mcp` Python SDK. Starts as stdio transport (compatible with Claude Desktop, Cursor):

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

mcp = Server("orthoassist")

# Register every tool
@mcp.tool()
async def detect_body_part(image_base64: str) -> dict: ...

@mcp.tool()
async def generate_diagnosis(detections: list, symptoms: str) -> dict: ...
# ... all 22 tools
```

### `api/endpoints/analyze.py` and `api/endpoints/chat.py`
Both call the same LangGraph agent — different initial state setup:

```python
# analyze.py
result = await run_agent({
    "user_message": request.symptoms or "Analyze this X-ray",
    "image_data": request.image_data,
    "patient_id": request.user_id,
    "session_id": str(uuid4())
})

# chat.py
result = await run_agent({
    "user_message": request.message,
    "image_data": request.attachment,
    "session_id": request.session_id  # preserves conversation history
})
```

---

## 7. LangGraph State & Graph Design

### The Supervisor Prompt (Critical)

The supervisor is not just an orchestrator — it is a **medical reasoning engine**. Its system prompt defines when to call what:

```
You are an orthopedic AI clinical assistant. You have access to specialist sub-agents.

Rules:
1. If an image is provided: ALWAYS start with detect_body_part. Never skip this.
2. Once body part is known, route to detect_hand_fracture OR detect_leg_fracture accordingly.
3. If detection confidence < 0.4: ask user to clarify or provide a better image before proceeding.
4. generate_diagnosis requires completed detections. Never call it without detections.
5. assess_triage requires a completed diagnosis. Never call it without one.
6. If triage = RED or AMBER: find_nearby_hospitals is MANDATORY.
7. If triage = GREEN: find_nearby_hospitals is OPTIONAL — only if user asked about visiting a doctor.
8. generate_patient_pdf or generate_clinician_pdf only if user explicitly requested a report.
9. If no image: skip all vision tools. Answer from knowledge_agent tools only.
10. Never call the same tool twice with the same arguments.
```

### Conditional Edge Logic

```python
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    
    if state["iteration_count"] > 10:
        return "error_handler"
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_executor"
    
    if state.get("error"):
        return "error_handler"
    
    return "response_builder"
```

---

## 8. MCP Server Design

### Transport Modes

| Mode | Use Case | How to Start |
|------|----------|-------------|
| **stdio** | Claude Desktop, Cursor, local MCP clients | `python -m mcp.server.stdio` |
| **SSE (HTTP)** | Remote MCP clients, Next.js frontend via `use-mcp` | `uvicorn mcp.server:app --port 8001` |

### Tool Naming Convention

All MCP tools follow the pattern `{namespace}_{action}`:

```
vision_detect_body_part
vision_detect_hand_fracture
vision_detect_leg_fracture
vision_annotate_xray_image
vision_upload_image_to_storage

clinical_generate_diagnosis
clinical_assess_triage
clinical_analyze_patient_symptoms
clinical_analyze_multiple_studies
clinical_get_patient_history

knowledge_lookup_orthopedic_condition
knowledge_get_treatment_recommendations
knowledge_get_anatomical_reference
knowledge_classify_fracture_type
knowledge_get_orthopedic_knowledge

report_generate_patient_pdf
report_generate_clinician_pdf
report_save_report_to_storage
report_retrieve_report

hospital_find_nearby_hospitals
hospital_get_hospital_details
hospital_get_emergency_contacts
```

### Claude Desktop Configuration (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "orthoassist": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "/path/to/ortho-backend",
      "env": {
        "OPENAI_API_KEY": "your_key",
        "LANGSMITH_API_KEY": "your_key"
      }
    }
  }
}
```

---

## 9. LangSmith Integration

### What LangSmith Provides

| Feature | What You See |
|---------|-------------|
| **Trace viewer** | Every LLM call, every tool call, full input/output per step |
| **Token usage** | Input tokens, output tokens, cost per trace |
| **Latency breakdown** | Which node is slowest (vision detection? LLM reasoning?) |
| **Error tracking** | Which tool fails most, what the error was |
| **Evaluations** | Run automated evals on diagnosis quality, triage accuracy |
| **Dataset creation** | Save good traces as golden examples for fine-tuning |

### Setup (3 lines in `.env`)

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=orthoassist-prod
```

LangSmith auto-instruments LangGraph — no code changes needed. Every graph run creates a trace with full node-level visibility.

### Recommended Projects Setup

| LangSmith Project | Purpose |
|------------------|---------|
| `orthoassist-dev` | Development and debugging traces |
| `orthoassist-prod` | Production monitoring |
| `orthoassist-evals` | Automated evaluation runs |

---

## 10. Phase-by-Phase Build Plan

### Phase 1 — Foundation (Day 1)
- [ ] Create `ortho-backend/` directory with full folder structure above
- [ ] Set up `pyproject.toml` with all dependencies
- [ ] Write `core/config.py` (Pydantic Settings, all env vars)
- [ ] Write `graph/state.py` (AgentState TypedDict)
- [ ] Set up `.env` with Groq API key, LangSmith key
- [ ] Verify LangSmith connection: run a hello-world LangGraph trace and see it in dashboard

### Phase 2 — Tool Layer (Day 2-3)
- [ ] Port `detect_body_part` from `agents/router.py` → `tools/vision/body_part_detector.py`
- [ ] Port `detect_hand_fracture` from `agents/hand.py` → `tools/vision/hand_detector.py`
- [ ] Port `detect_leg_fracture` from `agents/leg.py` → `tools/vision/leg_detector.py`
- [ ] Port `generate_diagnosis` from `agents/diagnosis.py` → `tools/clinical/diagnosis.py`
- [ ] Port `assess_triage` from `agents/triage.py` → `tools/clinical/triage.py`
- [ ] Port all 5 knowledge tools from `services/mcp_tools.py` → `tools/knowledge/`
- [ ] Port `generate_patient_pdf` from `agents/pdf_report.py` → `tools/report/patient_pdf.py`
- [ ] Port `generate_clinician_pdf` from `agents/report.py` → `tools/report/clinician_pdf.py`
- [ ] Port hospital tools from `agents/hospitals.py` → `tools/hospital/`
- [ ] **Test each tool in isolation** — pure function call, no LangGraph yet

### Phase 3 — LangGraph Graph (Day 4-5)
- [ ] Write `graph/nodes/supervisor.py` — bind Groq LLM with all tools, write system prompt
- [ ] Write `graph/nodes/tool_executor.py` — wrap LangGraph `ToolNode`
- [ ] Write `graph/nodes/response_builder.py` — format final answer
- [ ] Write `graph/nodes/error_handler.py` — retry + graceful degradation
- [ ] Write `graph/graph.py` — wire StateGraph with conditional edges
- [ ] Write `graph/checkpointer.py` — MemorySaver for session persistence
- [ ] **Test full graph**: upload sample X-ray → should auto-route through vision → clinical → response

### Phase 4 — Sub-Agents (Day 6)
- [ ] Write `agents/vision.py` — LLM + vision tools bound
- [ ] Write `agents/clinical.py` — LLM + clinical tools bound
- [ ] Write `agents/knowledge.py` — LLM + knowledge tools bound
- [ ] Write `agents/report.py` — LLM + report tools bound
- [ ] Write `agents/hospital.py` — LLM + hospital tools bound
- [ ] **Test multi-turn conversation**: verify session memory works across messages

### Phase 5 — MCP Server (Day 7)
- [ ] Write `mcp/registry.py` — centralized import of all 22 tool functions
- [ ] Write `mcp/server.py` — register all tools with `@mcp.tool()` decorator
- [ ] Run `mcp dev mcp/server.py` — inspect via MCP inspector UI
- [ ] Connect to Claude Desktop via `claude_desktop_config.json`
- [ ] **Test**: ask Claude Desktop to analyze an X-ray using the registered tools

### Phase 6 — FastAPI Layer (Day 8)
- [ ] Write `api/endpoints/analyze.py` → calls `run_agent()` with image context
- [ ] Write `api/endpoints/chat.py` → calls `run_agent()` with session context
- [ ] Write `api/endpoints/reports.py`, `health.py`, `metrics.py`
- [ ] Write `api/middleware.py` — CORS, security headers
- [ ] Write `main.py` — mounts all routers, starts server
- [ ] **Test all endpoints** via Swagger UI (`/docs`)

### Phase 7 — LangSmith Evals (Day 9)
- [ ] Create evaluation dataset: 20 sample X-rays with known diagnoses
- [ ] Write evaluator: does the agent triage correctly?
- [ ] Run baseline eval, capture scores
- [ ] Set up LangSmith alerts for latency > 10s or error rate > 5%

### Phase 8 — Connect to Next.js (Day 10)
- [ ] Update Next.js API routes to point to new `ortho-backend` server
- [ ] Test end-to-end: upload X-ray from Next.js → LangGraph agent → response back

---

## 11. Full Dependency List

```toml
[project]
name = "ortho-backend"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # FastAPI
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "python-multipart>=0.0.12",

    # LangChain + LangGraph
    "langchain>=0.3.0",
    "langchain-core>=0.3.0",
    "langchain-groq>=0.2.0",
    "langchain-community>=0.3.0",
    "langgraph>=0.2.0",
    "langgraph-checkpoint>=2.0.0",

    # LangSmith (observability)
    "langsmith>=0.2.0",

    # MCP (official Python SDK)
    "mcp>=1.0.0",

    # Groq SDK
    "groq>=0.11.0",

    # Computer Vision
    "torch>=2.1.0",
    "torchvision>=0.16.0",
    "ultralytics>=8.3.0",
    "Pillow>=10.0.0",
    "numpy>=1.26.0",
    "opencv-python-headless>=4.9.0",

    # PDF Generation
    "reportlab>=4.2.0",

    # Storage
    "cloudinary>=1.41.0",
    "aiofiles>=24.1.0",

    # Config
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "python-dotenv>=1.0.0",

    # Logging
    "loguru>=0.7.0",

    # Utilities
    "httpx>=0.27.0",
    "python-jose>=3.3.0",
    "passlib>=1.7.4",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]
```

---

## 12. Environment Configuration

```env
# ── Server ──────────────────────────────
HOST=0.0.0.0
PORT=8000
DEBUG=false

# ── OpenAI (LLM) ──────────────────────────
OPENAI_API_KEY=sk-proj-...

# ── LangSmith (Observability) ────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=orthoassist-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# ── Models ──────────────────────────────
HAND_MODEL_PATH=models/hand_yolo.pt
LEG_MODEL_PATH=models/leg_yolo.pt
SUPERVISOR_LLM=gpt-4o
FAST_LLM=gpt-4o-mini

# ── Detection Thresholds ─────────────────
ROUTER_THRESHOLD=0.70
DETECTOR_SCORE_MIN=0.35
NMS_IOU=0.50
TRIAGE_RED_THRESHOLD=0.80
TRIAGE_AMBER_THRESHOLD=0.60

# ── Storage ──────────────────────────────
STORAGE_TYPE=local
STORAGE_PATH=./storage
CLOUDINARY_URL=cloudinary://...

# ── Security ─────────────────────────────
SECRET_KEY=your_jwt_secret_here
PHI_REDACTION_ENABLED=true
MEDICAL_DISCLAIMER_ENABLED=true

# ── LangGraph ────────────────────────────
MAX_AGENT_ITERATIONS=10
SESSION_TTL_SECONDS=3600
```

---

## 13. Behavior Comparison: Old vs New

### Scenario: User uploads hand X-ray and asks "Do I need to go to the hospital?"

**Old (hardcoded pipeline):**
```
1. Router runs → "hand"
2. HandAgent runs → detections
3. DiagnosisAgent runs → summary
4. TriageAgent runs → RED
5. HospitalAgent runs → hospitals list
6. PDFReportAgent runs → generates PDF even though nobody asked
7. Returns everything

Total: same 6 steps, every single time, for every single request
```

**New (agentic):**
```
Supervisor reads: image + question about hospital → I need to analyze this image first

1. Calls detect_body_part → "hand, 0.92"
   Supervisor: confidence is good, route to hand detector

2. Calls detect_hand_fracture → {detections: [{label: "distal_radius_fracture", score: 0.78}]}
   Supervisor: fracture found with decent confidence, need clinical assessment

3. Calls generate_diagnosis → {finding: "distal radius fracture", severity: "moderate"}
   Supervisor: have diagnosis, now need triage to answer the hospital question

4. Calls assess_triage → {level: "RED", rationale: "displaced fracture, immediate care required"}
   Supervisor: RED triage — user asked about going to hospital, hospitals are mandatory

5. Calls find_nearby_hospitals → {hospitals: [...]}
   Supervisor: I now have everything to answer. No PDF was requested.

6. Returns: "Yes, go to the ER now. Your X-ray shows a likely distal radius fracture..."

Total: exactly 5 targeted tool calls, no unnecessary steps
```

---

### Scenario: User asks "What is a Colles fracture?"

**Old:** Routes to chat endpoint → calls Groq with template prompt → returns answer
(Works fine but goes through unnecessary overhead)

**New:**
```
Supervisor reads: text-only question, no image → knowledge_agent territory

1. Calls get_orthopedic_knowledge("Colles fracture") → {answer, description, treatment}
   OR
   Supervisor decides: I know this already from training → responds directly, zero tool calls

Total: 0 or 1 tool calls
```

---

### Scenario: Patient has 5 previous studies, asking about deterioration trend

**Old:** Not possible — no multi-study analysis in the chat flow

**New:**
```
Supervisor reads: multi-study context, patient_id present

1. Calls get_patient_history(patient_id) → {5 past studies}
   Supervisor: have history, now analyze trends

2. Calls analyze_multiple_studies(studies) → {trend: "progressive bone density loss", flag: true}
   Supervisor: concerning trend found, clinical assessment needed

3. Calls assess_triage({longitudinal: true, deterioration: true}) → AMBER
   Supervisor: have everything needed

Returns: "Your scans over the past 8 months show progressive changes..."
```

---

## Quick Start Commands (Once Built)

```bash
# Setup
cd ortho-backend
uv sync                          # or: pip install -e .

# Run FastAPI server
uvicorn main:app --reload --port 8000

# Run MCP server (for Claude Desktop / Cursor)
python -m mcp.server

# Run MCP inspector (debug tools in browser)
mcp dev mcp/server.py

# View LangSmith traces
# → https://smith.langchain.com/projects/orthoassist-dev
```
