# OrthoAssist

An AI-powered orthopedic diagnostic platform. Doctors upload X-rays, the agentic backend runs YOLOv8 detection, invokes clinical reasoning tools via LangGraph, and returns structured reports. Patients and doctors interact through a role-aware chat interface backed by the same agent graph.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│       Next.js Frontend      │    Claude Desktop / Cursor IDE     │
└──────────────┬──────────────┴──────────────┬────────────────────┘
               │ HTTP / REST                  │ MCP Protocol
               ▼                              ▼
┌──────────────────────┐    ┌────────────────────────────────────┐
│   FastAPI  (:8000)   │    │   MCP Server (stdio / SSE)         │
│   /api/analyze       │    │   22 tools via @mcp.tool()         │
│   /api/chat          │    │   Namespaced: vision.* clinical.*  │
│   /api/reports       │    └──────────────┬─────────────────────┘
│   /api/patients      │                   │
└──────────┬───────────┘                   │
           │             both call          │
           ▼                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    LangGraph  StateGraph                      │
│   Supervisor  →  Tool Executor  →  Response Builder          │
│         ↑               │                                    │
│   sub-agents:  vision · clinical · knowledge                 │
│                report  · hospital                            │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
  YOLOv8 detection · RAG (knowledge base) · MongoDB · Cloudinary
```

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API server | FastAPI + Uvicorn |
| Agent orchestration | LangGraph + LangChain |
| LLM | OpenAI GPT-4o / GPT-4o-mini |
| Observability | LangSmith |
| MCP server | Python MCP SDK |
| Computer vision | YOLOv8 (Ultralytics) — separate hand & leg models |
| Database | MongoDB (Motor async driver) |
| Storage | Local filesystem or Cloudinary |
| Report generation | ReportLab PDF |
| Auth utils | python-jose + passlib |

### Frontend
| Layer | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Auth | Clerk |
| UI components | shadcn/ui + Radix UI + Tailwind CSS |
| State | Zustand + TanStack Query |
| Animations | Framer Motion |
| Icons | Lucide React + Tabler Icons |
| Streaming | Vercel AI SDK |

---

## Features

- **X-ray Analysis** — Upload hand or leg X-rays; YOLO detects anatomical regions, the supervisor agent selects the right clinical tools and returns a triage result.
- **Agentic Chat** — Persistent, session-scoped chat backed by LangGraph. The LLM decides which tools to call; no hardcoded pipeline.
- **Role-based Dashboard** — Doctor and patient roles enforced at the middleware level via Clerk session claims. Each role sees only its permitted routes and data.
- **Patient Management** — Doctors can create and view patient records.
- **Report Generation** — Structured PDF reports generated from agent output, stored in MongoDB and retrievable from the dashboard.
- **MCP Server** — All 22 tools are also exposed as an MCP server, making them callable from Claude Desktop, Cursor, or any MCP-compatible client.
- **LangSmith Tracing** — Every agent run is traced: node decisions, tool calls, token counts, and latency.

---

## Project Structure

```
OrthoAssist/
├── backend/
│   ├── main.py                  # FastAPI app factory + lifespan
│   ├── core/                    # Config (pydantic-settings), logging, exceptions
│   ├── api/
│   │   ├── router.py            # Mounts all endpoint routers
│   │   ├── middleware.py        # CORS, request logging
│   │   ├── endpoints/           # analyze, chat, health, knowledge, metrics, reports, patients
│   │   └── schemas/             # Pydantic request/response models
│   ├── graph/
│   │   ├── graph.py             # LangGraph StateGraph definition
│   │   ├── state.py             # Shared AgentState TypedDict
│   │   ├── checkpointer.py      # MemorySaver session checkpointing
│   │   └── nodes/               # supervisor, tool_executor, response_builder, error_handler
│   ├── agents/                  # Sub-agent wrappers: vision, clinical, knowledge, report, hospital
│   ├── tools/                   # Pure async tool implementations (clinical/, vision/, report/, ...)
│   ├── mcp/
│   │   ├── server.py            # MCP server entry point
│   │   └── registry.py          # Tool registration
│   ├── services/                # mongo, storage, rag_store, chat_store, session, patient_store
│   └── models/                  # hand_yolo.pt, leg_yolo.pt
│
└── frontend/
    ├── app/                     # Next.js App Router pages
    │   ├── (auth)/              # Clerk sign-in / sign-up
    │   ├── select-role/         # Role selection after first login
    │   └── dashboard/
    │       ├── doctor/          # patients, reports, chat, settings
    │       └── patient/         # reports, chat, nearby hospitals
    ├── components/              # chat, upload, reports, patients, landing, layout, ui
    ├── hooks/                   # useChat, useReports, usePatients
    ├── lib/                     # api client, auth, RBAC helpers, validators
    └── store/                   # Zustand UI store
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB instance (local or Atlas)
- OpenAI API key
- Clerk account (for frontend auth)

