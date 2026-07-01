"""Gate-evidence CI check — the SR-6 / VR-4 "you can't skip the gate" enforcer.

Secure-by-construction means a security-sensitive or UI/behavioral change cannot merge
without the gate evidence the existing skills already produce. This check is the machine
backstop for that: it inspects a diff (base...head), classifies it into trigger categories,
and FAILS (exit 1) if a triggered category's evidence file is not present (added/modified) in
the SAME diff with at least minimal structure.

  Security-sensitive diff  -> requires docs/gates/<slug>-security-review.md  (/security-scan)
  UI/behavioral diff       -> requires docs/gates/<slug>-qa-gate.md          (qa-agent + /critic)

It enforces PRESENCE + STRUCTURE only — never QUALITY. The completeness/truthfulness of the
artifact stays with the security-agent (SR-6), the qa-agent (VR-2/3/4), /critic, and the CEO.
See docs/standards/GATE-EVIDENCE.md + ADR-0011.

Central truth, local enforcement (ADR-0011): this canonical copy lives in the company repo
(tools/evals/) and gates the company's own diffs via tier0.yml. Each product repo carries a
VENDORED copy at tools/gate/check_security_enumeration.py and runs it in its own CI. Keep the
two byte-identical; tools/evals/check_product_ci.py flags products whose copy is missing,
version-mismatched, or unwired. Bump GATE_EVIDENCE_CHECK_VERSION when the logic changes, then
re-vendor.

  python3 tools/evals/check_security_enumeration.py --base <sha> --head <sha> [--root .]
exit 0 = no triggered category is missing its evidence; exit 1 = one or more are missing it.

stdlib-only, zero-network, deterministic (charter: Claude Max usage is the budget).
"""

from __future__ import annotations

import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

# Bump when the trigger set or structure rules change; check_product_ci.py compares each
# product's vendored copy against this and flags a mismatch (re-vendor). See ADR-0011.
GATE_EVIDENCE_CHECK_VERSION = "3"

# The empty tree — diff target when there is no resolvable base (new branch / first push).
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# Max chars scanned per added line for content patterns (ReDoS defense-in-depth, SEC-GE-01).
_MAX_SCAN_LEN = 10000

# ── Trigger surfaces (docs/standards/GATE-EVIDENCE.md — the broader CEO-confirmed set) ──

# Security: a content pattern on an added/modified line OR a changed path glob.
SECURITY_CONTENT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"content-security-policy",
        r"unsafe-inline",
        r"unsafe-eval",
        r"\bnonce\b",
        r"\bauthorization\b",
        r"set-cookie",
        r"\bhttponly\b",
        r"\bsamesite\b",
        r"access-control-allow",
        r"\bcors\b",
        r"\b(crypto|cipher|hmac|bcrypt|pbkdf2|scrypt)\b",
        # Cryptographic hashing — explicit digest tokens, NOT bare `hash`: `\bhash\b` misses the
        # real call sites (`hashlib.sha256`, `password_hash` — the \b fails against `hashlib`/`_hash`)
        # yet fires on benign `obj.hash` / `# commit hash`. `digest` is excluded as overloaded
        # (RSS / email / HTTP-Digest auth). Keep in lockstep with the GATE-EVIDENCE.md crypto bullet.
        r"\b(hashlib|sha1|sha224|sha256|sha384|sha512|md5|blake2b|blake2s|createhash)\b",
        # BOUNDED quantifiers, not `.+` — an unbounded `.+...\bfrom` is quadratic ReDoS on a
        # long near-miss line (SEC-GE-01). A real SQL statement keyword-to-keyword span is short.
        r"\bselect\b.{1,200}?\bfrom\b",
        r"\binsert\s+into\b",
        r"\bupdate\b.{1,200}?\bset\b",
        r"\bdelete\s+from\b",
        r"\b(db|conn|cursor)\.(query|execute)\b",
        r"multipart/form-data",
        r"\b(pickle\.loads|yaml\.load|unserialize|deserialize)\b",
        r"\b(subprocess|child_process|os\.system|shell_exec)\b",
        r"\b(exec|eval)\s*\(",
        r"\b(jwt|jsonwebtoken)\b",
        r"redirect_uri",
        r"\bwebhook\b",
    )
]
SECURITY_PATH_GLOBS = (
    "*auth*",
    "*session*",
    "*secret*",
    "*credential*",
    "*cors*",
    "*rbac*",
    "*crypto*",
    "*csp*",
    "*headers*",
    "*.env*",
)

# UI/behavioral: path-based only.
# Extensions catch UI source wherever it lives (incl. under a Next.js app/ dir); the segment
# list stays narrow on purpose — "app/" would match nearly everything in a Next project and
# defeat "UI diffs only". A pure-backend .ts under app/ must NOT demand VR-4 evidence.
UI_EXTENSIONS = (".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss")
UI_PATH_SEGMENTS = ("components/", "pages/", "routes/", "views/")

