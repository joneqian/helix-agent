"""Build the seed-file set for sandbox ``/workspace`` materialization.

skill-runtime §5.1 — an agent's activated skills are materialized at
``/workspace/skills/<name>/…`` so bundled scripts run as authored (the
canonical Agent Skills model: skill = a directory on the VM filesystem).

This runs ONCE at build time (``agent_factory.build_agent``) over the already-
resolved ``SkillVersion`` rows; the result is bound onto the sandbox tools and
sent to the supervisor on each ``acquire`` (the supervisor re-validates path +
caps at its trust boundary). Reuses the same U-21 checks as ``skill_view`` so
seeded bytes can't bypass the scanner:

* **drift** — a row whose recomputed ``content_hash`` doesn't match is skipped
  whole (tampered past the import-time scan).
* **context-scope threat scan** — each text supporting file is re-scanned; a hit
  drops that file. Binary files can't encode a prompt, so they're seeded as-is.

SKILL.md itself is always seeded (it is the ``prompt_fragment`` already injected
into the system prompt) so a skill's relative refs resolve on disk.
"""

from __future__ import annotations

import base64
import binascii
import logging

from helix_agent.common.threat_patterns import scan_for_threats
from helix_agent.protocol import SkillVersion
from helix_agent.protocol.skill import compute_content_hash, supporting_files_to_jsonable
from orchestrator.tools.skill_view import _repack_skill_md

logger = logging.getLogger(__name__)

#: Caps mirror the ``.skill`` package limits (and the supervisor's re-check):
#: 5 MiB total / 256 entries across all activated skills.
_MAX_SEED_TOTAL_BYTES = 5 * 1024 * 1024
_MAX_SEED_FILES = 256


def build_skill_seed_files(
    resolved_versions: dict[str, SkillVersion],
    activated_skill_names: list[str],
) -> tuple[tuple[str, bytes], ...]:
    """Return ``(relpath, raw_bytes)`` pairs for every activated skill's files,
    anchored under ``skills/<name>/``. Drift-skipped + threat-filtered + capped.
    """
    out: list[tuple[str, bytes]] = []
    total = 0
    for name in activated_skill_names:
        version = resolved_versions.get(name)
        if version is None:
            continue
        # U-21 drift: a tampered row → skip the whole skill (mirrors skill_view).
        jsonable = supporting_files_to_jsonable(version.supporting_files)
        if compute_content_hash(version.prompt_fragment, jsonable) != version.content_hash:
            logger.warning("skill_seed.drift_skipped skill=%s", name)
            continue

        candidates: list[tuple[str, bytes]] = [
            (f"skills/{name}/SKILL.md", _repack_skill_md(version).encode("utf-8"))
        ]
        for relpath, entry in sorted(version.supporting_files.items()):
            try:
                raw = base64.b64decode(entry.content, validate=True)
            except (ValueError, binascii.Error):
                logger.warning("skill_seed.bad_base64 skill=%s path=%s", name, relpath)
                continue
            # Re-scan text files (context scope); binary can't carry a prompt.
            try:
                text: str | None = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text is not None and scan_for_threats(text, scope="context"):
                logger.warning("skill_seed.blocked skill=%s path=%s", name, relpath)
                continue
            candidates.append((f"skills/{name}/{relpath}", raw))

        for path, data in candidates:
            if len(out) >= _MAX_SEED_FILES or total + len(data) > _MAX_SEED_TOTAL_BYTES:
                logger.warning(
                    "skill_seed.truncated reason=cap files=%d total_bytes=%d", len(out), total
                )
                return tuple(out)
            out.append((path, data))
            total += len(data)
    return tuple(out)
