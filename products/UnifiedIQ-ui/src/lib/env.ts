// Static SPA: only public, build-time-inlined config. Auth and the API base
// are handled server-side by FastAPI (same origin) + Databricks SSO.
export const appName = process.env.NEXT_PUBLIC_APP_NAME ?? "UnifiedIQ";
