# Frontend Feature Flow

## 0. Landing Page (Marketing + Product Framing)

### Implemented Files
- `app/page.tsx`
- `components/landing/LandingPage.tsx`
- `components/ui/resizable-navbar.tsx`
- `components/layout/AppResizableNavbar.tsx`
- `components/resizable-navbar-demo.tsx`
- `components/layout/ThemeToggle.tsx`

### Implemented Sections
1. Hero section with product framing and CTA.
2. In-page section navigation (`#workflow`, `#audience`, `#trust`, `#start`).
3. Clinical workflow 3-step section.
4. Doctor vs patient audience section.
5. Trust & safety section.
6. Final CTA section.
7. Structured footer (product links + platform links).

### UX Notes
- Smooth scrolling for anchor navigation with reduced-motion fallback.
- Subtle motion via Framer Motion for section reveals and card stagger.
- Uses custom medical icons and healthcare-focused color direction.
- Dark/light mode toggle with persisted preference.
- Landing CTAs use Clerk redirect buttons for direct auth flow.
- Root app navigation now uses resizable navbar pattern.

## 1. Authentication (Clerk, App Router)

### Implemented Files
- `proxy.ts`
- `middleware.ts` (re-export of `proxy.ts` for Next.js 14 compatibility)
- `app/layout.tsx`
- `app/(auth)/sign-in/[[...sign-in]]/page.tsx`
- `app/(auth)/sign-up/[[...sign-up]]/page.tsx`
- `app/select-role/page.tsx`
- `components/auth/RoleSelectionScreen.tsx`
- `.env.example`

### Runtime Flow
1. Incoming requests pass through `clerkMiddleware()` in `proxy.ts`.
2. App is wrapped with `<ClerkProvider>` in `app/layout.tsx`.
3. Dedicated sign-in/sign-up routes render Clerk hosted UI components.
4. After auth, users are redirected to `/select-role` to choose `doctor` or `patient`.
5. Selected role is saved in Clerk `unsafeMetadata.role` and a short-lived role cookie for middleware routing.

### Dev Runtime Note
- `npm run dev` now uses `next dev` (non-turbo) as default for more stable local route compilation.
- `npm run dev:turbo` is still available if needed.

### Environment Setup
Use `.env.local` (not tracked):
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_DATA_SOURCE` (`mock` or `api`)

`.env.example` contains placeholders only.

## 2. RBAC (Doctor/Patient) via Clerk Session Claims

### Implemented Files
- `lib/constants.ts`
- `lib/rbac.ts`
- `app/dashboard/layout.tsx`
- `app/dashboard/page.tsx`
- `components/layout/DashboardShell.tsx`
- `components/layout/Header.tsx`
- `components/layout/Sidebar.tsx`
- `proxy.ts`

### Role Source
Role is resolved from Clerk session claims in this order:
1. `sessionClaims.role`
2. `sessionClaims.metadata.role`
3. `sessionClaims.publicMetadata.role`
4. `sessionClaims.public_metadata.role`

Supported roles:
- `doctor`
- `patient`

Fallback role:
- `patient`

### Route Guarding Flow
1. Any `/dashboard/*` route requires authenticated user (via middleware).
2. If unauthenticated, redirect to Clerk sign-in.
3. If authenticated but role missing, redirect to `/select-role`.
4. If authenticated with role:
- `/dashboard/doctor/*` requires `doctor`
- `/dashboard/patient/*` requires `patient`
5. If role/path mismatch, user is redirected to their allowed dashboard path.

### Dashboard Entry Flow
`/dashboard` server route:
1. Reads user + session claims (`auth()`).
2. Resolves role.
3. Redirects to:
- `/dashboard/doctor` for doctor
- `/dashboard/patient` for patient

## 3. Dashboard UI Segmentation

### Doctor Navigation
- Home
- Patients
- Reports
- Chat
- Settings

### Patient Navigation
- Home
- Reports
- Chat
- Nearby Care

Sidebar and header render role-aware UI from server-resolved role.

## 4. Data Layer (Mock/API Switch)

### Implemented Files
- `lib/data/mode.ts`
- `lib/data/types.ts`
- `lib/data/loaders.ts`
- `lib/mock-data/doctor-dashboard.ts`
- `lib/mock-data/patients.ts`
- `lib/mock-data/reports.ts`
- `lib/mock-data/nearby-care.ts`

### Runtime Switch
1. Set `NEXT_PUBLIC_DATA_SOURCE=mock` for frontend-only UI testing.
2. Set `NEXT_PUBLIC_DATA_SOURCE=api` to attempt backend-backed values.
3. Loaders gracefully fall back to mock data if API is unavailable or incomplete.

## 5. Chat Flow (Current Frontend State)

### Implemented Components
- AI Elements:
  - `components/ai-elements/conversation.tsx`
  - `components/ai-elements/message.tsx`
  - `components/ai-elements/prompt-input.tsx`
- Chat wrappers:
  - `components/chat/ChatWindow.tsx`
  - `components/chat/ChatInput.tsx`
  - `components/chat/MessageBubble.tsx`

### Current Behavior
1. User sends prompt from AI Elements prompt input.
2. Chat UI appends user message.
3. Chat UI appends local assistant mock response.

### Pending Integration
Replace local assistant mock with backend calls to:
- `POST /api/chat`
- `POST /api/analyze`

## 6. Backend Dependency Note

Current RBAC implementation is frontend/middleware-layer routing control using Clerk claims.

If you need strict API-level authorization, backend changes are required to validate Clerk-authenticated role for protected backend actions.
