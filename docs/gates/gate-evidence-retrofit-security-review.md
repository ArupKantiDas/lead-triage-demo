# Security Review — gate-evidence CI enforcement retrofit (ADR-0011)

Date: 2026-06-16
Target/Scope: this repo's retrofit to the company gate-evidence enforcement layer —
the vendored check `tools/gate/check_security_enumeration.py` and the new `gate-evidence`
job in `.github/workflows/ci.yml` (runs at the repo root, not `service/`).
Verdict: PASS

## What changed
- Vendored the company's canonical `tools/evals/check_security_enumeration.py` (byte-identical)
  to `tools/gate/check_security_enumeration.py` (version `1`).
- Added a build-failing `gate-evidence` job to `ci.yml` that runs the vendored check over the
  PR/push diff (`fetch-depth: 0`, no GitHub-API dependency). The job runs at the repo root so it
  sees `tools/gate/` and `docs/gates/` (the Node app lives in `service/`).

## Threat / findings
- The vendored check is stdlib-only, zero-network, deterministic; it reads the git diff and the
  working tree only. No new secret, no network egress, no new dependency. **No findings.**
- SHAs are passed to the shell step via `env:` (not interpolated into the script body) —
  defense-in-depth against workflow injection.
- Honest limit (per ADR-0011): the gate enforces PRESENCE + STRUCTURE of evidence, not its
  quality. Quality stays with the security-agent (SR-6), the qa-agent (VR-4), `/critic`, the CEO.

## In-repo proof the gate works (real runs of the vendored copy, captured — not assumed)
Run in an isolated `git worktree` off this repo's HEAD; a security-sensitive change (an
`Authorization` header helper) was committed without evidence, then with it:

```
########## RED run (auth diff, NO evidence) ##########
✗ gate-evidence: required gate evidence missing for this change:
    [security] security-sensitive change in this diff, but no valid docs/gates/<slug>-security-review.md was added/modified in it (SR-6).
RED_EXIT=1

########## GREEN run (same diff, WITH evidence) ##########
✓ gate-evidence: every triggered gate carries its docs/gates/ evidence.
GREEN_EXIT=0
```

Security gate verdict: **PASS** (no findings). This change is CEO-gated for release; not merged.
