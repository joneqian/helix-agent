# Threat Scanner Tuning — Capability Uplift Sprint #1

> Pairs with `docs/streams/STREAM-UPLIFT-DESIGN.md` § 1 + § 2.
>
> Authoritative source for: pattern-set update process, false-positive
> triage, SecOps alert response, and per-tenant `block` mode opt-in.

The scanner lives in `packages/helix-common/src/helix_agent/common/threat_patterns.py`.
It runs in two phases (Mini-ADR U-2):

| Phase | Scope | On match | Where |
|-------|-------|----------|-------|
| Layer A: Create / Patch trigger | `strict` | 422 + audit `trigger:prompt_injection_blocked` | `services/control-plane/src/control_plane/api/triggers.py` |
| Layer B: Fire trigger (cron / webhook) | `context` | per `tenant_config.trigger_fire_scan_mode` (default `warn`) | `services/control-plane/src/control_plane/trigger_firing.py` |

Two findings live in different audit columns:

| Column | Where |
|--------|-------|
| `action` | `trigger:prompt_injection_blocked` or `..._warn` |
| `details.findings[i].pattern_id` | Pattern that matched (NOT in the HTTP response — oracle defense) |
| `details.findings[i].excerpt` | ≤ 200-char window around the match |
| `details.field` | Trigger field path (e.g. `config.seed_input`) — Layer A only |
| `details.mode` | `warn` / `block` — Layer B only |

## 1 — Updating the pattern set

The pattern set is a registry inside the threat module. A pattern is:

```python
(regex_str, pattern_id, category, scope)
# scope ∈ {"all", "context", "strict"}; "all" ⊂ "context" ⊂ "strict"
```

**Before opening a PR**:

1. Add the pattern with a clear `pattern_id` (lowercase snake_case).
2. Add ≥ 2 positive cases in `packages/helix-common/tests/test_threat_patterns.py`.
3. Add ≥ 2 negative (false-positive guard) cases pinning examples we
   would NOT want to match.
4. Run the 10-seed false-positive matrix
   (`test_legitimate_prompt_examples_pass_at_all`). If any new pattern
   trips on those legitimate seeds, **narrow the pattern** before
   committing — never widen the seed allowlist.
5. Run `uv run pytest packages/helix-common/tests/test_threat_patterns.py`.

**PR requirements**:

