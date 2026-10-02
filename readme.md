# OrthoAssist

**Doctor-reviewed orthopedic X-ray reports, drafted faster.**

Upload a deidentified hand/wrist or leg/ankle X-ray, add clinical context, and review an AI-assisted structured report.

> For clinician review only. Not for emergency use or autonomous diagnosis.

## Pilot Scope

OrthoAssist currently targets licensed orthopedic clinicians at a small Indian clinic. The live workflow is intentionally narrow:

1. A manually provisioned doctor signs in with Clerk.
2. OrthoAssist creates or selects a deidentified case code.
3. The doctor confirms that one PNG/JPEG X-ray is deidentified and uploads it.
4. The doctor adds clinical context.
5. The existing hand or leg YOLO model supplies observations to the agent workflow.
6. OrthoAssist creates an editable, doctor-reviewed draft.
7. The doctor downloads the protected `clinician_simple_pdf` report.

Do not use real patient identifiers in the pilot. Name, date of birth, phone, email, patient accounts, emergency workflows, automated diagnosis, CT/MRI/DICOM, and third-party imaging APIs are out of scope.

## Live Surface

Only these API surfaces are registered:

| Method | Path | Access |
|---|---|---|
| `GET` | `/api/health` | Public |
| `GET` | `/api/dashboard/doctor` | Doctor token |
| `GET/DELETE` | `/api/patients...` | Owning doctor token |
| `GET/POST` | `/api/chat/sessions...` | Owning doctor token |
| `GET` | `/api/reports/list` | Doctor token |
| `GET` | `/api/reports/{report_id}` | Owning doctor token |
| `GET` | `/api/reports/{report_id}/pdf` | Owning doctor token |

Experimental analysis, CT/MRI/DICOM, nearby care, knowledge ingestion, feedback learning, metrics, and multi-agent modules remain in source but are not mounted by `backend/api/router.py`.

## Security Baseline

- Every live endpoint except health requires a Clerk bearer session token.
- The backend verifies RS256, issuer, expiration, `nbf`, authorized party (`azp`), subject, and the server-controlled `role` claim.
- Submitted identity fields, role cookies, and Clerk unsafe metadata are not authorization inputs.
- Case, chat, and report access is checked against the authenticated doctor ID.
- Local storage is not statically mounted. Report files are streamed only through the owner-checked API route.
- Uploads accept one strict base64 PNG/JPEG, up to 20 MiB decoded and 64 megapixels. URLs, PDFs, archives, DICOM, malformed images, and multiple attachments are rejected.
- FastAPI rejects request bodies over 30 MiB.
- Production startup rejects wildcard CORS and missing Clerk or MongoDB security configuration.

## Stack

- Backend: Python 3.11, FastAPI, LangGraph, python-jose, MongoDB, Pillow, Ultralytics YOLO, ReportLab
- Frontend: Next.js App Router, Clerk, TypeScript, Tailwind CSS
- Models: existing `backend/models/hand_yolo.pt` and `backend/models/leg_yolo.pt`

## Setup

### Backend

Install and pin the supported runtime with `uv`:

```powershell
cd backend
uv python install 3.11
uv sync --python 3.11
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Set at least these values in `backend/.env`:

```dotenv
APP_ENV=dev
FRONTEND_URL=http://localhost:3000
CORS_ALLOW_ORIGINS=http://localhost:3000
OPENAI_API_KEY=...
MONGODB_URI=...
MONGODB_DB_NAME=orthoassist
CLERK_JWT_KEY="-----BEGIN PUBLIC KEY-----\\n...\\n-----END PUBLIC KEY-----"
CLERK_ISSUER=https://your-instance.clerk.accounts.dev
CLERK_AUTHORIZED_PARTIES=http://localhost:3000
```

### Clerk Doctor Provisioning

Self-service role selection is disabled. Provision each pilot clinician manually:

1. In the Clerk dashboard, set the user's public metadata to `{"role":"doctor"}`.
2. Under session token customization, add the top-level claim `{"role":"{{user.public_metadata.role}}"}`.
3. Configure `CLERK_ISSUER` and the PEM public key for the same Clerk instance.
4. Add every legitimate frontend origin to `CLERK_AUTHORIZED_PARTIES` and `CORS_ALLOW_ORIGINS` as comma-separated values.
5. Sign out and back in after changing metadata so Clerk issues a new session token.

Do not accept role changes from browser forms, cookies, or unsafe metadata.

### Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

`NEXT_PUBLIC_API_BASE_URL` must include the `/api` prefix, for example `http://localhost:8000/api`.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run typecheck
npm run lint
```

## Pilot Data Cleanup

Case deletion removes linked MongoDB records and local X-rays/PDFs. There is no automated retention worker in this sprint. Record the pilot end date and, within 30 days, have the clinic operator delete every pilot case through the doctor dashboard and verify that the MongoDB case collections and `backend/storage` contain no pilot records. Keep a dated checklist of that manual verification.

Real patient data requires a separate DPDP operational, consent, retention, breach-response, and vendor review before use.
