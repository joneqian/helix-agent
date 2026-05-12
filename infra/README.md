# Helix-Agent Infra (local dev / dogfood)

Stream A.3 establishes a minimal local stack: **Postgres 16** + **PgBouncer**
in transaction-pooling mode. Matches the M0 deliverable in
[subsystems/23-postgres-scalability § 9](../docs/architecture/subsystems/23-postgres-scalability.md).

## Quick start

```bash
cd infra
docker compose up -d
docker compose ps
```

Services:

| Service     | Port | Purpose                                                    |
|-------------|------|------------------------------------------------------------|
| `postgres`  | 5432 | Direct Postgres access — migrations, psql, pg_dump        |
| `pgbouncer` | 6432 | Connection pool — application traffic                      |

The application **must** point at PgBouncer (`localhost:6432`); migrations
**must** point at Postgres directly (`localhost:5432`) because PgBouncer
transaction mode does not preserve session state across statements.

## Credentials

Defaults (placeholder, dev only):
- user: `helix_agent`
- password: `helix_agent_dev`
- database: `helix_agent_dev`

Override via `.env` or your shell:

```bash
export HELIX_DB_USER=…
export HELIX_DB_PASSWORD=…
export HELIX_DB_NAME=…
```

## Why PgBouncer transaction mode

Per [subsystems/23 § 5.1](../docs/architecture/subsystems/23-postgres-scalability.md#51-pgbouncer-模式选择):

- 1000 client connections → 50 backend connections (10–20× density)
- Required for M0 dogfood under modest concurrency before M2 read replicas

**Application constraints under transaction mode**:

- ❌ No advisory locks that span transactions (`pg_advisory_lock` → use
  `pg_advisory_xact_lock` instead — already in `DbEventStore`).
- ❌ No `LISTEN`/`NOTIFY` (migrate to Redis pub/sub if needed).
- ⚠️ Prepared statements need PgBouncer ≥ 1.21 (this stack ships 1.23.1).
  Helix uses **asyncpg with `statement_cache_size=0`** to sidestep the
  client-side prepared cache entirely — see
  `packages/helix-persistence/src/helix_agent/persistence/database.py`.

## Postgres tuning applied

Database-wide defaults (set by `postgres/init/00-helix-init.sql` on first
boot — production RDS must apply these manually):

- `statement_timeout = 30s`
- `idle_in_transaction_session_timeout = 60s`
- `lock_timeout = 5s`

Server-level (set via `command:` in `docker-compose.yml`):

- `shared_preload_libraries = pg_stat_statements`
- `log_min_duration_statement = 500` (ms — log slow queries to stderr)

Extensions installed:

- `pg_stat_statements`
- `vector` (pgvector) — for long-term memory (M1)

`pg_partman` installation is deferred to M1 alongside actual partitioning
(see [subsystems/23 § 9 M1](../docs/architecture/subsystems/23-postgres-scalability.md#m1--分区--rls--autovacuum-调优)).

## Reset

```bash
docker compose down -v   # wipes postgres-data volume
```
