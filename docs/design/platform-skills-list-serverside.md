# Platform skills list — server-side pagination + search + batch (C+)

The platform skills admin list (`SettingsPlatformSkills`) fetched only the first
page (`listPlatformSkills()` with no params, backend default `limit=50`),
discarded `next_cursor`, and rendered `pagination={false}`. So a library with
>50 skills hid everything past the first 50, and the new bulk-action "select
all" only ever covered those 50. This makes the list correct + scalable:
server-side pagination, server-side search, and a bulk endpoint that can target
**all rows matching the current filter**, not just the loaded page.

## Decisions

- **Offset pagination + total**, not cursor. An admin table wants page numbers,
  a total count, and jump-to-page — offset + a `COUNT(*)` gives that; cursor only
  gives next/prev. Platform skills are a curated, bounded set (low thousands worst
  case), so offset's deep-page cost is irrelevant. The existing cursor variant of
  `list_platform_skills` is replaced (only this endpoint + its tests consumed
  `next_cursor`).
- **Search `q`** — case-insensitive `ILIKE` over `name` + `description` (the two
  fields shown). Combined with the existing `status` / `category` filters (AND).
- **Bulk by filter, not just ids** — the whole point of server-side batch: a
  `POST /v1/platform/skills/batch` that applies a patch (`status` and/or
  `pinned`) to either an explicit id list (the page selection) OR everything
  matching a `{status, category, q}` filter (true "select all N matching" across
  pages). One atomic `UPDATE`, returns the affected count.

## Backend

### Store (`SkillStore`: base + sql + memory)
- `list_platform_skills(*, status, category, q=None, offset=0, limit=50) ->
  tuple[list[Skill], int]` — returns `(page_items, total_matching)`. Drops the
  `cursor` param + `next_cursor` return. SQL: `WHERE tenant_id IS NULL` + filters
  + `q` → `name ILIKE %q% OR description ILIKE %q%`; `total` via a `COUNT(*)` of
  the same predicate; page via `ORDER BY created_at DESC, id` + `OFFSET/LIMIT`.
- `bulk_update_platform_skills(*, ids=None, filter=None, status=None,
  pinned=None) -> int` — exactly one of `ids` / `filter`. Atomic
  `UPDATE skill SET (status?, pinned?, updated_at, state_changed_at?) WHERE
  tenant_id IS NULL AND (id = ANY(ids) | <filter predicate>)`; returns rowcount.
  `state_changed_at` bumped only when `status` changes (mirrors `set_status`).
  Memory store mirrors the predicate.

### API (`platform_skills.py`)
- `GET ""` — add `q` + `offset` Query params; response `{items, total}` (drop
  `next_cursor`). Still system_admin-only + `bypass_rls_session`.
- `POST /batch` — system_admin. Body:
  ```
  { patch: {status?: SkillStatus, pinned?: bool},   # ≥1 field, validated
    ids?: UUID[<=200],                               # explicit page selection, OR
    filter?: {status?, category?, q?} }              # all matching
  ```
  Exactly one of `ids` / `filter` (422 otherwise); empty `patch` → 422. Calls
  `bulk_update_platform_skills`; returns `{updated: int}`. One audit row
  (`SKILL_STATUS_CHANGE` / a bulk marker) with count + filter/id-count (no
  per-row spam). Cap ids at 200 (matches `_MAX_BATCH_SKILLS`).

## SDK (`api/platform-skills.ts`)
- `ListPlatformSkillsParams`: add `q`, `offset`. `PlatformSkillList`:
  `{items, total}` (drop `next_cursor`).
- `bulkUpdatePlatformSkills(body) -> {updated: number}`.

## Frontend (`SettingsPlatformSkills.tsx`)
- **State**: `page`, `pageSize` (default 20), `total`, `q` (debounced 300ms),
  `statusFilter`. Refetch on any change. Table `pagination={{current, pageSize,
  total, showSizeChanger}}` driven server-side (`onChange` → setPage/pageSize).
- **Search box** + a status filter `Select` above the table (aria-labelled).
- **Batch**: the existing toolbar now offers two scopes when a filter/search is
  active: "selected on this page" (ids) and "all N matching" (filter). Lock /
  unlock / archive / activate call `bulkUpdatePlatformSkills` with the chosen
  scope, then refetch + clear selection. Partial failure surfaced.
- Row selection persists per-page only (server pages); the "all matching" button
  is what makes cross-page bulk correct.

## Tests
- Store: `q` filters name+description; `total` correct under filter; offset
  paging; `bulk_update` by ids and by filter (count + state_changed_at on status).
- API: list `q`/`offset`/`total`; batch ids-mode + filter-mode + validation
  (both/neither → 422, empty patch → 422, tenant 403).
- SDK: param wiring + envelope.
- Frontend vitest: search refetches; pagination change refetches; "all matching"
  batch posts a filter not ids; label-resolves guard (no raw i18n keys).
- e2e: paginate, search narrows, bulk-archive-all-matching, axe clean.

## Non-goals
- Full-text ranking (ILIKE substring is enough for a curated library).
- Tenant skills list (`/v1/skills`) — same pattern can follow if needed; out of
  scope here.
