// Uses Node.js built-in sqlite (node:sqlite), available since Node 22.5.0.
// No native compilation required — pure JS, zero extra dependencies.
// The Docker image pins node:22-alpine or later; locally Node 22+ is required.
import { DatabaseSync } from "node:sqlite";
import path from "path";
import fs from "fs";

const DATA_DIR = process.env.DATA_DIR || "/data";

// Ensure data directory exists (for local dev outside Docker)
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const DB_PATH = path.join(DATA_DIR, "lead-triage.sqlite");

let db: DatabaseSync;

export function getDb(): DatabaseSync {
  if (!db) {
    db = new DatabaseSync(DB_PATH);
    migrate(db);
  }
  return db;
}

function migrate(db: DatabaseSync): void {
  db.exec(`
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS processed_leads (
      key          TEXT PRIMARY KEY,
      created_at   TEXT NOT NULL DEFAULT (datetime('now')),
      slack_ts     TEXT,
      classification TEXT
    );

    CREATE TABLE IF NOT EXISTS dead_letter (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      key        TEXT,
      reason     TEXT NOT NULL,
      payload    TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS runs (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      key        TEXT,
      status     TEXT NOT NULL,
      detail     TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_runs_key ON runs(key);
    CREATE INDEX IF NOT EXISTS idx_dead_letter_key ON dead_letter(key);
  `);
}