### Backend

```bash
cd backend

# create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# install dependencies
pip install -r requirements.txt

# copy and fill in environment variables
cp .env.example .env

# run
uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Frontend

```bash
cd frontend

npm install

# copy and fill in environment variables
cp .env.example .env.local

npm run dev
# → http://localhost:3000
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `APP_ENV` | `dev` or `production` |
| `OPENAI_API_KEY` | OpenAI key for the supervisor LLM |
| `SUPERVISOR_LLM` | Model name, default `gpt-4o` |
| `FAST_LLM` | Faster model for cheaper tasks, default `gpt-4o-mini` |
| `LANGCHAIN_API_KEY` | LangSmith API key |
| `LANGCHAIN_PROJECT` | LangSmith project name |
| `MONGODB_URI` | MongoDB connection string |
| `MONGODB_DB_NAME` | Database name, default `orthoassist` |
| `STORAGE_TYPE` | `local` or `cloudinary` |
| `CLOUDINARY_URL` | Required when `STORAGE_TYPE=cloudinary` |
| `SECRET_KEY` | JWT signing secret |
| `FRONTEND_URL` | Allowed CORS origin in production |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key |
| `CLERK_SECRET_KEY` | Clerk secret key |
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL, default `http://localhost:8000` |
| `NEXT_PUBLIC_DATA_SOURCE` | `mock` (dev) or `api` (production) |

---

## API Overview

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analyze` | Upload X-ray image, run full agent analysis |
| `POST` | `/api/chat` | Send message to agent graph (streaming) |
| `GET` | `/api/reports` | List reports for current session |
| `GET` | `/api/reports/{id}` | Fetch single report |
| `GET` | `/api/patients` | List patients (doctor only) |
| `POST` | `/api/patients` | Create patient record |
| `GET` | `/api/knowledge` | Query the orthopedic knowledge base (RAG) |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/metrics` | Agent run metrics |

Full interactive docs available at `http://localhost:8000/docs` when running locally.

---

## Agent Tools (22 total)

| Namespace | Tools |
|---|---|
| `vision.*` | `detect_xray_region`, `classify_fracture`, `annotate_image`, `route_by_body_part` |
| `clinical.*` | `triage_severity`, `suggest_treatment`, `flag_contraindications`, `differential_diagnosis` |
| `knowledge.*` | `search_ortho_kb`, `retrieve_drug_info`, `lookup_icd_code` |
| `report.*` | `generate_pdf_report`, `summarize_findings`, `format_for_ehr` |
| `hospital.*` | `find_nearby_hospitals`, `check_specialist_availability`, `get_emergency_contacts` |

All tools are registered on both the LangGraph tool executor and the MCP server.

---

## Development Notes

- **LangSmith tracing** is on by default in dev. Set `LANGCHAIN_TRACING_V2=false` to disable.
- **Mock data mode**: set `NEXT_PUBLIC_DATA_SOURCE=mock` in `.env.local` to run the frontend without a live backend.
- **YOLO models** (`hand_yolo.pt`, `leg_yolo.pt`) must be present in `backend/models/`. They are not tracked in git due to size.
- Session memory uses LangGraph `MemorySaver` with a TTL of 1 hour (`SESSION_TTL_SECONDS=3600`).
