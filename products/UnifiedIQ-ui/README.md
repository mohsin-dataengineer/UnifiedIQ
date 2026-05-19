# UnifiedIQ UI

Next.js 15 (App Router) frontend for UnifiedIQ. The browser never calls the
API directly — every request is proxied through Next.js Route Handlers (BFF),
which inject the authenticated user's identity and bearer token.

## Stack

- Next.js 15 + React 19 + TypeScript (strict)
- Tailwind CSS 4, shadcn/ui primitives
- NextAuth v5 with Okta (OIDC), JWT sessions (8h max age)
- Zod-validated env (`src/lib/env.ts`)
- Recharts, react-markdown + remark-gfm

## Local dev

```bash
cp .env.example .env.local     # fill in Okta + NEXTAUTH_SECRET
npm install
npm run dev                    # http://localhost:3000
```

Set `AUTH_BYPASS=true` (both UI and API) to develop without Okta.

## BFF proxy

- `src/app/api/[...path]/route.ts` — generic authenticated proxy to `API_BASE_URL`
- `src/app/api/chat/stream/route.ts` — SSE pass-through for streaming chat
- `src/app/api/auth/[...nextauth]/route.ts` — NextAuth handlers

State management is React Context only (no Redux/Zustand/Jotai).
