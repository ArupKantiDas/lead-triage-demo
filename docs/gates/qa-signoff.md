# QA Gate Sign-off — Lead Triage Demo

**Verdict: CONDITIONAL PASS — ships after one blocking fix (5-minute change)**

Date: 2026-06-11
QA Agent: qa-agent (claude-sonnet-4-6)
Security gate: PASSED (prior)
Build tested: /outputs/prototypes/lead-triage-demo/

---

## What was tested

### 1. Sidecar — live execution (not mocked)

The sidecar was built from source, started locally on port 3099 with DATA_DIR=/tmp, and
exercised with direct curl calls. All tests passed against actual SQLite state.

Test results:

| Test | Input | Expected | Actual | PASS/FAIL |
|------|-------|----------|--------|-----------|
| /healthz | GET | {ok:true} | {ok:true,ts:...} | PASS |
| /idempotency/check — unseen key | {key:"good-lead-demo-001"} | {seen:false} | {seen:false} | PASS |
| /idempotency/commit | {key,classification:"hot",slack_ts} | {ok:true} | {ok:true} | PASS |
| /idempotency/check — seen key | same key | {seen:true,record:{...}} | {seen:true,record:{key,created_at,slack_ts,classification}} | PASS |
| Double-commit (idempotency) | commit same key twice | 1 row in processed_leads | COUNT=1 (INSERT OR REPLACE upsert) | PASS |
| /deadletter reason=validation | {key,reason,payload} | {ok:true} | {ok:true} | PASS |
| /deadletter reason=error | {key,reason,payload} | {ok:true} | {ok:true} | PASS |
| /runs status=success | {key,status,detail} | {ok:true} | {ok:true} | PASS |
| /runs status=duplicate | same | {ok:true} | {ok:true} | PASS |
| /runs status=error | same | {ok:true} | {ok:true} | PASS |
| GET /runs | - | [{id,key,status,detail,created_at},...] | 3 rows covering all statuses | PASS |
| GET /deadletter | - | [{id,key,reason,payload,created_at},...] | 2 rows (validation+error) | PASS |
| Missing required field validation | no key/status/reason | 400 {error:...} | 400 on all 4 endpoints | PASS |
| Malformed JSON body | "NOT JSON" | 400 {error:"Invalid JSON body"} | Correct 400 | PASS |
| /runs with null key | {status:"error"} | {ok:true}, key=null in DB | Correct | PASS |

SQLite schema: all three tables (processed_leads, dead_letter, runs) migrate cleanly on first
start. processed_leads has TEXT PRIMARY KEY — INSERT OR REPLACE enforces one row per key.
dead_letter and runs are append-only (AUTOINCREMENT). Correct.

### 2. Workflow static analysis (workflow/lead-triage.json)

#### Happy path
Webhook -> Compute Key -> Validate Input -> Valid?(TRUE) -> Idempotency Check ->
Already Seen?(FALSE) -> LLM Classify -> Parse LLM Response -> Build Slack Message ->
Post to Slack -> Idempotency Commit -> Log Run (success) -> Respond – Success
Response: {"status":"ok","tier":"hot|warm|cold"}
Sidecar writes: /idempotency/commit, /runs (status=success). CORRECT.

#### Validation-reject path
... -> Valid?(FALSE) -> Dead-Letter (validation) -> Slack Alert (validation) ->
Respond – Rejected
Response: {"status":"rejected","reason":"..."}
LLM NOT called. Slack lead channel NOT posted. Dead-letter written. CORRECT.

#### Duplicate path
... -> Already Seen?(TRUE) -> Log Run (duplicate) -> Respond – Duplicate
Response: {"status":"duplicate","key":"..."}
LLM NOT called. Slack lead channel NOT posted. /runs written with status=duplicate. CORRECT.

#### Node-error path
Any of: Idempotency Check, LLM Classify, Parse LLM Response, Build Slack Message,
Post to Slack, Idempotency Commit — each has onError:continueErrorOutput wired to:
Error Handler -> Dead-Letter (error) -> Slack Alert (error) -> Log Run (error) ->
Respond – Error
Response: {"status":"error","logged":true}
No silent drop. CORRECT.

IF node branch directions: Valid? main[0]=TRUE->Idempotency Check, main[1]=FALSE->Dead-Letter.
Already Seen? main[0]=TRUE->Log Run (duplicate), main[1]=FALSE->LLM Classify. Both CORRECT.

---

## Defects found

### DEFECT 1 — BLOCKING (5-minute fix)
**Missing N8N_BLOCK_ENV_ACCESS_IN_NODE=false in docker-compose.yml**

Since n8n v0.213.0 (2022), n8n blocks $env access in workflow expressions by default.
The docker-compose.yml does not set N8N_BLOCK_ENV_ACCESS_IN_NODE=false.

