import { serve } from "@hono/node-server";
import { app } from "./app";

const PORT = Number.parseInt(process.env.PORT || "3001", 10);

// ── Start ─────────────────────────────────────────────────────────────────────
serve({ fetch: app.fetch, port: PORT }, () => {
  console.log(`[sidecar] listening on http://0.0.0.0:${PORT}`);
});
