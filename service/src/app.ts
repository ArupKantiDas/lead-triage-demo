import { Hono } from "hono";
import { getDb } from "./db";

export const app = new Hono();

// ── Healthz ──────────────────────────────────────────────────────────────────
app.get("/healthz", (c) => {
  const db = getDb();
  // Smoke-test the DB is reachable
  db.prepare("SELECT 1 AS ok").get();
  return c.json({ ok: true, ts: new Date().toISOString() });
});

// ── POST /idempotency/check ───────────────────────────────────────────────────
// Body: { key: string }
// Returns: { seen: boolean, record?: { key, created_at, slack_ts, classification } }
app.post("/idempotency/check", async (c) => {
  let body: { key?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const { key } = body;
  if (!key || typeof key !== "string") {
    return c.json({ error: "key is required" }, 400);
  }

  const db = getDb();
  const row = db
    .prepare(
      "SELECT key, created_at, slack_ts, classification FROM processed_leads WHERE key = ?",
    )
    .get(key) as
    | {
        key: string;
        created_at: string;
        slack_ts: string | null;
        classification: string | null;
      }
    | undefined;

  if (row) {
    return c.json({ seen: true, record: row });
  }
  return c.json({ seen: false });
});

// ── POST /idempotency/commit ──────────────────────────────────────────────────
// Body: { key: string, classification: string, slack_ts?: string }
// Returns: { ok: true }
app.post("/idempotency/commit", async (c) => {
  let body: { key?: string; classification?: string; slack_ts?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const { key, classification, slack_ts } = body;
  if (!key || typeof key !== "string") {
    return c.json({ error: "key is required" }, 400);
  }
  if (!classification || typeof classification !== "string") {
    return c.json({ error: "classification is required" }, 400);
  }

  const db = getDb();
  db.prepare(
    "INSERT OR REPLACE INTO processed_leads (key, classification, slack_ts, created_at) VALUES (?, ?, ?, datetime('now'))",
  ).run(key, classification, slack_ts ?? null);

  return c.json({ ok: true });
});

// ── POST /deadletter ──────────────────────────────────────────────────────────
// Body: { key?: string, reason: string, payload: object | string }
// Returns: { ok: true }
app.post("/deadletter", async (c) => {
  let body: { key?: string; reason?: string; payload?: unknown };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const { key, reason, payload } = body;
  if (!reason || typeof reason !== "string") {
    return c.json({ error: "reason is required" }, 400);
  }
  if (payload === undefined) {
    return c.json({ error: "payload is required" }, 400);
  }

  const db = getDb();
  db.prepare(
    "INSERT INTO dead_letter (key, reason, payload, created_at) VALUES (?, ?, ?, datetime('now'))",
  ).run(
    key ?? null,
    reason,
    typeof payload === "string" ? payload : JSON.stringify(payload),
  );

  return c.json({ ok: true });
});

// ── POST /runs ────────────────────────────────────────────────────────────────
// Body: { key?: string, status: string, detail?: string }
// Returns: { ok: true }
app.post("/runs", async (c) => {
  let body: { key?: string; status?: string; detail?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const { key, status, detail } = body;
  if (!status || typeof status !== "string") {
    return c.json({ error: "status is required" }, 400);
  }

  const db = getDb();
  db.prepare(
    "INSERT INTO runs (key, status, detail, created_at) VALUES (?, ?, ?, datetime('now'))",
  ).run(key ?? null, status, detail ?? null);

  return c.json({ ok: true });
});

// ── GET /runs ─────────────────────────────────────────────────────────────────
// Returns: last 50 runs
app.get("/runs", (c) => {
  const db = getDb();
  const rows = db
    .prepare(
      "SELECT id, key, status, detail, created_at FROM runs ORDER BY id DESC LIMIT 50",
    )
    .all() as {
    id: number;
    key: string | null;
    status: string;
    detail: string | null;
    created_at: string;
  }[];
  return c.json({ runs: rows });
});

// ── GET /deadletter ───────────────────────────────────────────────────────────
// Returns: last 50 dead-letter entries
app.get("/deadletter", (c) => {
  const db = getDb();
  const rows = db
    .prepare(
      "SELECT id, key, reason, payload, created_at FROM dead_letter ORDER BY id DESC LIMIT 50",
    )
    .all() as {
    id: number;
    key: string | null;
    reason: string;
    payload: string;
    created_at: string;
  }[];
  return c.json({ dead_letter: rows });
});