# Evidence files (suffix match — <slug> is free-form; category match, not slug match).
SECURITY_EVIDENCE_SUFFIX = "security-review.md"
QA_EVIDENCE_SUFFIX = "qa-gate.md"
GATES_DIR = "docs/gates/"

# Excluded from TRIGGERING — these describe or implement the gate; they are not the change
# under review (GATE-EVIDENCE.md "Excluded from triggering").
_EXCLUDED_CHECK_NAMES = {
    "check_security_enumeration.py",
    "test_security_enumeration.py",
    "check_gate_evidence.py",
}

# Dependency lockfiles are GENERATED dependency-resolution metadata, never a hand-authored
# runtime surface. npm records each dependency's Subresource-Integrity digest as
# `"integrity": "sha512-…"` — which matches the crypto-digest content pattern on EVERY entry
# — so a one-line dev-dependency bump that regenerates the lockfile would otherwise be forced
# to carry a security review (false trigger). Exclude by basename, the same treatment as docs/
# and .md. This does NOT open a bypass: the real supply-chain surface is the MANIFEST
# (package.json / pyproject.toml — NOT excluded, still scanned) plus the CI dependency-audit
# gate (npm audit / pip-audit / osv-scanner); a lockfile carries no executable/reviewable code,
# only a name→version→hash table. Keep in lockstep with GATE-EVIDENCE.md.
_LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lock",
        "bun.lockb",
        "composer.lock",
        "Gemfile.lock",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "Cargo.lock",
        "go.sum",
        "flake.lock",
        "Podfile.lock",
        "gradle.lockfile",
        "packages.lock.json",
    }
)


def is_excluded(path: str) -> bool:
    """A changed path that should never itself trigger a gate.

    Excluded: docs/ (prose); ANY Markdown file (.md) — policy / docs / agent + command
    definitions describe security keywords but are not a shipped runtime surface, so a
    keyword in prose must not demand a security review (the real surface lives in code or
    config, never .md); dependency LOCKFILES (generated hash tables — see _LOCKFILE_NAMES);
    and the gate tooling itself. Note: executable controls like .claude/hooks/*.sh are NOT
    excluded — those are real security surfaces.
    """
    p = path.replace("\\", "/")
    if p.startswith("docs/") or p.endswith(".md"):
        return True
    name = p.rsplit("/", 1)[-1]
    return name in _EXCLUDED_CHECK_NAMES or name in _LOCKFILE_NAMES


# ── Structure validators (anti-stub; presence + minimal shape, never quality) ──

_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SEC_VERDICT = re.compile(
    r"(?i)\b(verdict|overall)\b.{0,40}?\b(PASS_WITH_NOTES|PASS|FAIL)\b", re.DOTALL
)
_SEC_MARKER = re.compile(r"(?i)\b(scope|target|finding|threat)\b")
_QA_VERDICT = re.compile(
    r"(?i)\b(verdict|overall)\b.{0,40}?\b(PASS|FAIL|CONCERNS|MARKET[- ]?READY)\b",
    re.DOTALL,
)
_QA_VR4 = re.compile(r"(?i)(VR-4|real[ -]?browser|playwright|\bbrowser\b)")
_QA_CRITIC = re.compile(r"(?i)\bcritic\b")


def valid_security_structure(text: str) -> bool:
    return bool(
        _SEC_VERDICT.search(text) and _DATE.search(text) and _SEC_MARKER.search(text)
    )


def valid_qa_structure(text: str) -> bool:
    return bool(
        _QA_VERDICT.search(text)
        and _DATE.search(text)
        and _QA_VR4.search(text)
        and _QA_CRITIC.search(text)
    )


# ── Pure decision logic (no git, no fs — unit-tested directly) ──


def triggers_security(changed_paths, added_lines_by_path) -> bool:
    for path in changed_paths:
        if is_excluded(path):
            continue
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        if any(fnmatch(name, g) or fnmatch(path, g) for g in SECURITY_PATH_GLOBS):
            return True
    for path, lines in added_lines_by_path.items():
        if is_excluded(path):
            continue
        for line in lines:
            # Cap scan length: a hand-authored security keyword appears early; a multi-KB single
            # line is a minified/generated blob, not a reviewed security edit. Bounds worst-case
            # regex cost even if a pattern regresses (defense-in-depth for SEC-GE-01).
            if any(p.search(line[:_MAX_SCAN_LEN]) for p in SECURITY_CONTENT_PATTERNS):
                return True
    return False


def triggers_ui(changed_paths) -> bool:
    for path in changed_paths:
        if is_excluded(path):
            continue
        p = path.replace("\\", "/")
        if p.endswith(UI_EXTENSIONS) or any(seg in p for seg in UI_PATH_SEGMENTS):
            return True
    return False


def _has_evidence(evidence_texts, suffix, validator) -> bool:
    for path, text in evidence_texts.items():
        p = path.replace("\\", "/")
        if GATES_DIR in p and p.endswith(suffix) and validator(text):
            return True
    return False


