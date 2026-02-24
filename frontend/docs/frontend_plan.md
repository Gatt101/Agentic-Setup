# Frontend Plan (Next.js App Router)

## 1. Frontend Folder Structure

```text
ortho-frontend/
|
|-- app/
|   |-- layout.tsx                 # Root layout (theme, ClerkProvider)
|   |-- page.tsx                   # Landing page
|   |-- globals.css                # Tailwind base + tokens
|   |
|   |-- (auth)/
|   |   |-- sign-in/[[...sign-in]]/page.tsx
|   |   `-- sign-up/[[...sign-up]]/page.tsx
|   |
|   |-- dashboard/
|   |   |-- layout.tsx             # Dashboard shell (sidebar + header)
|   |   |-- page.tsx               # Redirect by role (doctor/patient)
|   |   |
|   |   |-- doctor/
|   |   |   |-- page.tsx           # Doctor home
|   |   |   |-- patients/page.tsx
|   |   |   |-- reports/page.tsx
|   |   |   |-- chat/page.tsx
|   |   |   `-- settings/page.tsx
|   |   |
|   |   `-- patient/
|   |       |-- page.tsx           # Patient home
|   |       |-- reports/page.tsx
|   |       |-- chat/page.tsx
|   |       `-- nearby/page.tsx
|   |
|   `-- api/                       # Optional Next API (proxy layer)
|
|-- components/
|   |-- layout/
|   |   |-- Sidebar.tsx
|   |   |-- Header.tsx
|   |   `-- DashboardShell.tsx
|   |
|   |-- chat/
|   |   |-- ChatWindow.tsx
|   |   |-- ChatInput.tsx
|   |   |-- MessageBubble.tsx
|   |   `-- AttachmentPreview.tsx
|   |
|   |-- upload/
|   |   |-- XrayUploader.tsx
|   |   `-- FileDropzone.tsx
|   |
|   |-- reports/
|   |   |-- ReportCard.tsx
|   |   `-- ReportViewer.tsx
|   |
|   |-- patients/
|   |   |-- PatientList.tsx
|   |   `-- PatientProfile.tsx
|   |
|   `-- ui/                        # shadcn/ui customized components
|       |-- button.tsx
|       |-- card.tsx
|       `-- modal.tsx
|
|-- icons/                         # Custom SVG icons (bone, xray, hospital, report)
|   |-- BoneIcon.tsx
|   |-- XrayIcon.tsx
|   |-- HospitalIcon.tsx
|   `-- ReportIcon.tsx
|
|-- lib/
|   |-- api.ts                     # API client (fetch wrappers)
|   |-- auth.ts                    # RBAC helpers
|   |-- rbac.ts                    # role checks, guards
|   |-- constants.ts               # routes, roles
|   `-- validators.ts              # zod schemas
|
|-- hooks/
|   |-- useChat.ts
|   |-- useReports.ts
|   `-- usePatients.ts
|
|-- store/
|   `-- ui.store.ts                # Zustand for UI state (sidebar, modals)
|
|-- styles/
|   `-- theme.css                  # CSS variables for colors, radii
|
|-- public/
|   `-- mockups/                   # landing visuals
|
`-- middleware.ts                  # Route protection (RBAC)
```

### Practical Additions for Working Repo
- Added `frontend/.gitignore` to ignore `node_modules`, `.next`, logs, and local env files.
- `package-lock.json` is generated and maintained by `npm install`.
- Added `.gitkeep` in `app/api` and `public/mockups` so empty planned folders stay tracked in git.
- Added required Next.js/Tailwind root config files for tooling compatibility:
  - `next.config.mjs`
  - `tsconfig.json`
  - `next-env.d.ts`
  - `tailwind.config.ts`
  - `postcss.config.cjs`
  - `.eslintrc.json`
- Added shadcn registry config: `components.json`.
- Added AI Elements generated component set in `components/ai-elements/` and supporting shadcn UI primitives in `components/ui/`.

## 2. Frontend Architectural Flow

### A. App Flow
Landing -> Get Started -> Clerk Auth -> Role Detection -> Dashboard (Doctor/Patient)

### B. Auth + RBAC Flow
User signs in (Clerk)  
-> Clerk session contains role metadata  
-> middleware.ts checks role  
-> route guard:
- `/dashboard/doctor/*` -> doctor only
- `/dashboard/patient/*` -> patient only
-> UI hides unauthorized features

### C. Chat + AI Flow (Frontend POV)
User uploads X-ray / asks question  
-> ChatWindow sends request to FastAPI (`/api/analyze` or `/api/chat`)  
-> Show streaming response  
-> Render:
- text
- annotated image URL
- report link (if generated)

### D. Doctor Workflow
Select patient  
-> View history  
-> Upload new X-ray  
-> Chat with assistant  
-> Generate report  
-> Save to backend  
-> Reports auto-attached to patient

### E. Patient Workflow
Upload report/X-ray  
-> Chat explains report in simple terms  
-> Severity shown  
-> Nearby hospitals fetched  
-> Advice + next steps

### F. State & Data
- Server state: React Query (chat, reports, patients)
- UI state: Zustand (sidebar open, modals, upload progress)
- Auth state: Clerk hooks

## 3. Codex (Copilot) Execution Plan (Detailed)

### Phase 1: Project Setup
Prompt:
Initialize Next.js 14 App Router with TypeScript, Tailwind, shadcn/ui, Clerk. Add root layout with ClerkProvider and theme tokens.

Tasks:
- Create app router
- Install Tailwind + shadcn/ui
- Setup Clerk auth pages
- Add theme tokens (colors, radius, fonts)

### Phase 2: Layout System
Prompt:
Build DashboardShell with Sidebar and Header. Sidebar should support role-based menu items.

Tasks:
- Sidebar component
- Header with user menu
- Dashboard layout
- Responsive collapse

### Phase 3: RBAC
Prompt:
Implement role-based access using Clerk metadata. Protect routes via middleware and UI guards.

Tasks:
- middleware.ts guards
- lib/rbac.ts helpers
- Hide doctor features from patients
- Redirect wrong role to own dashboard

### Phase 4: Chat UI
Prompt:
Build medical assistant chat UI with file upload, message streaming, and attachment previews.

Tasks:
- ChatWindow + MessageBubble
- FileDropzone
- Streaming response UI
- Loading states

### Phase 5: Doctor Dashboard
Prompt:
Create doctor views: patients list, patient profile, reports, chat. Use placeholder APIs.

Tasks:
- Patients list UI
- Patient profile panel
- Reports list
- Generate report CTA

### Phase 6: Patient Dashboard
Prompt:
Create patient views: upload report/X-ray, understand report, nearby hospitals.

Tasks:
- Upload UI
- Report viewer
- Nearby hospitals card
- Severity badges

### Phase 7: Visual Polish
Prompt:
Apply premium medical SaaS styling. Use custom SVG icons. Add subtle animations with Framer Motion.

Tasks:
- Replace default icons
- Add motion
- Improve empty states
- Skeleton loaders

## 4. Design System Tokens (Quick)

- Colors:
  - Primary: slate blue
  - Secondary: sage
  - Neutral: off-white, charcoal
  - Accent: amber
- Radius: 12px
- Shadow: soft card shadows
- Spacing: 8pt grid

## 5. What This Gives You

- Hackathon-ready premium UI
- Clean RBAC separation
- Doctor and patient journeys clearly modeled
- Future-proof for more agents and features
- Looks like a startup product, not an AI demo
