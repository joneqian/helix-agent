"""Shared threat-pattern library — Capability Uplift Sprint #1.

Single source of truth for prompt-injection / promptware / exfiltration
patterns + invisible-Unicode detection. Used by:

- ``control_plane.api.triggers`` — create / patch (scope=strict, block)
- ``control_plane.trigger_firing`` — fire-time (scope=context, warn)
- ``control_plane.memory.*`` — write / recall (Sprint #2)

Design lives in ``docs/streams/STREAM-UPLIFT-DESIGN.md`` § 1.1 + § 2.

Pattern set is adapted from ``hermes-agent/tools/threat_patterns.py``
with the following helix-specific changes:

- Returns ``list[ThreatFinding]`` (not ``list[str]``) so callers can
  log full finding context to ``audit_event.details`` without re-parsing
  pattern IDs.
- ``severity`` is derived from scope: ``strict``/``all`` → ``"block"``,
  ``context`` → ``"warn"``. Callers decide what to do with severity;
  this module only classifies.
- ``excerpt`` (≤ 200 chars) captures the matched substring + neighborhood
  so SecOps can triage from the audit log directly.

The pattern set evolves via PR + ``security`` label. Updates MUST be
accompanied by ≥ 2 positive + 2 negative test cases (per the runbook at
``docs/runbooks/threat-scanner-tuning.md``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

ScanScope = Literal["all", "context", "strict"]

ThreatCategory = Literal[
    "injection",  # classic prompt-injection ("ignore previous instructions")
    "exfil",  # exfil via curl/wget/cat secrets
    "role_hijack",  # "you are now X" / "pretend you are X"
    "c2",  # C2 framework vocabulary / behaviors
    "persistence",  # SSH backdoor / config file overwrite
    "secrets",  # hardcoded credentials
    "invisible_unicode",  # zero-width / bidi / invisible math
]

Severity = Literal["block", "warn"]


@dataclass(frozen=True)
class ThreatFinding:
    """One match from :func:`scan_for_threats`.

    Immutable so callers can freely log / forward without defensive copy.
    """

    pattern_id: str
    category: ThreatCategory
    severity: Severity
    excerpt: str


# ---------------------------------------------------------------------------
# Invisible Unicode set — aligned with Hermes ``skills_guard.py``
# ---------------------------------------------------------------------------

INVISIBLE_CHARS: Final[frozenset[str]] = frozenset(
    {
        "​",  # zero-width space
        "‌",  # zero-width non-joiner
        "‍",  # zero-width joiner
        "⁠",  # word joiner
        "⁢",  # invisible times
        "⁣",  # invisible separator
        "⁤",  # invisible plus
        "﻿",  # zero-width no-break space (BOM)
        "‪",  # left-to-right embedding
        "‫",  # right-to-left embedding
        "‬",  # pop directional formatting
        "‭",  # left-to-right override
        "‮",  # right-to-left override
        "⁦",  # left-to-right isolate
        "⁧",  # right-to-left isolate
        "⁨",  # first strong isolate
        "⁩",  # pop directional isolate
    }
)


# ---------------------------------------------------------------------------
# Pattern registry — (regex, pattern_id, category, scope)
# ---------------------------------------------------------------------------

# Pattern anchoring rules (per Hermes ``threat_patterns.py``):
#
# - Anchor on C2-specific vocabulary or unambiguous attack behavior, NOT
#   on bossy English. "You must X" alone fires on every CLAUDE.md ever
#   written. Verb-anchor it: "you must register/connect/report".
#
# - Use ``(?:\w+\s+)*`` between key tokens so attackers can't bypass with
#   filler ("ignore all prior instructions" vs "ignore instructions").
#
# Adding a pattern: ≥ 2 positive cases + ≥ 2 negative cases in
# ``test_threat_patterns.py``, plus run the K.K12 false-positive matrix.

_PATTERNS: Final[list[tuple[str, str, ThreatCategory, ScanScope]]] = [
    # ── Classic prompt injection (scope=all) ───────────────────────────
    (
        r"ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+(?:\w+\s+)*instructions",
        "prompt_injection",
        "injection",
        "all",
    ),
    (r"system\s+prompt\s+override", "sys_prompt_override", "injection", "all"),
    (
        r"disregard\s+(?:\w+\s+)*(your|all|any)\s+(?:\w+\s+)*(instructions|rules|guidelines)",
        "disregard_rules",
        "injection",
        "all",
    ),
    (
        r"act\s+as\s+(if|though)\s+(?:\w+\s+)*you\s+(?:\w+\s+)*"
        r"(have\s+no|don't\s+have)\s+(?:\w+\s+)*(restrictions|limits|rules)",
        "bypass_restrictions",
        "injection",
        "all",
    ),
    (
        r"<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->",
        "html_comment_injection",
        "injection",
        "all",
    ),
    (
        r"<\s*div\s+style\s*=\s*[\"\'][\s\S]*?display\s*:\s*none",
        "hidden_div",
        "injection",
        "all",
    ),
    (
        r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)",
        "translate_execute",
        "injection",
        "all",
    ),
    (
        r"do\s+not\s+(?:\w+\s+)*tell\s+(?:\w+\s+)*the\s+user",
        "deception_hide",
        "injection",
        "all",
    ),
    # ── Role-play / identity hijack (scope=context) ────────────────────
    (
        r"you\s+are\s+(?:\w+\s+)*now\s+(?:a|an|the)\s+",
        "role_hijack",
        "role_hijack",
        "context",
    ),
    (
        r"pretend\s+(?:\w+\s+)*(you\s+are|to\s+be)\s+",
        "role_pretend",
        "role_hijack",
        "context",
    ),
    (
        r"output\s+(?:\w+\s+)*(system|initial)\s+prompt",
        "leak_system_prompt",
        "injection",
        "context",
    ),
    (
        r"(respond|answer|reply)\s+without\s+(?:\w+\s+)*"
        r"(restrictions|limitations|filters|safety)",
        "remove_filters",
        "injection",
        "context",
    ),
    (
        r"you\s+have\s+been\s+(?:\w+\s+)*(updated|upgraded|patched)\s+to",
        "fake_update",
        "injection",
        "context",
    ),
    # "name yourself X" — Brainworm tell, anchored to the verb pair.
    (r"\bname\s+yourself\s+\w+", "identity_override", "role_hijack", "context"),
    # ── C2 / Brainworm-style promptware (scope=context) ───────────────
    (r"register\s+(as\s+)?a?\s*node", "c2_node_registration", "c2", "context"),
    (
        r"(heartbeat|beacon|check[\s\-]?in)\s+(to|with)\s+",
        "c2_heartbeat",
        "c2",
        "context",
    ),
    (r"pull\s+(down\s+)?(?:new\s+)?task(?:ing|s)?\b", "c2_task_pull", "c2", "context"),
    (r"connect\s+to\s+the\s+network\b", "c2_network_connect", "c2", "context"),
    (
        r"you\s+must\s+(?:\w+\s+){0,3}(register|connect|report|beacon)\b",
        "forced_action",
        "c2",
        "context",
    ),
    (r"only\s+use\s+one[\s\-]?liners?\b", "anti_forensic_oneliner", "c2", "context"),
    (
        r"never\s+(?:\w+\s+)*(?:create|write)\s+(?:\w+\s+)*(?:script|file)\s+(?:\w+\s+)*disk",
        "anti_forensic_disk",
        "c2",
        "context",
    ),
    (
        r"unset\s+\w*(?:CLAUDE|CODEX|HERMES|HELIX|AGENT|OPENAI|ANTHROPIC)\w*",
        "env_var_unset_agent",
        "c2",
        "context",
    ),
    (
        r"\b(?:praxis|cobalt\s*strike|sliver|havoc|mythic|metasploit|brainworm)\b",
        "known_c2_framework",
        "c2",
        "context",
    ),
    (
        r"\bc2\s+(?:server|channel|infrastructure|beacon)\b",
        "c2_explicit",
        "c2",
        "context",
    ),
    (r"\bcommand\s+and\s+control\b", "c2_explicit_long", "c2", "context"),
    # ── Exfiltration ──────────────────────────────────────────────────
    (
        r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)",
        "exfil_curl",
        "exfil",
        "all",
    ),
    (
        r"wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)",
        "exfil_wget",
        "exfil",
        "all",
    ),
    (
        r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)",
        "read_secrets",
        "exfil",
        "all",
    ),
    (
        r"(send|post|upload|transmit)\s+.*\s+(to|at)\s+https?://",
        "send_to_url",
        "exfil",
        "strict",
    ),
    (
        r"(include|output|print|share)\s+(?:\w+\s+)*"
        r"(conversation|chat\s+history|previous\s+messages|full\s+context|entire\s+context)",
        "context_exfil",
        "exfil",
        "strict",
    ),
    # ── Persistence / config tamper (scope=strict) ────────────────────
    (r"authorized_keys", "ssh_backdoor", "persistence", "strict"),
    (r"\$HOME/\.ssh|\~/\.ssh", "ssh_access", "persistence", "strict"),
    (
        r"\$HOME/\.helix/\.env|\~/\.helix/\.env",
        "helix_env",
        "persistence",
        "strict",
    ),
    (
        r"(update|modify|edit|write|change|append|add\s+to)\s+.*"
        r"(?:AGENTS\.md|CLAUDE\.md|\.cursorrules|\.clinerules)",
        "agent_config_mod",
        "persistence",
        "strict",
    ),
    (
        r"(update|modify|edit|write|change|append|add\s+to)\s+.*"
        r"\.helix/(config\.yaml|SOUL\.md|manifest\.yaml)",
        "helix_config_mod",
        "persistence",
        "strict",
    ),
    # ── Hardcoded secrets ──────────────────────────────────────────────
    (
        r"(?:api[_-]?key|token|secret|password)\s*[=:]\s*[\"\'][A-Za-z0-9+/=_-]{20,}",
        "hardcoded_secret",
        "secrets",
        "strict",
    ),
]


# ---------------------------------------------------------------------------
# Compilation — pattern lists per scope
# ---------------------------------------------------------------------------

_CompiledEntry = tuple[re.Pattern[str], str, ThreatCategory]
_COMPILED: dict[ScanScope, list[_CompiledEntry]] = {
    "all": [],
    "context": [],
    "strict": [],
}


def _compile() -> None:
    """Compile pattern sets. Scope inclusion: all ⊂ context ⊂ strict."""
    if _COMPILED["all"]:
        return
    for raw, pid, category, scope in _PATTERNS:
        compiled = re.compile(raw, re.IGNORECASE)
        entry: _CompiledEntry = (compiled, pid, category)
        if scope == "all":
            _COMPILED["all"].append(entry)
            _COMPILED["context"].append(entry)
            _COMPILED["strict"].append(entry)
        elif scope == "context":
            _COMPILED["context"].append(entry)
            _COMPILED["strict"].append(entry)
        elif scope == "strict":
            _COMPILED["strict"].append(entry)
        else:
            raise ValueError(f"unknown scope {scope!r} for pattern {pid!r}")


_compile()


# ---------------------------------------------------------------------------
# Excerpt helper
# ---------------------------------------------------------------------------

_EXCERPT_MAX = 200
_EXCERPT_PAD = 40  # chars of surrounding context on each side of the match


def _excerpt(content: str, match: re.Match[str] | None) -> str:
    """Return a ≤ ``_EXCERPT_MAX`` window around the match.

    If ``match`` is None (invisible Unicode case), returns the head of
    ``content`` (capped).
    """
    if match is None:
        return content[:_EXCERPT_MAX]
    start = max(0, match.start() - _EXCERPT_PAD)
    end = min(len(content), match.end() + _EXCERPT_PAD)
    chunk = content[start:end]
    if len(chunk) > _EXCERPT_MAX:
        chunk = chunk[:_EXCERPT_MAX]
    return chunk


def _severity_for_scope(scope: ScanScope) -> Severity:
    return "warn" if scope == "context" else "block"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_for_threats(content: str, *, scope: ScanScope) -> list[ThreatFinding]:
    """Scan ``content`` and return all matched patterns + invisible chars.

    Scope selects the pattern set:

    - ``"all"`` (narrow): classic injection + exfil only. Lowest false
      positives. Severity: block.
    - ``"context"`` (default): adds promptware / C2 / role-hijack patterns.
      Severity: warn.
    - ``"strict"`` (broad): adds persistence / SSH backdoor / config-tamper
      patterns. Severity: block.

    Invisible Unicode characters always fire (at every scope) and report
    as ``pattern_id="invisible_unicode_U+XXXX"``.
    """
    if not content:
        return []
    if scope not in _COMPILED:
        raise ValueError(f"unknown scope {scope!r}")

    findings: list[ThreatFinding] = []
    severity = _severity_for_scope(scope)

    # Invisible Unicode — single set-intersection pass.
    char_set = set(content)
    invisible_hits = char_set & INVISIBLE_CHARS
    for ch in sorted(invisible_hits):
        findings.append(
            ThreatFinding(
                pattern_id=f"invisible_unicode_U+{ord(ch):04X}",
                category="invisible_unicode",
                severity=severity,
                excerpt=_excerpt(content, None),
            )
        )

    # Regex patterns.
    for compiled, pid, category in _COMPILED[scope]:
        match = compiled.search(content)
        if match is not None:
            findings.append(
                ThreatFinding(
                    pattern_id=pid,
                    category=category,
                    severity=severity,
                    excerpt=_excerpt(content, match),
                )
            )

    return findings


def first_threat_message(content: str, *, scope: ScanScope) -> str | None:
    """Return a human-readable error for the first finding, or None.

    Convenience wrapper for paths that block on first hit (memory write,
    skill install). The returned string is safe to put in a log line —
    it deliberately omits the matched substring to avoid log poisoning.
    """
    findings = scan_for_threats(content, scope=scope)
    if not findings:
        return None
    first = findings[0]
    if first.pattern_id.startswith("invisible_unicode_"):
        codepoint = first.pattern_id.removeprefix("invisible_unicode_")
        return (
            f"Blocked: content contains invisible unicode character "
            f"{codepoint} (possible injection)."
        )
    return (
        f"Blocked: content matches threat pattern {first.pattern_id!r}. "
        f"Content is injected into the system prompt and must not contain "
        f"injection or exfiltration payloads."
    )


__all__ = [
    "INVISIBLE_CHARS",
    "ScanScope",
    "Severity",
    "ThreatCategory",
    "ThreatFinding",
    "first_threat_message",
    "scan_for_threats",
]