def evaluate(changed_paths, added_lines_by_path, evidence_texts):
    """Return a list of violation dicts. Pure — feed it parsed diff data.

    changed_paths: repo-relative paths changed in the diff.
    added_lines_by_path: {path: [added/modified content lines]}.
    evidence_texts: {path: full text} for docs/gates/*.md files touched in the diff.
    """
    out = []
    if triggers_security(changed_paths, added_lines_by_path) and not _has_evidence(
        evidence_texts, SECURITY_EVIDENCE_SUFFIX, valid_security_structure
    ):
        out.append(
            {
                "check": "gate-evidence",
                "category": "security",
                "message": (
                    "security-sensitive change in this diff, but no valid "
                    f"docs/gates/<slug>-{SECURITY_EVIDENCE_SUFFIX} was added/modified in it "
                    "(SR-6). Run /security-scan and commit its docs/gates/ artifact."
                ),
            }
        )
    if triggers_ui(changed_paths) and not _has_evidence(
        evidence_texts, QA_EVIDENCE_SUFFIX, valid_qa_structure
    ):
        out.append(
            {
                "check": "gate-evidence",
                "category": "qa",
                "message": (
                    "UI/behavioral change in this diff, but no valid "
                    f"docs/gates/<slug>-{QA_EVIDENCE_SUFFIX} was added/modified in it "
                    "(VR-4 + critic). Run the QA gate + /critic and commit the docs/gates/ artifact."
                ),
            }
        )
    return out


# ── git/fs plumbing for main() ──


def _git(root: Path, *args) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _safe_ref(ref: str) -> str:
    """Reject an option-like ref (leading '-') so a ref value can't smuggle a git option
    (e.g. `--output=...`) into the diff call (SEC-GE-02). Fail closed."""
    if ref.startswith("-"):
        raise ValueError(f"refusing option-like git ref: {ref!r}")
    return ref


def _resolve_base(root: Path, base: str | None) -> str:
    """Return a diffable base ref; fall back to the empty tree for new/unknown bases."""
    if not base or set(base) <= {"0"}:
        return _EMPTY_TREE
    try:
        _git(root, "rev-parse", "--verify", f"{_safe_ref(base)}^{{commit}}")
        return base
    except subprocess.CalledProcessError:
        return _EMPTY_TREE


def _diff_range(base: str) -> str:
    # three-dot (merge-base) for a real base; two-dot vs the empty tree lists all files.
    return base if base == _EMPTY_TREE else f"{base}..."


def collect_diff(root: Path, base: str, head: str):
    """Return (changed_paths, added_lines_by_path, evidence_texts) from git + the work tree."""
    head = _safe_ref(head)  # SEC-GE-02 — never let head smuggle a git option
    resolved = _resolve_base(root, base)
    sep = _diff_range(resolved)
    rng = [sep + head] if resolved != _EMPTY_TREE else [resolved, head]
    # Trailing `--` stops any token after the refs being parsed as an option/pathspec.
    changed = [
        ln.strip()
        for ln in _git(root, "diff", "--name-only", *rng, "--").splitlines()
        if ln.strip()
    ]

    added_lines_by_path: dict[str, list[str]] = {}
    cur: str | None = None
    for line in _git(root, "diff", "--unified=0", *rng, "--").splitlines():
        if line.startswith("+++ "):
            tail = line[4:].strip()
            cur = (
                None if tail == "/dev/null" else tail[2:] if tail[1:2] == "/" else tail
            )
        elif line.startswith("+") and not line.startswith("+++") and cur is not None:
            added_lines_by_path.setdefault(cur, []).append(line[1:])

    evidence_texts: dict[str, str] = {}
    for path in changed:
        p = path.replace("\\", "/")
        if GATES_DIR in p and p.endswith(".md"):
            f = root / path
            if f.is_file():
                evidence_texts[path] = f.read_text(encoding="utf-8", errors="ignore")
    return changed, added_lines_by_path, evidence_texts


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(
        description="Gate-evidence CI check (SR-6 / VR-4) — see docs/standards/GATE-EVIDENCE.md"
    )
    ap.add_argument("--root", default=".")
    ap.add_argument("--base", default=None, help="base ref/sha (default: origin/main)")
    ap.add_argument("--head", default="HEAD", help="head ref/sha (default: HEAD)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    base = a.base or "origin/main"

    try:
        changed, added, evidence = collect_diff(root, base, a.head)
    except (subprocess.CalledProcessError, ValueError) as e:
        # Fail closed — a security gate that can't read the diff (or is handed an unsafe ref)
        # must not silently pass.
        detail = getattr(e, "stderr", None) or e
        print(f"✗ gate-evidence: could not compute the diff ({detail}).")
        return 1

    viols = evaluate(changed, added, evidence)
    if not viols:
        print("✓ gate-evidence: every triggered gate carries its docs/gates/ evidence.")
        return 0

    print("✗ gate-evidence: required gate evidence missing for this change:")
    for v in viols:
        print(f"    [{v['category']}] {v['message']}")
    print(
        "\n  See docs/standards/GATE-EVIDENCE.md + ADR-0011. The evidence file must be "
        "added/modified in the SAME diff as the change it attests to."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