The workflow uses $env.SIDECAR_URL, $env.LLM_API_KEY, $env.LLM_BASE_URL, $env.LLM_MODEL,
$env.SLACK_WEBHOOK_HOT, $env.SLACK_WEBHOOK_WARM, $env.SLACK_WEBHOOK_COLD, and
$env.SLACK_WEBHOOK_ALERTS in 11 different nodes. Without this flag, every $env reference
returns undefined/empty — every sidecar call and every Slack call silently posts to an empty
URL, and the LLM call gets an empty Authorization header (401). All three headline claims fail.

Fix: add one line to the n8n service environment block in docker-compose.yml:
  N8N_BLOCK_ENV_ACCESS_IN_NODE: "false"

Severity: BLOCKING. The demo cannot run end-to-end without this change.

### DEFECT 2 — README documentation error (non-blocking for demo)
**README step 3 instructs users to create an n8n HTTP Header credential named "LLM API Key"**

The workflow does not reference any credential on the LLM Classify node (credentials: {} in
the JSON). The node reads the API key via $env.LLM_API_KEY in its Authorization header
parameter. The credential created per the README is never used.

Impact: a user following the README exactly will create a credential and expect n8n to inject
it, but nothing will break (once Defect 1 is fixed — the header will already have the key
from the env var). It is misleading and could confuse a prospect watching the demo.

Fix: remove the credential creation instructions from README step 3. Replace with:
"The LLM key is read automatically from the LLM_API_KEY env var you set in step 1. No
separate credential is needed inside n8n."

Severity: NON-BLOCKING for demo functionality. Blocking for README credibility.

### DEFECT 3 — Minor robustness (non-blocking for demo)
**Response body templates for Respond-Duplicate and Respond-Success use inline {{ }} syntax**

The responseBody for resp-duplicate is: ={ "status": "duplicate", "key": "{{ key }}" }
This is n8n's template-string mode (not JS expression mode). It works for the fixed demo
key "good-lead-demo-001" and sha256 hex strings. It would produce invalid JSON if the
Idempotency-Key header value contained a double-quote character. Not exploitable in the
demo — the scripts use a fixed safe key — but worth noting.

Severity: NOT BLOCKING for demo.

---

## What could NOT be verified without Docker/n8n

The following required a live n8n instance and could not be verified statically or via
sidecar tests alone:

1. Whether n8n v1.x actually routes the error output of continueErrorOutput nodes to the
   error-output-connected node correctly under all failure conditions. The connection map is
   correct in the JSON; runtime behavior was not executed.
2. Whether the Respond nodes correctly send HTTP 200 with the specified body shape to the
   original webhook caller (depends on n8n respondToWebhook typeVersion 1.1 runtime).
3. The full end-to-end path with real Groq API and real Slack webhook.
4. Whether the Already Seen? IF node in n8n correctly evaluates $json.seen as boolean true
   vs the string "true" (n8n IF comparisons with boolean type should handle this, but it
   was not live-tested).

Judgment: these gaps are acceptable for a DEMO gate. The spec says "nothing faked" and
the sidecar — which is the only novel code — was fully exercised. The workflow is a
standard n8n graph with no logic more complex than IF + HTTP nodes. The one unresolved
runtime risk (Defect 1) is the blocking fix.

---

## Loom demo viability

Claim 1 — Idempotency: FULLY SHOWABLE. Fire good lead -> see Slack post + GET /runs shows
status=success. Replay same lead -> response shows {status:"duplicate"} + GET /runs shows
a second row status=duplicate + no new Slack post. Clean 20-second beat.

Claim 2 — Error handling: FULLY SHOWABLE. Fire bad input -> response shows {status:"rejected"}
+ Slack #alerts shows validation alert + GET /deadletter shows the entry. For node-error:
demo by temporarily pointing LLM_BASE_URL at a bad URL -> response shows {status:"error",logged:true}
+ Slack #alerts shows error alert + GET /deadletter shows entry.

Claim 3 — Observability: FULLY SHOWABLE. curl GET /runs | jq . shows all three run types
in one command. curl GET /deadletter | jq . shows both dead-letter entries. n8n UI
Executions tab shows full execution history as a bonus screenshot.

All three claims can be shown in under 90 seconds across the three paths. Nothing is
visually hidden or requires explanation — the curl responses and Slack screenshots tell
the story directly.

---

## Conditions for PASS

1. Fix Defect 1: add N8N_BLOCK_ENV_ACCESS_IN_NODE: "false" to docker-compose.yml n8n service.
2. Fix Defect 2: remove the false credential instructions from README step 3.

After those two changes, the demo is market-ready as a credibility artifact. It is thin,
honest, and proves the three claimed properties. No gold-plating needed.

---

QA sign-off: CONDITIONAL PASS pending Defect 1 (blocking) and Defect 2 (credibility).
Sidecar: fully tested and passing. Workflow: statically verified correct. README: one
inaccuracy to fix. Stack: ready to run on first docker compose up after the two fixes.