- Label: `security`
- Required reviewer: someone from the SecOps rotation
- Merge SLA: 24 hours (per [memory:zero-tech-debt](../../.claude/projects/-Users-mac-src-github-jone-qian-helix-agent/memory/feedback_zero_tech_debt.md) —
  pattern drift windows are an attack surface; don't let PRs rot)

**Post-merge dogfood**:

- Watch `helix:uplift:threat_block_rate:5m` for 24h after deploy.
- If `> 0.5 blocks/sec` for 15min: `HelixUpliftThreatBlockRateSpike`
  fires; treat as "did the new pattern catch real attacks, or did we
  add a noisy pattern" — see § 3.

## 2 — False-positive triage

When a tenant reports "my legitimate prompt got blocked":

1. Pull the audit row:

   ```sh
   curl -s "/v1/audit?action=trigger:prompt_injection_blocked&actor_id=<tenant_actor>" \
     | jq '.entries[].details'
   ```

2. Read `findings[*].pattern_id` and `findings[*].excerpt`.
3. If the matched substring is genuinely legitimate (e.g. a code review
   prompt that contains "pretend you are a reviewer"):
   - Open a `security`-labelled PR that **narrows the pattern** (anchor
     on more attack-specific vocabulary).
   - Add the legitimate excerpt to
     `test_legitimate_prompt_examples_pass_at_all` (in
     `test_threat_patterns.py`) to lock the fix.
   - Backport not required (M0 is one ring) — push to main, follow
     standard rollout.
4. If the matched substring is genuinely suspicious — explain to the
   tenant which input to rewrite. **Never** quote the `pattern_id` to
   the tenant (oracle defense — see § 4).

## 3 — SecOps alert response

### `HelixUpliftThreatBlockRateSpike`

`helix:uplift:threat_block_rate:5m > 0.5` sustained 15 min.

1. Group recent blocks by tenant + actor_id:

   ```sh
   curl -s "/v1/audit?action=trigger:prompt_injection_blocked&from=now-1h" \
     | jq '.entries | group_by(.actor_id) | map({actor: .[0].actor_id, count: length})'
   ```

2. If concentrated on one actor_id: likely a probe / abuse — escalate
   per the abuse-response runbook.
3. If diffuse across many tenants right after a deploy: probably a
   noisy pattern from the latest pattern-set update — `git log` on
   `threat_patterns.py` for the past 24h, identify the new pattern, run
   § 2 triage.

### `HelixUpliftFireTimeWarn`

`helix:uplift:trigger_fire_warn_rate:1h > 0` sustained 15 min.

This is **always** worth a look — fire-time matches mean either:

- (a) A pattern-set update is retroactively matching historically-accepted
  triggers (benign drift), OR
- (b) A trigger row was mutated past the create-time strict scan via
  SQL injection / internal-actor DB write (real attack).

To distinguish:

1. Identify which triggers fired with WARN:

   ```sh
   curl -s "/v1/audit?action=trigger:prompt_injection_warn&from=now-1h" \
     | jq '.entries[] | {trigger_id: .resource_id, findings: .details.findings}'
   ```

2. For each `trigger_id`, fetch the current row + check `updated_at`:
   - If `updated_at` is very recent (< pattern-set deploy time) → DB
     drift suspect; pull `audit_log` history for that resource_id and
     look for unexpected actors.
   - If `updated_at` is old → benign retroactive match; either narrow
     the new pattern (§ 2) or accept the warn.

## 4 — Oracle defense (why response bodies are generic)

The HTTP 422 body intentionally reads "prompt blocked by injection
scanner; see audit log for details" — it never names `pattern_id`,
never echoes the matched substring, never includes
`finding.category`.

Reason: an attacker who can call `POST /v1/triggers` repeatedly can
probe response bodies to learn which pattern fired, then mutate the
prompt to bypass that pattern.

The full finding is available in the audit log to the tenant's admin +
SecOps. That's the right cardinality of disclosure: developers debugging
their own triggers can pull the audit row; attackers can't (the audit
API requires authenticated admin access scoped to the tenant).

**If a developer asks "what pattern fired?"** — point them at
`GET /v1/audit?action=trigger:prompt_injection_blocked&actor_id=me`,
do not paste the `pattern_id` in a chat / ticket.

## 5 — `tenant_config.trigger_fire_scan_mode` opt-in to `block`

Default is `warn` for all tenants — pattern-set updates can't
retroactively block historically-accepted triggers.

High-compliance tenants can opt-in to `block` via:

```sh
curl -X PUT "/v1/tenants/{tid}/config" \
  -d '{"trigger_fire_scan_mode": "block"}'
```

**Before flipping a tenant to `block`**:

- Pull their `trigger:prompt_injection_warn` audit rows from the past
  30 days — anything currently warning will start blocking on next
  fire.
- Confirm with the tenant they have an incident-response process for
  blocked fires (their cron will silently fail with a 503 — no run, no
  data).

**Reverting**:

```sh
curl -X PUT "/v1/tenants/{tid}/config" \
  -d '{"trigger_fire_scan_mode": "warn"}'
```

No backfill — only affects future fires.

## 6 — Field-size cap

Single `str` leaves in `trigger.config` over `MAX_FIELD_BYTES` (10 KB,
in `services/control-plane/src/control_plane/uplift/threat_scan.py`)
are rejected with 422 **before** the scan runs (DoS defense — a
million-char string could exhaust the regex engine on a
catastrophic-backtracking pattern).

If a tenant has a legitimate need for fields larger than 10 KB:

1. Do not raise `MAX_FIELD_BYTES` without first analyzing the regex
   pattern set for catastrophic-backtracking potential (re2-style
   compilation isn't currently in place).
2. Prefer splitting the prompt across multiple smaller fields or using
   a skill (which has its own pipeline + size budget).

## 7 — Pattern-set provenance

Patterns are adapted from `hermes-agent/tools/threat_patterns.py`
(commit hash captured in the module docstring). When a Hermes update
adds new attack signatures, we don't auto-sync; SecOps reviews the
upstream diff and ports relevant patterns through § 1's PR flow.
