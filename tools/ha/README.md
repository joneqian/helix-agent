# Stream 9.4 — HA-failover live E2E

Proves the orphaned-run **automatic hot-handoff** end to end against a real
two-instance dev stack. CI can't cover this: it needs two live control-plane
processes sharing one Postgres, a real model key (resolved server-side), and an
abrupt `docker kill` mid-run.

## What it proves

1. A run starts on **blue** and durably claims its ownership lease.
2. **blue** is killed mid-run (abrupt crash, no terminal status write) — the run
   is now an orphan: `status=running` with a lease nobody renews.
3. **green**'s `OrphanSweep` detects the expired lease, reclaims it (reclaim CAS
   → exactly-one winner), adopts it, and resumes from the durable LangGraph
   checkpoint via `run_agent(graph_input=None)`.
4. The run reaches `success` under a **different** owner with `reclaim_count >= 1`,
   a `run:failover` audit row exists, and green's
   `helix_run_orphan_reclaimed_total` metric incremented.

## Prerequisites

- Dev stack built with this branch (`make dev-up` — rebuilds the control-plane
  image from the working tree and runs Alembic migration `0081_agent_run_lease`).
- A **second** control-plane instance (green). `make dev-up` excludes green
  because its default host port `8001` collides with the sandbox supervisor, so
  bring it up with the overlay (remaps green to `8002`):

  ```bash
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.ha-e2e.yml \
      --profile full up -d --no-deps control-plane-green
  ```

- An **active domestic-model agent** (deepseek/qwen/…) whose key is resolvable
  server-side, and a dev-login bearer token.

## Run

```bash
export HELIX_API_TOKEN=<a dev-login bearer token>   # never logged
uv run python tools/ha/verify_failover.py            # auto-picks a domestic agent
uv run python tools/ha/verify_failover.py --agent my-agent@1.0.0
```

Exit code is non-zero if failover did not complete cleanly. Lease fields
(`claimed_by` / `reclaim_count`) aren't on the run API, so they're read straight
from Postgres via `docker exec helix-postgres psql` (the dev superuser bypasses
RLS); green's metrics are scraped over its container loopback via `docker exec`,
so green needs no reachable host port.
