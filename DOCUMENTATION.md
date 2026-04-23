# OrthoAssist — Comprehensive Technical Documentation

> Generated: 2026-04-23

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Backend Architecture](#3-backend-architecture)
   - 3.1 [Application Entry Point](#31-application-entry-point)
   - 3.2 [Configuration](#32-configuration)
   - 3.3 [Middleware and CORS](#33-middleware-and-cors)
4. [LangGraph Agent Pipeline](#4-langgraph-agent-pipeline)
   - 4.1 [Shared State — AgentState](#41-shared-state--agentstate)
   - 4.2 [Graph Nodes](#42-graph-nodes)
   - 4.3 [Control-Flow Routing](#43-control-flow-routing)
   - 4.4 [Care-Plan Node](#44-care-plan-node)
   - 4.5 [Multi-Agent Integration Node](#45-multi-agent-integration-node)
5. [Multi-Agent System](#5-multi-agent-system)
   - 5.1 [BaseAgent Abstract Class](#51-baseagent-abstract-class)
   - 5.2 [Specialized Agents](#52-specialized-agents)
   - 5.3 [MultiAgentCoordinator](#53-multiagentcoordinator)
   - 5.4 [Coordination Lifecycle](#54-coordination-lifecycle)
6. [Tool Catalog](#6-tool-catalog)
   - 6.1 [Vision Tools](#61-vision-tools)
   - 6.2 [CT Tools](#62-ct-tools)
   - 6.3 [MRI Tools](#63-mri-tools)
   - 6.4 [Modality Tools](#64-modality-tools)
   - 6.5 [Clinical Tools](#65-clinical-tools)
   - 6.6 [Knowledge Tools](#66-knowledge-tools)
   - 6.7 [Report Tools](#67-report-tools)
   - 6.8 [Hospital Tools](#68-hospital-tools)
7. [API Endpoints](#7-api-endpoints)
   - 7.1 [Analysis](#71-analysis)
   - 7.2 [Chat and Sessions](#72-chat-and-sessions)
   - 7.3 [Patients](#73-patients)
   - 7.4 [Reports](#74-reports)
   - 7.5 [Knowledge Base](#75-knowledge-base)
   - 7.6 [Multi-Agent](#76-multi-agent)
   - 7.7 [Feedback and Learning](#77-feedback-and-learning)
   - 7.8 [System](#78-system)
8. [Key Services](#8-key-services)
   - 8.1 [LLM Service (Groq/OpenAI)](#81-llm-service-groqopenai)
   - 8.2 [MongoDB Service](#82-mongodb-service)
   - 8.3 [RAG Store](#83-rag-store)
   - 8.4 [Chat Store](#84-chat-store)
   - 8.5 [Patient Store](#85-patient-store)
   - 8.6 [Storage Service](#86-storage-service)
   - 8.7 [Agent Learning — AdaptiveSupervisor](#87-agent-learning--adaptivesupervisor)
   - 8.8 [Probabilistic Reasoning](#88-probabilistic-reasoning)
   - 8.9 [Session Service](#89-session-service)
9. [MCP Server](#9-mcp-server)
10. [Frontend Architecture](#10-frontend-architecture)
    - 10.1 [App Router Structure](#101-app-router-structure)
    - 10.2 [Dashboard Pages](#102-dashboard-pages)
    - 10.3 [Key Components](#103-key-components)
    - 10.4 [Hooks](#104-hooks)
    - 10.5 [State Management](#105-state-management)
    - 10.6 [API Client and Auth Utilities](#106-api-client-and-auth-utilities)
11. [Data Flow — End-to-End](#11-data-flow--end-to-end)
    - 11.1 [X-ray Analysis Flow](#111-x-ray-analysis-flow)
    - 11.2 [Chat Message Flow](#112-chat-message-flow)
    - 11.3 [Agent Collaboration Flow](#113-agent-collaboration-flow)
    - 11.4 [Report Generation Flow](#114-report-generation-flow)
12. [Technologies and Dependencies](#12-technologies-and-dependencies)
    - 12.1 [Backend Dependencies](#121-backend-dependencies)
    - 12.2 [Frontend Dependencies](#122-frontend-dependencies)
13. [Environment Variables](#13-environment-variables)
14. [Setup and Installation](#14-setup-and-installation)
    - 14.1 [Backend](#141-backend)
    - 14.2 [Frontend](#142-frontend)
15. [MongoDB Collections](#15-mongodb-collections)
16. [YOLO Models](#16-yolo-models)
17. [Detection Thresholds and Tuning Knobs](#17-detection-thresholds-and-tuning-knobs)
18. [Security Considerations](#18-security-considerations)
19. [Known Gaps and Documentation Notes](#19-known-gaps-and-documentation-notes)

---

## 1. Project Overview

OrthoAssist is an **AI-powered orthopedic diagnostic platform** designed for two primary user roles — doctors and patients. Its core purpose is to automate the interpretation of orthopedic imaging studies (X-rays, CT scans, MRI scans) and to generate structured clinical reports, care plans, and patient-facing educational content.

**Primary capabilities:**

- Upload plain X-ray images (JPEG/PNG) or DICOM files/archives; the system automatically detects the imaging modality and body region.
- Run YOLOv8-based object detection to identify anatomical landmarks and fractures in X-ray images.
- For CT scans, perform full volumetric bone segmentation using TotalSegmentator; for MRI, perform knee or spine segmentation using kneeseg and TotalSegmentator.
- Invoke a LangGraph-orchestrated agentic pipeline that selects and sequences tools autonomously, following a Supervisor → Tool Executor → Response Builder pattern.
- A parallel multi-agent system (vision, clinical, treatment planner, rehabilitation, patient education, appointment) that perceives, reasons, formulates goals, and reaches consensus independently.
- Generate role-differentiated PDF reports (patient-simplified vs. clinician-detailed) via ReportLab.
- Maintain persistent, session-scoped chat history backed by MongoDB.
- Expose all 30+ tools simultaneously as a Model Context Protocol (MCP) server, usable from Claude Desktop, Cursor, or any MCP-compatible client.
- Learn continuously from user feedback and live execution outcomes using an AdaptiveSupervisor and Bayesian belief updater.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                               │
│     Next.js 16 Frontend (Clerk Auth, shadcn/ui, Zustand)            │
│     Claude Desktop / Cursor IDE (MCP Protocol)                       │
└────────────────┬────────────────────────────────┬───────────────────┘
                 │  HTTP / REST  (:3000 → :8000)   │  MCP (stdio/SSE)
                 ▼                                 ▼
┌────────────────────────────┐   ┌─────────────────────────────────────┐
│   FastAPI  (:8000)         │   │   MCP Server (FastMCP)               │
│   /api/analyze             │   │   All tools registered via           │
│   /api/chat                │   │   @mcp.tool() decorator              │
│   /api/reports             │   └──────────────┬──────────────────────┘
│   /api/patients            │                  │
│   /api/multi_agent         │                  │
│   /api/feedback            │                  │
└──────────────┬─────────────┘                  │
               │        both call               │
               ▼                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│              LangGraph  StateGraph  (AgentState TypedDict)            │
│                                                                      │
│  START → multi_agent_integrator → supervisor                         │
│             │                        │                               │
│             │               ┌────────┴────────┐                      │
│             │               │   tool_executor │◄────────────────┐    │
│             │               └────────┬────────┘                 │    │
│             │                        │  tool results             │    │
│             │                        └──────────────────────────►│    │
│             │                         supervisor (loop)           │    │
│             │                        │                            │    │
│             │               care_plan_node (parallel agents)      │    │
│             │                        │                            │    │
│             └───────────────response_builder──────────────────► END   │
│                              │  error_handler                         │
└──────────────────────────────────────────────────────────────────────┘
               │
               ▼
  YOLOv8 · TotalSegmentator · kneeseg · RAG · MongoDB · Cloudinary/Local FS
```

---

## 3. Backend Architecture

### 3.1 Application Entry Point

**File:** `backend/main.py`

The application is a FastAPI application created by the `create_app()` factory function. It uses an `asynccontextmanager` lifespan that:

1. Validates the Python runtime is 3.11.x.
2. Calls `storage_service.initialize()` — sets up local or Cloudinary storage.
3. Calls `mongo_service.initialize()` — connects to MongoDB and creates indexes.
4. Calls `adaptive_supervisor.ensure_initialized()` — loads persisted learning patterns from MongoDB.
5. Calls `bayesian_updater.ensure_initialized()` — loads persisted tool beliefs from MongoDB.
6. On shutdown, closes the MongoDB client.

The FastAPI instance:
- Includes all API routers under the `/api` prefix.
- Mounts a `StaticFiles` endpoint at `/storage` to serve locally-stored PDFs and images.

### 3.2 Configuration

**File:** `backend/core/config.py`

A `pydantic-settings` `BaseSettings` class (`Settings`) is used for all configuration. Values are read from `backend/.env`. Key properties:

| Property | Purpose |
|---|---|
| `app_env` | `dev` or `production` — controls defaults and CORS behavior |
| `supervisor_llm` | Model used by the LangGraph supervisor (default `gpt-4o`) |
| `fast_llm` | Model for faster/cheaper tasks (default `gpt-4o-mini`) |
| `max_agent_iterations` | Hard cap on supervisor loop iterations (default `10`) |
| `session_ttl_seconds` | LangGraph MemorySaver TTL (default `3600`) |
| `multi_agent_enabled` | Feature flag for the multi-agent integration node (default `False`) |
| `multi_agent_confidence_threshold` | Minimum consensus confidence required (default `0.8`) |
| `router_threshold` | Body-part detection confidence gate (default `0.70`) |
| `detector_score_min` | Minimum YOLO detection score (default `0.35`) |
| `triage_red_threshold` | Severity score above which triage is RED (default `0.80`) |
| `triage_amber_threshold` | Severity score above which triage is AMBER (default `0.60`) |
| `storage_type` | `local` or `cloudinary` |
| `totalsegmentator_device` | `cpu` or `cuda:0` for CT/MRI segmentation |
| `totalsegmentator_fast` | Use 3mm fast mode (default `True`) — significantly reduces CPU inference time |
| `ct_max_volume_mb` / `mri_max_volume_mb` | Upload size caps for volumetric data (default `500` MB each) |
| `phi_redaction_enabled` | Toggle PHI (Protected Health Information) redaction |
| `medical_disclaimer_enabled` | Append AI-generated content disclaimers |

The singleton `settings = get_settings()` is imported by all modules.

### 3.3 Middleware and CORS

**File:** `backend/api/middleware.py`

- CORS is configured from `settings.cors_origins`. In dev mode this defaults to `["*"]`. In production it restricts to the explicit `FRONTEND_URL` and any comma-separated values in `CORS_ALLOW_ORIGINS`.
- Request logging is handled by loguru.

---

## 4. LangGraph Agent Pipeline

The agent pipeline is the core orchestration layer. It is built as a LangGraph `StateGraph` compiled with a `MemorySaver` checkpointer.

### 4.1 Shared State — AgentState

**File:** `backend/graph/state.py`

`AgentState` is a `TypedDict` that acts as the single shared data structure flowing through every graph node. All fields are optional (`total=False`).

**Input fields:**

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | Unique identifier for the analysis session |
| `user_message` | `str` | Raw text from the user |
| `image_data` | `str \| None` | Base64-encoded X-ray image (data URL) |
| `symptoms` | `str \| None` | Free-text symptom description |
| `patient_id` | `str \| None` | Reference to patient record in MongoDB |
| `location` | `str \| None` | Patient location for hospital search |
| `actor_role` | `str \| None` | `"doctor"` or `"patient"` |
| `actor_name` | `str \| None` | Display name from Clerk |
| `modality` | `str \| None` | `"xray"`, `"ct"`, or `"mri"` |
| `body_region` | `str \| None` | e.g. `"hand"`, `"spine"`, `"knee"` |
| `volume_path` | `str \| None` | Path to NIfTI file on disk (CT/MRI) |
| `dicom_metadata` | `dict \| None` | Extracted DICOM tag dictionary |

**Runtime fields populated during execution:**

| Field | Description |
|---|---|
| `body_part` | Detected body part (from vision tools) |
| `detections` | YOLO detection results from X-ray analysis |
| `ct_findings` | Segmentation findings from CT tools |
| `mri_findings` | Segmentation findings from MRI tools |
| `diagnosis` | Structured diagnosis dictionary |
| `triage_result` | Structured triage result (level: RED/AMBER/GREEN) |
| `knowledge_context` | RAG retrieval results |
| `hospitals` | Nearby hospital records |
| `report_url` | URL to the generated PDF report |
| `annotated_slices_base64` | Annotated key slices for CT/MRI |
| `patient_info` | Name, age, gender, doctor, patient_id |
| `multi_agent_insights` | Insights from the multi-agent coordination pass |
| `multi_agent_coordination` | Metadata about the coordination round |

**Care-plan fields (populated by `care_plan_node`):**

| Field | Description |
|---|---|
| `treatment_plan` | Output from TreatmentPlannerAgent |
| `rehabilitation_plan` | Output from RehabilitationAgent |
| `patient_education` | Output from PatientEducationAgent |
| `appointment_schedule` | Output from AppointmentAgent |

**LangGraph internals:**

| Field | Description |
|---|---|
| `messages` | LangChain message list (add_messages reducer) |
| `tool_calls_made` | Ordered list of tool names called this session |
| `agent_trace` | Structured trace of every node decision |
| `iteration_count` | Loop counter compared against `max_agent_iterations` |
| `error` | Error string if a node failed |
| `final_response` | Final natural language response to the user |

### 4.2 Graph Nodes

**File:** `backend/graph/nodes/`

| Node | File | Responsibility |
|---|---|---|
| `supervisor` | `supervisor.py` | Binds `ALL_TOOLS` to the LLM (GPT-4o via `bind_tools`), constructs the system prompt with learning insights and pipeline state, invokes the LLM, and emits tool-call or no-tool responses |
| `tool_executor` | `tool_executor.py` | Iterates over `AIMessage.tool_calls`, calls the matching LangChain tool, stores outcomes in `tool_execution_outcomes`, updates `tool_calls_made` and `agent_trace` |
| `response_builder` | `response_builder.py` | Formats the final natural language response from structured pipeline state; prefers the last non-tool AI message but falls back to synthesizing from diagnosis/triage/care-plan data |
| `error_handler` | `error_handler.py` | Catches iteration-count exceeded or execution errors, produces a user-safe error message, and routes either back to supervisor (for retries) or to response_builder (for final failure response) |
| `care_plan_node` | `graph.py` (inline) | Runs four specialist agents in parallel (perceive → reason → act) once diagnosis and triage are present |
| `multi_agent_integrator` | `graph.py` (inline) | Optionally calls the MultiAgentCoordinator and enriches state with consensus recommendations; controlled by `settings.multi_agent_enabled` |

### 4.3 Control-Flow Routing

The `should_continue` conditional edge function governs the loop after each supervisor invocation:

```
supervisor output has tool_calls?
  → YES → tool_executor (always)
  → NO  → check pipeline state:
       diagnosis + triage present AND care_plan NOT generated?
         → care_plan_node
       care_plan generated AND no report requested?
         → response_builder
       report requested AND report_url present OR report attempted?
         → response_builder
       otherwise?
         → response_builder
       error or iteration cap hit?
         → error_handler
```

The `error_handler_route` conditional edge allows the error handler to retry via supervisor (for recoverable errors) or terminate via response_builder (for iteration exhaustion).

### 4.4 Care-Plan Node

When `diagnosis` and `triage_result` are both present in state and `care_plan_generated` is `False`, the graph routes to `care_plan_node` before building the response. This node runs four specialist agents in three phases:

1. **Phase 1 — Parallel perception:** All four agents (TreatmentPlanner, Rehabilitation, PatientEducation, Appointment) and the optional PDFGeneration agent call `perceive(context)` concurrently via `asyncio.gather`.
2. **Phase 2 — Parallel reasoning:** Each agent calls `reason(context + its own perception)` concurrently.
3. **Phase 3 — Parallel action:** Each agent calls `act(first_recommended_action)` concurrently.

Results are written back to `AgentState` as `treatment_plan`, `rehabilitation_plan`, `patient_education`, and `appointment_schedule`. Failures are silently swallowed (logged at WARNING level) so a failing specialist agent never blocks the user response.

### 4.5 Multi-Agent Integration Node

This optional graph node runs at the very start of every request (before the supervisor). When `settings.multi_agent_enabled = True`:

1. Assembles a `multi_agent_context` dict from the current state.
2. Calls `agent_coordinator.coordinate_analysis(context)` which runs the full 6-phase autonomous coordination cycle.
3. Extracts consensus tool recommendations, agent perceptions, collaborative opportunities, and learning signals.
4. Writes `multi_agent_insights` and `multi_agent_coordination` back to state.
5. The supervisor then reads `multi_agent_insights.consensus_recommendation` and can bias its tool selection accordingly.

---

## 5. Multi-Agent System

### 5.1 BaseAgent Abstract Class

**File:** `backend/agents/base_agent.py`

All specialized agents inherit from `BaseAgent`. It provides:

- **AgentMessage dataclass:** typed envelope for inter-agent communication with fields `sender`, `receiver`, `message_type` (`"request"`, `"response"`, `"notification"`, `"consensus"`), `content`, `priority`, `confidence`.
- **AgentGoal dataclass:** a goal with `priority` (`"urgent"`, `"high"`, `"medium"`, `"low"`), `objective`, `success_criteria`, `deadline`, and lifecycle tracking (`status`: `"pending"`, `"in_progress"`, `"completed"`, `"failed"`).
- **AgentCapabilities dataclass:** declares `tool_capabilities`, `perception_abilities`, `reasoning_level`, `collaboration_style`, `specialization_domains`, `confidence_ranges`.
- **Abstract interface:** every subclass must implement `perceive(context)`, `reason(context)`, and `act(action)`.
- **Lifecycle methods:** `formulate_goals()`, `select_action()`, `execute_action()`, `collaborate_with_agent()`.
- **Performance metrics:** per-agent counters for tasks completed, tasks failed, collaboration success/failure.
- **Bayesian integration:** on `__init__`, each tool capability is registered with `bayesian_updater.initialize_belief()`. Outcomes of `execute_action()` call `bayesian_updater.update_belief()`.

### 5.2 Specialized Agents

| Agent Class | File | agent_name | Role |
|---|---|---|---|
| `VisionAgent` | `vision_agent.py` | `vision_agent` | Perceives image data; recommends vision detection tools; specializes in X-ray analysis and body-part classification |
| `ClinicalAgent` | `clinical_agent.py` | `clinical_agent` | Perceives detection results and patient info; recommends diagnosis and triage tools; specializes in orthopedic clinical reasoning |
| `TreatmentPlannerAgent` | `treatment_planner_agent.py` | `treatment_planner_agent` | Generates conservative and surgical treatment pathways using `knowledge_get_treatment_recommendations` |
| `RehabilitationAgent` | `rehabilitation_agent.py` | `rehabilitation_agent` | Produces physiotherapy and rehabilitation protocols |
| `PatientEducationAgent` | `patient_education_agent.py` | `patient_education_agent` | Creates patient-facing educational content explaining the diagnosis and recovery expectations |
| `AppointmentAgent` | `appointment_agent.py` | `appointment_agent` | Schedules follow-up appointments and care milestones |
| `PDFGenerationAgent` | `pdf_agent.py` | `pdf_generation_agent` | Orchestrates report PDF generation; invoked from `care_plan_node` when image/annotation data is available |

### 5.3 MultiAgentCoordinator

**File:** `backend/agents/agent_coordinator.py`

`MultiAgentCoordinator` is a singleton (`agent_coordinator`) that lazily initializes all seven agents on first use. It owns:

- `agents: Dict[str, BaseAgent]` — the registry of all live agent instances.
- `message_bus: List[AgentMessage]` — a shared in-memory message log.
- `consensus_history: List[ConsensusResult]` — historical consensus records for pattern analysis.
- `collaboration_metrics` — running counts of total collaborations, successful/failed consensus, and average coordination time.

**ConsensusResult dataclass** captures: `consensus_id`, `topic`, `participants`, `consensus_reached`, `final_decision`, `participant_assessments`, `confidence`, `timestamp`, `reasoning_process`.

### 5.4 Coordination Lifecycle

When `coordinate_analysis(context)` is called, it executes six phases in sequence:

| Phase | Method | Description |
|---|---|---|
| 1 | `_parallel_agent_perception` | All agents call `perceive(context)` concurrently; results keyed by agent name |
| 2 | `_parallel_agent_reasoning` | Each agent calls `reason({...context, ...its_perception})` concurrently |
| 3 | `_parallel_goal_formulation` | Each agent calls `formulate_goals(...)` concurrently; AgentGoal lists returned |
| 4 | `_facilitate_collaboration` | Identifies collaboration needs (vision–clinical mutual verification, multi-agent consensus); dispatches to `_handle_vision_clinical_collaboration` or `_handle_multi_agent_consensus` |
| 5 | `_execute_collaborative_actions` | Executes decisions from Phase 4 |
| 6 | `_build_agent_consensus` | Aggregates all results into a final `ConsensusResult`; confidence-aligns participant assessments (consensus if all confidences within 0.2 of each other) |

**Consensus evaluation:** Consensus is declared reached when the range of participant confidence scores is less than 0.2. Final decisions use the highest-confidence participant's assessment. Without consensus, a weighted average approach is used.

---

## 6. Tool Catalog

All tools are LangChain `StructuredTool` objects registered in `ALL_TOOLS` (`backend/tools/__init__.py`). They are bound to the supervisor LLM via `llm.bind_tools(ALL_TOOLS)` and simultaneously registered with the MCP server.

### 6.1 Vision Tools

**Namespace prefix:** `vision_`  
**File:** `backend/tools/vision/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `vision_detect_body_part` | `body_part_detector.py` | Runs a routing YOLO model to classify the uploaded X-ray as `hand` or `leg` (or other region); gates subsequent detection based on `router_threshold` (0.70) |
| `vision_detect_hand_fracture` | `hand_detector.py` | Runs `hand_yolo.pt` (YOLOv8) on the image; returns a list of detections with bounding boxes, class labels, and confidence scores |
| `vision_detect_leg_fracture` | `leg_detector.py` | Runs `leg_yolo.pt` (YOLOv8) on the image; same output schema as hand detector |
| `vision_annotate_image` | `annotator.py` | Draws bounding boxes, labels, and confidence overlays on the original X-ray; returns `annotated_image_base64` |
| `vision_upload_image` | `uploader.py` | Saves image bytes to storage (local or Cloudinary); returns a public URL |

**Supporting modules:**
- `yolo_runtime.py` — shared model loading and inference runtime; models are cached in memory after first load.

### 6.2 CT Tools

**Namespace prefix:** `ct_`  
**File:** `backend/tools/ct/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `ct_analyze_full_body` | `bone_segmentation.py` | Full-body bone segmentation using TotalSegmentator; identifies major skeletal structures in a NIfTI volume |
| `ct_analyze_spine` | `spine_segmentation.py` | Spine-specific segmentation using TotalSegmentator or VerSe nnUNet; segments individual vertebrae |
| `ct_analyze_appendicular` | `appendicular_segmentation.py` | Segmentation of appendicular skeleton (limbs, pelvis, shoulder girdle) using TotalSegmentator |

**Supporting modules:**
- `ct_utils.py` — NIfTI loading, Hounsfield unit windowing, slice extraction.
- `ct_runtime.py` — TotalSegmentator invocation wrapper; handles CPU vs. GPU device selection and fast/full mode.
- `totalsegmentator_worker.py` — subprocess isolation for TotalSegmentator to avoid memory conflicts.

### 6.3 MRI Tools

**Namespace prefix:** `mri_`  
**File:** `backend/tools/mri/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `mri_analyze_knee` | `knee_segmentation.py` | Knee cartilage and bone segmentation using the `kneeseg` library |
| `mri_analyze_spine` | `spine_segmentation.py` | Spine disc and vertebra segmentation on MRI volumes using TotalSegmentator |

**Supporting modules:**
- `mri_utils.py` — NIfTI volume loading and slice rendering utilities for MRI.
- `mri_runtime.py` — model invocation runtime; manages device placement.

### 6.4 Modality Tools

**File:** `backend/tools/modality/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `detect_imaging_modality` | `detect_modality.py` | Infers imaging modality (`xray`, `ct`, `mri`) from file content and DICOM metadata |
| `parse_dicom` | `dicom_parser.py` | Parses a DICOM file; extracts metadata (modality, body part, study/series description, patient info) |
| `extract_mid_slice` | `dicom_parser.py` | Extracts the middle slice from a DICOM series as a PNG image for preview |

**Supporting module:**
- `dicom_utils.py` — comprehensive DICOM handling: `is_dicom()`, `read_dicom_metadata()`, `dicom_bytes_to_nifti_file()`, `dicom_series_to_nifti_file()`, `normalize_dicom_series()`, `extract_dicom_files_from_zip_bytes()`, `normalize_body_part()`. This module is the entry point for all DICOM ingestion in both the analyze and chat endpoints.

### 6.5 Clinical Tools

**Namespace prefix:** `clinical_`  
**File:** `backend/tools/clinical/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `clinical_generate_diagnosis` | `diagnosis.py` | Generates a structured diagnosis dict from YOLO/segmentation detections; uses the fast LLM for synthesis; output contains `finding`, `severity`, `confidence`, `summary` |
| `clinical_assess_triage` | `triage.py` | Assigns triage level (RED/AMBER/GREEN) from diagnosis severity; computes urgency score and recommended timeframe |
| `clinical_analyze_symptoms` | `symptoms.py` | Analyzes free-text symptom descriptions and maps them to probable orthopedic conditions |
| `clinical_analyze_multiple_studies` | `multi_study.py` | Compares findings across multiple imaging sessions for the same patient; identifies progression |
| `clinical_get_patient_history` | `history.py` | Retrieves and summarizes stored patient clinical history from MongoDB |

### 6.6 Knowledge Tools

**File:** `backend/tools/knowledge/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `knowledge_lookup_orthopedic_condition` | `condition_lookup.py` | Returns structured information about a named orthopedic condition (anatomy, prevalence, classification) |
| `knowledge_get_treatment_recommendations` | `treatment.py` | Returns conservative and surgical treatment options for a given diagnosis and severity |
| `knowledge_get_anatomical_reference` | `anatomy.py` | Returns anatomical context and landmark descriptions for a named body part |
| `knowledge_classify_fracture_type` | `fracture_classifier.py` | Classifies fracture type (e.g. transverse, oblique, comminuted, stress) from detection details |
| `knowledge_get_orthopedic_knowledge` | `ortho_knowledge.py` | General orthopedic knowledge retrieval; delegates to the RAG store for document search |
| `knowledge_get_rehabilitation_plan` | `rehabilitation.py` | Returns a structured rehabilitation protocol for a given injury type and triage level |
| `knowledge_get_patient_education` | `patient_education.py` | Returns patient-friendly educational materials explaining the diagnosis and recovery |
| `knowledge_get_appointment_schedule` | `appointment.py` | Returns a recommended appointment schedule and follow-up milestones |

### 6.7 Report Tools

**File:** `backend/tools/report/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `report_generate_comprehensive_pdf` | `comprehensive_pdf.py` | Primary report tool; generates a full PDF with patient info, X-ray/annotated image, findings, diagnosis, triage, and care-plan sections; handles both patient and clinician roles |
| `report_generate_patient_pdf` | `patient_pdf.py` | Simplified patient-facing PDF with plain-language findings and next steps |
| `report_generate_clinician_simple_pdf` | `clinician_simple_pdf.py` | One-page clinical summary for quick doctor review |
| `report_generate_clinician_pdf` | `clinician_pdf.py` | Full technical PDF with detection confidence tables, triage reasoning, and clinical recommendations |
| `report_save_to_storage` | `save_report.py` | Persists a PDF to local storage or Cloudinary; returns `public_url` and stores metadata in MongoDB |
| `report_retrieve` | `retrieve_report.py` | Fetches a stored report record by session_id or report_id from MongoDB |

**Supporting module:**
- `pdf_engine.py` — shared ReportLab PDF rendering helpers (page setup, fonts, image embedding, color themes).

### 6.8 Hospital Tools

**File:** `backend/tools/hospital/`

| Tool Name | Implementation File | Description |
|---|---|---|
| `hospital_find_nearby` | `finder.py` | Searches for orthopedic hospitals near a given location; returns name, distance, address, contact |
| `hospital_get_details` | `details.py` | Fetches detailed information (specialties, surgeons, equipment) for a specific hospital |
| `hospital_get_emergency_contacts` | `emergency.py` | Returns emergency contact numbers and protocols for orthopedic emergencies |

**Supporting module:**
- `data.py` — static hospital data store; used when no external geo-lookup API is configured.

---

## 7. API Endpoints

All endpoints are mounted under the `/api` prefix. The FastAPI Swagger UI is available at `http://localhost:8000/docs` when running locally.

### 7.1 Analysis

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analyze` | Upload X-ray image or DICOM data; runs the full LangGraph agent pipeline; supports `image_data` (base64), `dicom_data` (base64 DICOM bytes or ZIP), `modality`, `body_region`, `symptoms`, `patient_id`, `location`, `session_id`. Returns `AgentResponse` with diagnosis, triage, hospitals, report_url, and annotated_image_base64 |

### 7.2 Chat and Sessions

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Send a message to the agent (creates session automatically if no session_id); supports image and DICOM attachments; returns `AgentResponse` |
| `POST` | `/api/chat/sessions` | Create a new chat session; injects a role-specific intake greeting |
| `GET` | `/api/chat/sessions` | List chat sessions for an actor (`actor_id`, `actor_role` query params) |
| `POST` | `/api/chat/sessions/{chat_id}/messages` | Send a message within an existing session; handles attachment classification, DICOM ingestion, patient info extraction, pipeline state persistence, and report generation |
| `GET` | `/api/chat/sessions/{chat_id}/messages` | Retrieve full message history for a session |
| `GET` | `/api/chat/sessions/{chat_id}/trace` | Retrieve the agent execution trace for a session |
| `POST` | `/api/chat/assignments` | Assign a patient to a doctor |
| `GET` | `/api/chat/patients` | Derive a patient list from chat sessions and pipeline state (doctor-only) |

### 7.3 Patients

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/patients` | List patient records (doctor-only) |
| `POST` | `/api/patients` | Create a new patient record |
| `GET` | `/api/patients/{id}` | Fetch a single patient record |

### 7.4 Reports

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/reports` | List reports for the current actor |
| `GET` | `/api/reports/{id}` | Fetch a single report record and PDF URL |

### 7.5 Knowledge Base

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/knowledge` | Query the orthopedic RAG knowledge base; accepts `q` (query text) and optional `patient_id` |
| `POST` | `/api/knowledge/ingest` | Ingest a document into the RAG store |

### 7.6 Multi-Agent

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/multi_agent/analyze` | Trigger a full autonomous multi-agent coordination cycle for a given context |
| `GET` | `/api/multi_agent/status` | Get real-time status of all agents (active goals, task queues, performance) |
| `GET` | `/api/multi_agent/goals` | List goals formulated by agents; optionally filter by `agent_name` |
| `GET` | `/api/multi_agent/performance` | Agent performance metrics and system health |
| `GET` | `/api/multi_agent/consensus/history` | Paginated history of agent consensus events |
| `GET` | `/api/multi_agent/collaboration/analyze` | Statistical analysis of collaboration patterns over a given number of days |
| `POST` | `/api/multi_agent/simulation` | Simulate a full collaborative case analysis (demo/testing endpoint) |
| `POST` | `/api/multi_agent/care_plan` | Explicitly trigger care-plan generation via the four specialist agents; returns `treatment_plan`, `rehabilitation_plan`, `patient_education`, `appointment_schedule` |

### 7.7 Feedback and Learning

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/feedback` | Submit structured clinician or patient feedback for a session; triggers `adaptive_supervisor.learn_from_feedback()` |
| `GET` | `/api/feedback/learning/summary` | Get a summary of all learned patterns, success/failure counts, and confidence levels |

### 7.8 System

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check; returns `{"status": "ok"}` |
| `GET` | `/api/metrics` | Returns `active_sessions` (from MongoDB) and `stored_reports` count |
| `GET` | `/api/dashboard` | Aggregated dashboard statistics for the doctor UI |
| `GET` | `/api/nearby` | Nearby hospital lookup (also proxied from frontend Next.js route handler) |

---

## 8. Key Services

### 8.1 LLM Service (Groq/OpenAI)

**File:** `backend/services/groq_llm.py`

Provides the `get_supervisor_llm()` factory function. Despite the filename referencing Groq, the actual model used is configurable via `settings.supervisor_llm` (default `gpt-4o`) and defaults to `langchain_openai.ChatOpenAI`. A `fast_llm` variant (default `gpt-4o-mini`) is used for cheaper synthesis tasks. LangSmith tracing is configured at module import time using `settings.langchain_api_key` and `settings.langchain_project`.

### 8.2 MongoDB Service

**File:** `backend/services/mongo.py`

`MongoService` is a singleton wrapping Motor (async MongoDB driver). It:

- Checks `settings.mongodb_uri` at startup; if empty, it operates in disabled mode (all collections return gracefully).
- Creates compound indexes on `chat_sessions`, `chat_messages`, `chat_traces`, `patients`, `reports`, `agent_patterns`, and `tool_beliefs` on first connect.
- Exposes `get_collection(name)` for typed collection access.

**Collections used:**

| Collection | Purpose |
|---|---|
| `chat_sessions` | Session metadata (chat_id, actor, patient, doctor, title, timestamps) |
| `chat_messages` | Per-message records with attachment URLs and agent traces |
| `chat_traces` | Full agent execution trace logs |
| `chat_pipeline_state` | Persisted clinical pipeline state across turns (diagnosis, triage, body_part, patient_info) |
| `patients` | Patient demographic records and analysis history |
| `reports` | Report metadata and PDF URLs keyed by patient_id |
| `agent_patterns` | Learned experience patterns from AdaptiveSupervisor |
| `tool_beliefs` | Bayesian belief parameters (alpha, beta) per tool |
| `kb_documents` | RAG document index |
| `kb_chunks` | RAG text chunks for retrieval |

### 8.3 RAG Store

**File:** `backend/services/rag_store.py`

A lightweight keyword-based retrieval system (not vector-based). Documents are chunked into 800-character segments with 120-character overlap and stored in `kb_chunks`. Retrieval uses a MongoDB regex OR filter across all query tokens, then re-ranks results by token-hit count (BM25-like).

**Key methods:**
- `ingest_document(title, content, source, patient_id)` — chunk and store document; returns `{document_id, chunk_count}`.
- `retrieve(query, patient_id, limit)` — keyword token search; supports per-patient scoping; returns ranked list of chunk dicts.

### 8.4 Chat Store

**File:** `backend/services/chat_store.py`

Manages chat sessions and messages in MongoDB. Key responsibilities:
- `create_session()` / `get_session()` / `list_sessions()` — session CRUD.
- `append_message()` — appends a message record with optional `attachment_data_url` and `annotated_image_base64`.
- `get_messages()` — retrieves all messages for a session.
- `save_pipeline_state()` / `get_pipeline_state()` — persists the clinical pipeline state dict across turns so the agent can resume with full context on subsequent messages.
- `init_trace()` / `append_trace_event()` / `complete_trace()` — execution trace logging.
- `assign_patient_to_doctor()` / `is_patient_assigned()` — RBAC helper for doctor-patient assignment.

### 8.5 Patient Store

**File:** `backend/services/patient_store.py`

- `upsert_patient(name, age, gender, doctor_user_id, patient_user_id, chat_id, existing_patient_id)` — creates or updates a patient record; returns `{patient_id}`.
- `add_analysis(patient_id, analysis_data)` — appends an analysis result to the patient's history array.
- `save_report(patient_id, patient_name, pdf_url, title, severity, doctor_user_id)` — saves report metadata to the `reports` collection.
- `get_reports(actor_id, actor_role)` — retrieves reports visible to the requesting actor.

### 8.6 Storage Service

**File:** `backend/services/storage.py`

Abstracts file storage between local filesystem and Cloudinary.

- **Local mode:** files are written to `settings.resolved_storage_path/reports/`, `images/`, `chat_attachments/`, etc. The `/storage/` URL prefix is served by FastAPI `StaticFiles`.
- **Cloudinary mode:** files are uploaded to Cloudinary; public URLs are returned directly.
- `save_bytes(payload, filename, subdir)` → `{public_url}`.
- `save_pdf(pdf_bytes, filename)` → `{public_url}`.

### 8.7 Agent Learning — AdaptiveSupervisor

**File:** `backend/services/agent_learning.py`

`AdaptiveSupervisor` provides experience-based learning capabilities. It maintains `experience_patterns: Dict[str, ExperiencePattern]` in memory and persists them to MongoDB's `agent_patterns` collection.

**ExperiencePattern fields:** `pattern_id`, `pattern_type` (`success`, `failure`, `optimization`), `pattern_data`, `success_count`, `failure_count`, `confidence`, `last_applied`.

**Learning triggers:**
- `learn_from_feedback(feedback)` — called when a user submits explicit feedback. Extracts learning signals from incorrect diagnoses, triage mismatches, low/high ratings, missed findings, and incorrect findings.
- `learn_from_execution(execution_state)` — called automatically after every `run_agent()` call. Records tool failure patterns and successful tool sequences into MongoDB.

**Inference:**
- `find_applicable_patterns(current_state)` — returns the top 5 applicable patterns for the current state, used by the supervisor to build learning context injected into the system prompt. Failure patterns are applied when confidence > 0.7; success patterns when confidence > 0.6.

### 8.8 Probabilistic Reasoning

**File:** `backend/services/probabilistic_reasoning.py`

Three cooperating classes implement probabilistic decision support:

**ConfidenceEstimator:**
- `estimate_tool_confidence(tool_name, state)` — computes a final confidence score as `base_confidence × state_multiplier × learning_adjustment`.
- Base confidences are hardcoded per tool (e.g. `vision_detect_body_part`: 0.95, `clinical_generate_diagnosis`: 0.75).
- State multiplier penalizes tools called without prerequisite data (e.g. vision tools without image data → 0.3×).
- Learning adjustment queries `adaptive_supervisor.find_applicable_patterns()` and `bayesian_updater.get_success_probability()`.

**ProbabilisticDecisionMaker:**
- `select_action_with_probability(candidates, state)` — uses Thompson Sampling to balance exploitation (high-confidence tools) with exploration (lower-confidence alternatives).
- `assess_decision_uncertainty(action, state)` — categorizes uncertainty as low/moderate/medium/high and returns recommendations.

**BayesianBeliefUpdater:**
- Maintains Beta distribution parameters (alpha, beta) per tool.
- `update_belief(tool_name, success)` — increments alpha (success) or beta (failure); persists to MongoDB.
- `get_success_probability(tool_name)` — returns `alpha / (alpha + beta)`.
- `get_confidence_interval(tool_name, confidence)` — returns a normal-approximation confidence interval for the posterior.

### 8.9 Session Service

**File:** `backend/services/session.py`

Utility helpers for session token generation and validation using `python-jose` JWT and `passlib` for any internal auth flows (separate from Clerk, which handles all frontend authentication).

---

## 9. MCP Server

**Files:** `backend/mcp/server.py`, `backend/mcp/registry.py`

OrthoAssist exposes all its tools as an MCP (Model Context Protocol) server using the `FastMCP` SDK. This makes all 30+ tools callable from Claude Desktop, Cursor, or any MCP-compatible client.

**`registry.py`** assembles `MCP_TOOL_REGISTRY` — a list of `ToolSpec` objects mapping each tool's `name`, `description`, and `handler` (the same async function used by LangGraph).

**`server.py`** creates a `FastMCP("orthoassist")` instance, iterates over the registry, and registers each tool via `mcp.tool()`. It exposes:
- **Stdio transport** — for Claude Desktop and local IDE integration.
- **SSE/HTTP transport** — if `streamable_http_app()` or `sse_app()` is available on the FastMCP instance.

The server is started independently from the main FastAPI app via `python -m mcp.server` (or `mcp.run()`).

---

## 10. Frontend Architecture

### 10.1 App Router Structure

The frontend is built with Next.js 16 App Router. All routes are under `frontend/app/`.

```
app/
├── layout.tsx                  # Root layout: ClerkProvider, global CSS, theme
├── page.tsx                    # Landing page — redirects to sign-in or dashboard
├── globals.css                 # Base Tailwind + CSS custom properties
├── (auth)/
│   ├── sign-in/[[...sign-in]]/page.tsx    # Clerk sign-in page
│   └── sign-up/[[...sign-up]]/page.tsx    # Clerk sign-up page
├── select-role/page.tsx        # Role selection screen after first login
├── api/
│   └── nearby/route.ts         # Next.js route handler proxying the hospital geo-lookup
└── dashboard/
    ├── layout.tsx              # Dashboard shell: Sidebar + Header, auth guard
    ├── page.tsx                # Role redirect (doctor → /doctor, patient → /patient)
    ├── doctor/
    │   ├── page.tsx            # Doctor overview dashboard
    │   ├── patients/page.tsx   # Patient management panel
    │   ├── reports/page.tsx    # Reports list for doctor
    │   ├── chat/page.tsx       # Agentic chat interface (doctor view)
    │   └── settings/page.tsx   # Doctor settings
    └── patient/
        ├── page.tsx            # Patient overview
        ├── reports/page.tsx    # Patient's own reports
        ├── chat/page.tsx       # Agentic chat interface (patient view)
        └── nearby/page.tsx     # Nearby hospitals map
```

### 10.2 Dashboard Pages

| Page | Route | Role | Description |
|---|---|---|---|
| Doctor Dashboard | `/dashboard/doctor` | Doctor | Aggregate stats: patient count, recent analyses, risk distribution; uses `DoctorDashboardOverview` component |
| Patient Management | `/dashboard/doctor/patients` | Doctor | `DoctorPatientsPanel` showing patient list with triage risk badges; click-through to patient profiles |
| Doctor Reports | `/dashboard/doctor/reports` | Doctor | List of generated PDF reports; `ReportCard` + `ReportViewer` |
| Doctor Chat | `/dashboard/doctor/chat` | Doctor | Full agentic chat; supports X-ray/DICOM upload via drag-and-drop; shows `MultiAgentInsights` panel |
| Patient Overview | `/dashboard/patient` | Patient | Summary of recent reports and session status |
| Patient Reports | `/dashboard/patient/reports` | Patient | Patient-facing report list |
| Patient Chat | `/dashboard/patient/chat` | Patient | Agentic chat for self-service analysis |
| Nearby Hospitals | `/dashboard/patient/nearby` | Patient | Interactive hospital finder using geolocation |

### 10.3 Key Components

**AI Elements (`components/ai-elements/`):**
- `MultiAgentInsights.tsx` — Displays real-time multi-agent status: agent count, coordination metrics, consensus history, per-agent goals. Polls `/api/multi_agent/status` and `/api/multi_agent/consensus/history`.
- `conversation.tsx` — Scrollable conversation thread.
- `message.tsx` — Individual message bubble with Markdown rendering via `streamdown`.
- `prompt-input.tsx` — Prompt text area with send button.
- `reasoning.tsx` — Collapsible agent reasoning trace panel.
- `shimmer.tsx` — Loading skeleton.

**Chat (`components/chat/`):**
- `ChatWindow.tsx` — Main chat container; manages session creation, message sending, attachment handling, and streaming.
- `ChatInput.tsx` — Input box with attach button; supports multi-file upload.
- `MessageBubble.tsx` — Role-differentiated message rendering.
- `AttachmentPreview.tsx` — Image/DICOM attachment preview thumbnail.

**Upload (`components/upload/`):**
- `FileDropzone.tsx` — React Dropzone wrapper; accepts images and DICOM/ZIP files.
- `XrayUploader.tsx` — Specialized uploader that previews an X-ray and sends it to the analyze endpoint.

**Layout (`components/layout/`):**
- `DashboardShell.tsx` — Wraps all dashboard pages with Sidebar + Header.
- `Sidebar.tsx` — Role-aware navigation sidebar (different links for doctor vs. patient).
- `Header.tsx` — Top bar with user avatar, theme toggle, and data source toggle.
- `DataSourceToggle.tsx` — Switches between `mock` and `api` data modes (controlled by `NEXT_PUBLIC_DATA_SOURCE` env var).
- `AppFloatingNavbar.tsx` / `AppResizableNavbar.tsx` — Landing page navigation variants.

**Patients (`components/patients/`):**
- `DoctorPatientsPanel.tsx` — Full patient panel with list, search, and profile view.
- `PatientList.tsx` — Sortable/filterable patient list with risk badges.
- `PatientProfile.tsx` — Detailed patient view with analysis history and report links.

**Reports (`components/reports/`):**
- `ReportCard.tsx` — Summary card showing report title, date, severity, and PDF link.
- `ReportViewer.tsx` — Embedded PDF viewer.

**Auth (`components/auth/`):**
- `RoleSelectionScreen.tsx` — Presented after first Clerk login; stores role selection to Clerk session claims.

### 10.4 Hooks

| Hook | File | Description |
|---|---|---|
| `useChat` | `hooks/useChat.ts` | Manages chat session state: creates sessions, sends messages, handles streaming responses, tracks attachment state |
| `usePatients` | `hooks/usePatients.ts` | Fetches patient list from `/api/patients` using TanStack Query; handles loading and error states |
| `useReports` | `hooks/useReports.ts` | Fetches report list from `/api/reports`; supports refetch on report generation |

### 10.5 State Management

- **Zustand** (`store/ui.store.ts`) — global UI state: sidebar open/close, current theme, data source mode.
- **TanStack Query** — server state for patients, reports, and multi-agent status polling.
- **React local state** — chat message list, session ID, attachment previews within chat components.

### 10.6 API Client and Auth Utilities

- `lib/api.ts` — Axios instance with `baseURL = NEXT_PUBLIC_API_BASE_URL/api` (default `http://localhost:8000/api`) and 30-second timeout.
- `lib/auth.ts` — Clerk session helpers; extracts `actor_id`, `actor_role`, and `actor_name` from Clerk session claims.
- `lib/rbac.ts` — Role-based access control helpers; guards routes based on Clerk role.
- `lib/constants.ts` — Application-wide string constants and route paths.
- `lib/validators.ts` — Zod schemas for form validation.
- `lib/utils.ts` — `cn()` (clsx + tailwind-merge) and other utility functions.

---

## 11. Data Flow — End-to-End

### 11.1 X-ray Analysis Flow

```
User (browser)
  │  POST /api/analyze  {image_data: base64, symptoms, session_id}
  ▼
FastAPI /analyze endpoint
  │  Decodes DICOM if present (dicom_utils)
  │  Detects modality (xray by default if image_data present)
  │  Calls run_agent(payload)
  ▼
LangGraph graph.ainvoke(state)
  ├── multi_agent_integrator (if enabled)
  │     └── agent_coordinator.coordinate_analysis()
  │           └── All 7 agents: perceive → reason → goals → collaborate → consensus
  │
  └── supervisor_node
        │  Binds ALL_TOOLS to GPT-4o
        │  Builds system prompt with learning insights
        │  LLM decides: call vision_detect_body_part
        ▼
      tool_executor_node
        │  Calls vision_detect_body_part → {body_part: "hand"}
        │  Updates state.body_part
        ▼
      supervisor_node (iteration 2)
        │  LLM decides: call vision_detect_hand_fracture
        ▼
      tool_executor_node
        │  Calls vision_detect_hand_fracture → {detections: [...]}
        ▼
      supervisor_node (iteration 3)
        │  LLM decides: call clinical_generate_diagnosis
        ▼
      tool_executor_node
        │  Calls clinical_generate_diagnosis → {diagnosis: {...}}
        ▼
      supervisor_node (iteration 4)
        │  LLM decides: call clinical_assess_triage
        ▼
      tool_executor_node
        │  Calls clinical_assess_triage → {triage_result: {level: "AMBER"}}
        ▼
      should_continue → care_plan_node
        ├── TreatmentPlannerAgent: perceive → reason → act → treatment_plan
        ├── RehabilitationAgent: perceive → reason → act → rehabilitation_plan
        ├── PatientEducationAgent: perceive → reason → act → patient_education
        └── AppointmentAgent: perceive → reason → act → appointment_schedule
        ▼
      response_builder_node
        │  Synthesizes final_response from all structured data
        ▼
FastAPI endpoint
  │  Calls adaptive_supervisor.learn_from_execution(result)
  │  Builds annotated_image_base64
  │  Returns AgentResponse JSON
  ▼
Frontend
  │  Renders diagnosis, triage badge, annotated image, care plan
```

### 11.2 Chat Message Flow

The chat endpoint (`POST /api/chat/sessions/{chat_id}/messages`) adds several layers around the core agent:

1. **Attachment classification** — detects image vs. DICOM vs. other using magic bytes and MIME type.
2. **DICOM ingestion** — if DICOM or ZIP, extracts all DICOM files, normalizes the series, converts to NIfTI if CT/MRI.
3. **Patient info extraction** — regex-based extraction of name, age, gender, and doctor from conversation history and current message.
4. **Pipeline state restore** — loads `diagnosis`, `triage_result`, `body_part`, `patient_info`, and `pending_report_actor_role` from MongoDB (persisted from the previous turn).
5. **Fast-path check** — if the message contains only patient intake info (name/age/gender) and no analysis/report keywords, a direct acknowledgment is returned without invoking the agent graph.
6. **Agent invocation** — `run_agent(payload)` with full history injected as LangChain messages.
7. **Pipeline state save** — persists updated clinical state back to MongoDB so the next turn has context.
8. **Patient upsert** — creates or updates MongoDB patient record when all intake fields are present.
9. **Report fallback** — if a report was requested but the agent didn't generate one, the endpoint directly calls `generate_comprehensive_pdf_impl`.
10. **Report save** — saves generated PDF URL to MongoDB reports collection.
11. **Message persistence** — appends user and assistant messages to `chat_messages`.

### 11.3 Agent Collaboration Flow

When `settings.multi_agent_enabled = True` and the `multi_agent_integrator` node runs:

```
context from AgentState
  ▼
MultiAgentCoordinator.coordinate_analysis(context)
  ├── Phase 1: all 7 agents perceive() concurrently
  │     VisionAgent.perceive()     → {has_image, existing_detections, ...}
  │     ClinicalAgent.perceive()   → {detections, patient_info, ...}
  │     TreatmentPlannerAgent.perceive() → {diagnosis, triage, ...}
  │     [4 more agents]
  │
  ├── Phase 2: all 7 agents reason() concurrently
  │     Each produces {recommended_actions: [...], collaboration_needs: [...], confidence}
  │
  ├── Phase 3: all 7 agents formulate_goals() concurrently
  │     AgentGoal objects with priority, objective, success_criteria
  │
  ├── Phase 4: _facilitate_collaboration()
  │     _identify_collaboration_needs() checks vision + clinical reasoning outputs
  │     → vision_clinical_collaboration if mutual verification needed
  │     → multi_agent_consensus if total needs > 2
  │     _handle_multi_agent_consensus():
  │       Each participant generates consensus assessment
  │       Confidence range evaluated (gap < 0.2 = consensus)
  │       ConsensusResult stored in consensus_history
  │
  ├── Phase 5: _execute_collaborative_actions()
  │
  └── Phase 6: _build_agent_consensus()
        Returns {consensus_reached, final_decision, confidence, participants}

  ▼
multi_agent_integration_node extracts:
  consensus_recommendation.tool → supervisor can bias tool selection
  agent_perceptions → enriched context
  collaborative_opportunities → logged
  
  ▼
state.multi_agent_insights populated
state.multi_agent_coordination populated
  ▼
supervisor_node reads multi_agent_insights in system prompt
```

### 11.4 Report Generation Flow

```
User message: "generate a report" (or "PDF" or "document")
  ▼
chat endpoint: _report_requested(message) = True
  ▼
Agent graph runs; supervisor calls:
  report_generate_comprehensive_pdf(diagnosis, triage, patient_info, actor_role,
    image_base64, annotated_image_base64, treatment_plan, rehabilitation_plan,
    patient_education, appointment_schedule)
  ▼
comprehensive_pdf.py:
  └── pdf_engine.py builds ReportLab PDF with:
        - Cover: patient info, body part, date
        - Findings: detection table with confidence scores
        - Diagnosis: summary, severity, ICD context
        - Triage: level badge, recommended timeframe
        - Images: original + annotated X-ray embedded
        - Care Plan: treatment, rehab, patient education, appointments
        - Disclaimer: AI-generated content notice
  └── storage_service.save_pdf() → public_url
  └── patient_store.save_report() → MongoDB
  ▼
AgentResponse.report_url returned to frontend
  ▼
Frontend renders clickable PDF link in chat bubble
```

---

## 12. Technologies and Dependencies

### 12.1 Backend Dependencies

| Category | Library | Version | Role |
|---|---|---|---|
| API framework | FastAPI | ≥0.115 | HTTP API server |
| ASGI server | Uvicorn | ≥0.32 | Production-grade ASGI server |
| Agent orchestration | LangGraph | ≥0.2 | StateGraph-based agent pipeline |
| LLM interface | LangChain | ≥0.3 | Tool binding, message types |
| LLM interface | langchain-openai | ≥0.2 | ChatOpenAI wrapper for GPT-4o |
| Observability | LangSmith | ≥0.2 | Agent run tracing |
| MCP protocol | mcp | ≥1.0 | Model Context Protocol server |
| Computer vision | Ultralytics (YOLOv8) | ≥8.3 | X-ray fracture detection |
| Deep learning | PyTorch | ≥2.1 | Model inference backend |
| CT segmentation | TotalSegmentator | ≥2.7 | Bone segmentation in CT volumes |
| CT segmentation | nnunetv2 | ≥2.6 | VerSe nnUNet for spine |
| MRI segmentation | kneeseg | ≥0.1.3 | Knee cartilage segmentation |
| DICOM processing | pydicom | ≥3.0 | DICOM file parsing |
| Medical imaging | SimpleITK | ≥2.3 | NIfTI conversion and resampling |
| Medical imaging | nibabel | ≥5.2 | NIfTI volume I/O |
| Image processing | Pillow | ≥10.0 | Image conversion and encoding |
| Image processing | OpenCV | 4.10.0.84 (headless) | Annotation drawing |
| PDF generation | ReportLab | ≥4.2 | PDF report rendering |
| Database (async) | Motor | ≥3.6 | Async MongoDB driver |
| Cloud storage | Cloudinary | ≥1.41 | Optional cloud file storage |
| Data validation | Pydantic | ≥2.9 | Schema validation and settings |
| Settings | pydantic-settings | ≥2.6 | Environment variable loading |
| Logging | loguru | ≥0.7 | Structured logging with log interception |
| HTTP client | httpx | ≥0.27 | Async HTTP for external calls |
| Auth | python-jose | ≥3.3 | JWT signing/verification |
| Auth | passlib | ≥1.7 | Password hashing utilities |
| Async I/O | aiofiles | ≥24.1 | Async file operations |

### 12.2 Frontend Dependencies

| Category | Library | Version | Role |
|---|---|---|---|
| Framework | Next.js | ^16.1.6 | React framework with App Router |
| Auth | @clerk/nextjs | ^6.38.2 | Authentication and session management |
| State | Zustand | ^4.5.4 | Global UI state management |
| Server state | @tanstack/react-query | ^5.45 | Data fetching and caching |
| UI components | Radix UI (multiple) | various | Accessible headless primitives |
| Styling | Tailwind CSS | ^3.4 | Utility-first CSS framework |
| Animation | Framer Motion | ^11.3 | Page and component animations |
| Animation | motion | ^12.34 | Lower-level motion primitives |
| Icons | Lucide React | ^0.575 | Icon set |
| Icons | @tabler/icons-react | ^3.37 | Extended icon set |
| HTTP client | Axios | ^1.7 | API communication |
| Streaming | ai (Vercel AI SDK) | ^6.0 | AI streaming response utilities |
| Markdown | streamdown | ^2.3 | Streaming markdown renderer |
| File upload | react-dropzone | ^14.2 | Drag-and-drop file upload |
| Toast notifications | sonner | ^1.5 | Toast notification system |
| Utilities | clsx + tailwind-merge | — | Conditional class composition |
| Validation | zod | ^3.23 | Runtime schema validation |
| Date utilities | date-fns | ^3.6 | Date formatting |

---

## 13. Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `dev` | Environment (`dev` or `production`) |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server bind port |
| `DEBUG` | `False` | Enable debug/reload mode |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed CORS origin |
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `SUPERVISOR_LLM` | `gpt-4o` | Model for the supervisor node |
| `FAST_LLM` | `gpt-4o-mini` | Model for fast synthesis tasks |
| `LANGCHAIN_TRACING_V2` | `true` | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | — | LangSmith API key |
| `LANGCHAIN_PROJECT` | `orthoassist-dev` | LangSmith project name |
| `MONGODB_URI` | — | MongoDB connection string |
| `MONGODB_DB_NAME` | `orthoassist` | MongoDB database name |
| `STORAGE_TYPE` | `local` | `local` or `cloudinary` |
| `STORAGE_PATH` | `./storage` | Base path for local file storage |
| `CLOUDINARY_URL` | — | Cloudinary connection URL (if cloudinary) |
| `SECRET_KEY` | `change-me` | JWT signing secret |
| `MAX_AGENT_ITERATIONS` | `10` | Maximum LangGraph supervisor iterations |
| `SESSION_TTL_SECONDS` | `3600` | MemorySaver session TTL in seconds |
| `MULTI_AGENT_ENABLED` | `False` | Enable multi-agent integration node |
| `MULTI_AGENT_CONFIDENCE_THRESHOLD` | `0.8` | Minimum consensus confidence |
| `TOTALSEGMENTATOR_DEVICE` | `cpu` | `cpu` or `cuda:0` for CT/MRI inference |
| `TOTALSEGMENTATOR_FAST` | `True` | Use 3mm fast mode for TotalSegmentator |
| `CT_MAX_VOLUME_MB` | `500` | Max CT volume size in MB |
| `MRI_MAX_VOLUME_MB` | `500` | Max MRI volume size in MB |
| `CHAT_REQUEST_TIMEOUT_SECONDS` | `45` | Timeout for standard chat requests |
| `VOLUMETRIC_CHAT_TIMEOUT_SECONDS` | `7200` | Timeout for CT/MRI chat requests |
| `PHI_REDACTION_ENABLED` | `True` | Redact PHI from responses |
| `MEDICAL_DISCLAIMER_ENABLED` | `True` | Append AI content disclaimers |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | — | Clerk publishable key (required) |
| `CLERK_SECRET_KEY` | — | Clerk secret key (required) |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend API base URL |
| `NEXT_PUBLIC_DATA_SOURCE` | `mock` | `mock` (dev without backend) or `api` (live backend) |

---

## 14. Setup and Installation

### 14.1 Backend

**Prerequisites:** Python 3.11.x, MongoDB (local or Atlas), OpenAI API key.

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, MONGODB_URI, and any other required values

# Start the server
uvicorn main:app --reload
# API available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

**YOLO models:** Place `hand_yolo.pt` and `leg_yolo.pt` in `backend/models/`. These are not tracked in git due to file size.

**TotalSegmentator:** On first CT/MRI analysis request, TotalSegmentator will download its model weights automatically (~2-3 GB). Set `TOTALSEGMENTATOR_DEVICE=cuda:0` if a CUDA GPU is available for significantly faster inference.

**MCP server (separate process):**
```bash
cd backend
python -m mcp.server
```

### 14.2 Frontend

**Prerequisites:** Node.js 20+, Clerk account.

```bash
cd frontend

npm install

# Configure environment
# Create frontend/.env.local with Clerk keys and API URL

npm run dev
# App available at http://localhost:3000
```

For production build:
```bash
npm run build
npm start
```

---

## 15. MongoDB Collections

| Collection | Key Indexes | Notes |
|---|---|---|
| `chat_sessions` | `chat_id` (unique), `(owner_user_id, last_message_at)`, `(patient_id, last_message_at)`, `(doctor_id, last_message_at)` | Stores session metadata and embedded pipeline state via `$set` |
| `chat_messages` | `message_id` (unique), `(chat_id, created_at)` | Full message history with attachments and traces |
| `chat_traces` | `chat_id` | Agent execution trace logs |
| `chat_pipeline_state` | `chat_id` | Persisted clinical pipeline state across turns |
| `patients` | `patient_id` | Demographics and analysis history array |
| `reports` | `patient_id`, `doctor_user_id` | Report metadata and PDF URLs |
| `agent_patterns` | `pattern_id` (upsert key) | Learned experience patterns from AdaptiveSupervisor |
| `tool_beliefs` | `tool_name` (upsert key) | Bayesian Beta distribution parameters per tool |
| `kb_documents` | `document_id` | RAG document index |
| `kb_chunks` | `(patient_id, text regex)` | RAG text chunks for retrieval |

---

## 16. YOLO Models

| Model File | Purpose | Architecture |
|---|---|---|
| `backend/models/hand_yolo.pt` | Detects fractures and anatomical landmarks in hand X-rays | YOLOv8 (custom-trained) |
| `backend/models/leg_yolo.pt` | Detects fractures and anatomical landmarks in leg/foot X-rays | YOLOv8 (custom-trained) |

Both models are loaded lazily on first use by `yolo_runtime.py` and cached in memory. A routing model run by `body_part_detector.py` first classifies the X-ray as `hand` vs. `leg` before selecting the appropriate specialized model.

---

## 17. Detection Thresholds and Tuning Knobs

| Setting | Default | Effect |
|---|---|---|
| `router_threshold` | `0.70` | Minimum confidence for body-part routing; below this, the agent requests clarification |
| `detector_score_min` | `0.35` | Minimum YOLO detection score; detections below this are discarded |
| `nms_iou` | `0.50` | Non-maximum suppression IoU threshold; controls detection deduplication |
| `triage_red_threshold` | `0.80` | Severity scores above this map to RED triage |
| `triage_amber_threshold` | `0.60` | Severity scores above this map to AMBER triage |
| `multi_agent_confidence_threshold` | `0.80` | Minimum confidence for multi-agent consensus to be acted upon |
| `max_agent_iterations` | `10` | Hard cap on supervisor loop iterations before error handler is invoked |
| `totalsegmentator_fast` | `True` | `True` uses 3mm resolution (much faster on CPU); `False` uses 1.5mm (higher quality) |

---

## 18. Security Considerations

- **Authentication:** All frontend routes are guarded by Clerk. Session claims include `actor_role` (`doctor` or `patient`). The backend does not re-validate Clerk tokens directly but enforces RBAC rules based on `actor_role` and `actor_id` passed in request bodies.
- **Doctor-patient assignment:** Doctors can only access chat sessions where they are the assigned doctor, enforced in `chat_store.is_patient_assigned()` and `_ensure_session_access()`.
- **PHI redaction:** `phi_redaction_enabled = True` (default) instructs the LLM system prompt to redact protected health information from AI-generated text.
- **Medical disclaimer:** `medical_disclaimer_enabled = True` appends a standard disclaimer to all AI-generated clinical content.
- **CORS:** In production, restricted to the explicit `FRONTEND_URL`. In dev, defaults to `["*"]`.
- **JWT secret:** `SECRET_KEY` must be changed from the default `"change-me"` in any non-dev deployment.
- **DICOM path traversal:** The `/storage/` static file endpoint uses `Path.relative_to()` to guard against path traversal attacks when resolving attachment URLs.
- **Volumetric upload limits:** `ct_max_volume_mb` and `mri_max_volume_mb` cap file sizes to prevent denial-of-service via large DICOM uploads.

---

## 19. Known Gaps and Documentation Notes

- **LLM provider naming:** `backend/services/groq_llm.py` is named after Groq but the implementation uses `langchain_openai.ChatOpenAI`. The Groq integration may be a planned or historical artifact — the actual model is fully controlled by `SUPERVISOR_LLM` and `FAST_LLM` environment variables.
- **Mock data mode:** The frontend supports a `NEXT_PUBLIC_DATA_SOURCE=mock` mode for development without a live backend, but the mock data layer itself is not fully documented here as it is UI-internal.
- **RAG store is keyword-based:** The current `rag_store.py` uses regex token matching, not vector embeddings. A vector-based RAG upgrade (e.g., using LangChain vector stores with OpenAI embeddings) is noted in the roadmap (`ROADMAP.md`).
- **Hospital data:** The `hospital/data.py` module contains static hospital records. Integration with a live geo-lookup API (e.g., Google Places) is handled by the Next.js `/api/nearby` route handler, which wraps an external call.
- **MCP tool count:** The README states 22 tools; the actual registry as of this analysis contains 30+ tools across 8 namespaces. The discrepancy reflects tools added since the README was last updated.
- **multi_agent_enabled is `False` by default:** The multi-agent integration node is a feature-flagged experimental capability. All production traffic by default runs through the standard supervisor-only pipeline without multi-agent overhead.
- **Feedback endpoint:** `backend/api/endpoints/feedback.py` has a `.backup` file alongside it, suggesting the feedback schema was recently refactored. The `AgentFeedback` Pydantic schema in `api/schemas/feedback.py` defines the canonical structure.
- **Python version pin:** The backend requires exactly Python 3.11.x (enforced at runtime startup). Python 3.12+ and 3.10- are explicitly rejected due to dependencies with strict ABI requirements (TotalSegmentator, nnunetv2).
