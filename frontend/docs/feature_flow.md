# Frontend Feature Flow

## 1. Authentication (Clerk, App Router)

### Implemented Files
- `proxy.ts`
- `middleware.ts` (re-export of `proxy.ts` for Next.js 14 compatibility)
- `app/layout.tsx`
- `app/(auth)/sign-in/[[...sign-in]]/page.tsx`
- `app/(auth)/sign-up/[[...sign-up]]/page.tsx`
- `.env.example`

### Runtime Flow
1. Incoming requests pass through `clerkMiddleware()` in `proxy.ts`.
2. App is wrapped with `<ClerkProvider>` in `app/layout.tsx`.
3. Header renders:
- `<SignedOut>` -> `SignInButton`, `SignUpButton`
- `<SignedIn>` -> `UserButton`
4. Dedicated sign-in/sign-up routes render Clerk hosted UI components.

### Environment Setup
Use `.env.local` (not tracked):
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `NEXT_PUBLIC_API_BASE_URL`

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
3. If authenticated:
- `/dashboard/doctor/*` requires `doctor`
- `/dashboard/patient/*` requires `patient`
4. If role/path mismatch, user is redirected to their allowed dashboard path.

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

## 4. Chat Flow (Current Frontend State)

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

## 5. Backend Dependency Note

Current RBAC implementation is frontend/middleware-layer routing control using Clerk claims.

If you need strict API-level authorization, backend changes are required to validate Clerk-authenticated role for protected backend actions.
