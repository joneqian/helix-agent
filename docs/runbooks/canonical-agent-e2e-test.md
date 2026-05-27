# Canonical Agent 端到端测试 SOP

> M0 → M1 Gate 准入测试。覆盖 [STREAM-M-DESIGN](../streams/STREAM-M-DESIGN.md)
> § 2.1 SLO + § 2.2 canonical agent 端到端 6 条 + § 2.3 eval baseline +
> § 2.4 安全验收 + § 2.5 数据保护演练。
>
> 此文档是**操作手册**(逐条命令可粘贴)。Gate 退出决策的判定标准在
> [`m0-m1-gate.md`](./m0-m1-gate.md) § 5.1 GO Criteria。

---

## 0. 测试目标 + 范围

### 0.1 测试什么

| 维度 | 来源 | 条数 |
|------|------|------|
| **A. 能力级 eval baseline** | STREAM-M § 2.3 | 14 项 capability(J.1-J.15,J.13 除外)|
| **B. canonical agent 端到端 6 条** | STREAM-M § 2.2 | 6 项端到端用户场景 |
| **C. 系统级 SLO 数据采集** | STREAM-M § 2.1 | 8 项 SLO 指标可被 Prometheus 拉到 |
| **D. 安全验收** | STREAM-M § 2.4 | gVisor 7/7 + cross-tenant 3 项 |
| **E. 数据保护演练** | STREAM-M § 2.5 | PG / WORM / KMS / Volume 各 1 次 |

**A/B/C 是日常 dev 环境就能跑的;D/E 必须有 staging Linux 主机才能完整跑。**

### 0.2 测试不包含

- 30 天观察期本身(本文是把 Gate 入场前的能力跑通,30 天观察用 `m0-m1-gate.md` § 1)
- 真实 LLM provider 长跑(只在 Phase 2/3/4/5 各打 1-3 个真实 turn 验证;其余用 mock_provider)
- 多 region / 跨 AZ 灰度

---

## 1. 测试矩阵 + 顺序

执行**按 Phase 顺序**进行 — 每个 Phase 是下一个 Phase 的前置(Phase 6/7 之间可并行)。

| Phase | 名称 | 估时 | 必需环境 | 阻塞下游 |
|-------|------|------|---------|---------|
| **Phase 0** | 前置准备 + canonical agent manifest 入仓 | 0.5-1d | dev | 全部 |
| **Phase 1** | 能力级 eval baseline 重产 + diff | 0.5d | dev | — |
| **Phase 2** | 多轮对话 + 跨 thread 长记忆 | 0.5d | dev | — |
| **Phase 3** | 持久工作区 + hibernate restore | 0.5d | dev | — |
| **Phase 4** | artifact + 审批门 | 0.5d | dev | — |
| **Phase 5** | 多模态(图像)输入 | 0.5d | dev | — |
| **Phase 6** | SLO 8 项指标采集联调 | 0.5d | dev + Prometheus | — |
| **Phase 7** | 安全 + 数据保护(staging) | 1-2d | staging Linux | — |

**整段累计:4-6 工作日**(Phase 7 因为要打 staging 演练,实际占 1-2 天)。

---

## Phase 0 — 前置准备

### 0.1 dev 环境拉起 + 健康检查

```sh
cd /Users/mac/src/github/jone_qian/helix-agent

# 1. 拉最新 main
git checkout main && git pull --ff-only

# 2. 启动 docker-compose 全栈
cd infra
docker compose --profile full up -d

# 3. 等所有容器就绪(60s)
docker compose ps
# 期望:control-plane / postgres / pgbouncer / redis / sandbox-supervisor /
#       credential-proxy / minio / prometheus / grafana / loki / tempo
#       状态都是 healthy 或 Up

# 4. healthcheck
curl -sS http://localhost:8000/healthz/ready | python3 -m json.tool
# 期望:{"status": "ready", "checks": {"postgres": "ok", "redis": "ok", ...}}
```

**失败排查**:
- 容器起不来 → `docker compose logs control-plane`,常见 DB 未 migrate(`docker compose exec control-plane alembic upgrade head`)
- `ready=false` 但容器是 Up → 看 `checks` 里哪个失败,对应排查 `postgres.md` / `sandbox.md`

### 0.2 创建 canonical agent manifest 并落仓库

⚠️ **仓库当前没有 canonical agent yaml,这一步必须先做**。

新建 `manifests/canonical-agent/v1.0.0.yaml`(或团队约定路径),内容大致:

```yaml
apiVersion: helix.io/v1
kind: Agent
metadata:
  name: canonical
  version: "1.0.0"
  tenant: platform-eng
spec:
  tenant_config: {}
  model:
    provider: anthropic
    name: claude-sonnet-4-5
    fallback_chain:
      - {provider: anthropic, name: claude-haiku-4-5-20251001}
  system_prompt:
    template: |
      你是 helix canonical agent — per-user 持久 agent。
      用户=公司的员工/客户;租户=公司。
      你有跨会话的长期记忆、可访问的工作区 /workspace、可调用工具。
  sandbox:
    resources: { cpu: "1.0", memory: "1Gi" }
    network:
      egress: proxy
      allowlist: ["api.anthropic.com"]
    filesystem:
      readonly_root: true
      writable: ["/workspace"]
  tools:
    # canonical agent 至少要打开:web_search / file_io / code_exec
    enabled_skills:
      - {name: web_search, version: "*"}
      - {name: file_io, version: "*"}
      - {name: code_exec, version: "*"}
  memory:
    long_term:
      enabled: true
      embedder: helix-fake-keyword-embedder-v1  # M0 用 fake;Phase 7 staging 切真实
  hitl:
    enabled: true
    triggers:
      - on_action: code_exec
        match: "rm -rf|sudo|curl.*\\|.*sh"
  multimodal:
    vision: true  # supports_vision 主模型走 content block;否则 ask_image
```

入仓 + 注册:

```sh
# 1. 写入仓库
mkdir -p manifests/canonical-agent
$EDITOR manifests/canonical-agent/v1.0.0.yaml
# 粘贴上面内容(根据实际 Skill 名称调整)

# 2. 通过 control-plane API 注册
TENANT_ID=$(curl -sS -X POST http://localhost:8000/v1/tenants -H 'Content-Type: application/json' -d '{"name":"platform-eng"}' | jq -r .data.id)
USER_TOKEN="<本地 keycloak 或 dev 调试 token>"

curl -sS -X POST http://localhost:8000/v1/agents \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d @<(jq -Rn --rawfile y manifests/canonical-agent/v1.0.0.yaml '{manifest: $y}')
# 期望:201 Created,返回 spec_id + sha

# 3. 验证已注册
curl -sS http://localhost:8000/v1/agents -H "Authorization: Bearer ${USER_TOKEN}" | jq .
# 期望:items 列表里有 name=canonical version=1.0.0
```

**或者**通过 Admin UI:
1. 浏览器开 `http://localhost:5173/agents`
2. 点 `New Agent` → 选 `Upload YAML` → 选 `manifests/canonical-agent/v1.0.0.yaml`
3. 验证列表里出现 `canonical 1.0.0`

### 0.3 前置 Checklist(全部 ✅ 才能进 Phase 1)

- [ ] docker compose 全栈 healthy
- [ ] `/healthz/ready` 返回 ready
- [ ] `manifests/canonical-agent/v1.0.0.yaml` 已 commit 入仓库
- [ ] `POST /v1/agents` 注册返回 201
- [ ] `GET /v1/agents` 列表能看到 canonical 1.0.0
- [ ] Admin UI(localhost:5173)能看到 canonical agent

---

## Phase 1 — 能力级 eval baseline 重产 + diff

目标:确认当前 main 跑出的 baseline 等于 checked-in baseline(`tools/eval/baselines/m0_gate_baseline.yaml` 已记录的 14 capability 全 PASS)。

### 1.1 跑 baseline

```sh
cd /Users/mac/src/github/jone_qian/helix-agent

# 1. 安装 eval 依赖(如未装)
uv sync

# 2. 跑 baseline,写到临时文件
.venv/bin/python tools/eval/run_baseline.py --out /tmp/baseline-phase1.yaml

# 3. diff capability 分数(忽略 metadata)
diff <(yq '.capabilities' tools/eval/baselines/m0_gate_baseline.yaml) \
     <(yq '.capabilities' /tmp/baseline-phase1.yaml)
```

**期望**:diff 为空(所有 capability 分数 100% 一致,只 metadata 字段变)。

### 1.2 单独 capability 抽查

抽查 3 个最复杂的(J.1 plan_execute / J.3 memory_recall / J.6 multimodal):

```sh
# J.1 plan_execute(LLM-judge,需要 ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=<key> .venv/bin/pytest tools/eval/test_plan_execute.py -v

# J.3 memory_recall
.venv/bin/pytest tools/eval/test_memory_recall.py -v

# J.6 multimodal
.venv/bin/pytest tools/eval/test_multimodal.py -v
```

**期望**:全部 PASS。

### 1.3 Phase 1 Checklist

- [ ] `run_baseline.py` 写出的临时文件 diff main 上 baseline = 空
- [ ] J.1 / J.3 / J.6 单独 pytest 全 PASS
- [ ] 任何 capability `status: PASS` 转 `FAIL` → **STOP,P0 升级**

---

## Phase 2 — 多轮对话 + 跨 thread 长记忆

对应 STREAM-M § 2.2 第 ① 条:**多轮对话跨会话保持记忆**(J.3 long-term memory 跨 thread 召回,K6/K7 CRUD/DLQ 闭环)。

### 2.1 测试场景

**用户故事**:用户 A 在 thread #1 告诉 agent "我在做 Stream M 的 Gate 验收",在 thread #2 问 "我最近在做什么" — agent 应能召回。

### 2.2 操作步骤

通过 Admin UI Playground(localhost:5173/agents/canonical/1.0.0/playground):

```
# Thread #1
user> 我在做 Stream M 的 Gate 验收,正在跑 canonical agent 端到端测试。
agent> [记录到长期记忆]
user> 请记住我现在的工作。
agent> [写 memory key="current_work" value="Stream M Gate 验收"]
```

新开 Thread #2:

```
# Thread #2
user> 我最近在做什么?
agent> 你在做 Stream M 的 Gate 验收,正在跑 canonical agent 端到端测试。
```

### 2.3 后端验证

```sh
# 1. 列 user 的 long-term memory
curl -sS http://localhost:8000/v1/memory?kind=long_term \
  -H "Authorization: Bearer ${USER_TOKEN}" | jq .
# 期望:items 里有 current_work 这条记忆

# 2. cross-tenant 隔离验证(另起一个 tenant 的 user 应看不到)
curl -sS http://localhost:8000/v1/memory?kind=long_term \
  -H "Authorization: Bearer ${OTHER_TENANT_TOKEN}" | jq '.items | length'
# 期望:0(或不含 current_work)

# 3. 在 Admin UI /memory 也能看到这条记忆
```

### 2.4 Phase 2 Checklist

- [ ] Thread #2 能复述 Thread #1 的内容
- [ ] `/v1/memory` 能列出 current_work 记忆
- [ ] cross-tenant 用 OTHER_TENANT_TOKEN 看不到这条记忆
- [ ] Admin UI /memory 页能编辑这条记忆(走 H.4 PR 2 path)

---

## Phase 3 — 持久工作区 + hibernate restore

对应 STREAM-M § 2.2 ② + ③:**持久工作区跨 run 留存** + **空闲 hibernate + 快速 restore**。

### 3.1 测试场景

agent 在 /workspace 写一个文件 → run 结束 → 等 TTL reaper 回收 sandbox →
重新发消息触发 cold start → 文件应仍可读 → 冷启动 P95 < 5s。

### 3.2 操作步骤

```
# Step 1 - 通过 Playground
user> 在 /workspace/notes.md 写入 "Gate verification notes - 2026-05-27"
agent> [执行 file_io,写文件]
user> 验证文件存在 → cat /workspace/notes.md
agent> Gate verification notes - 2026-05-27
```

```sh
# Step 2 - 触发 TTL reaper 回收(或等自然 TTL)
# 强制回收当前 sandbox(通过 admin API,需 system_admin):
curl -sS -X POST http://localhost:8000/v1/sandboxes/reap?force=true \
  -H "Authorization: Bearer ${SYSADMIN_TOKEN}"
# 期望:reaped_count >= 1
```

```
# Step 3 - 回 Playground 继续对话
user> cat /workspace/notes.md
agent> Gate verification notes - 2026-05-27   ← 文件仍在
```

```sh
# Step 4 - 抓本次 run 的冷启动延迟
curl -sS 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95, sum by (le)(rate(helix_sandbox_cold_start_seconds_bucket[5m])))' | jq .
# 期望:P95 < 5.0
```

### 3.3 Phase 3 Checklist

- [ ] sandbox 被回收后,文件 `/workspace/notes.md` 仍可读
- [ ] `helix_sandbox_cold_start_seconds` P95 < 5s
- [ ] Admin UI Run Detail 页能看到 sandbox lifecycle 事件(cold_start → idle → reaped → cold_start)

---

## Phase 4 — artifact + 审批门

对应 STREAM-M § 2.2 ④ + ⑤:**artifact 跨 thread 可访问** + **审批门跑通**。

### 4.1 artifact 测试

```
# Thread #3 - 创建 artifact
user> 把当前 /workspace/notes.md 作为 artifact 保存,名字 "gate-notes"
agent> [调用 artifact 工具] → 保存 artifact gate-notes v1
```

```sh
# 验证 artifact 已写入
curl -sS http://localhost:8000/v1/artifacts \
  -H "Authorization: Bearer ${USER_TOKEN}" | jq '.items[] | select(.name=="gate-notes")'
# 期望:items 里有 name=gate-notes version=1
```

```
# Thread #4 - 跨 thread 访问
user> 列出我所有的 artifacts
agent> [列表] → gate-notes v1
user> 下载 gate-notes v1 并显示内容
agent> Gate verification notes - 2026-05-27
```

### 4.2 审批门测试

```
# Thread #5
user> 帮我执行 rm -rf /workspace/notes.md
agent> ⚠️ 危险操作 — 已暂停等待审批(interrupt 触发)
```

```sh
# 后端验证 — 应有 pending approval
curl -sS http://localhost:8000/v1/runs?status=awaiting_approval \
  -H "Authorization: Bearer ${USER_TOKEN}" | jq '.items[0]'
# 期望:有一条 run 状态 awaiting_approval,reason 包含 "rm -rf"

# Admin UI 操作:
# 1. 开 /runs 列表 → 找到 awaiting approval 那条 run
# 2. 打开 Run Detail 页 → ApprovalCard
# 3. 点 Approve → run resume → audit_log 写入 APPROVAL_GRANTED
# 4. 或点 Reject → run 标 failed → audit_log 写入 APPROVAL_DENIED

# 验证 audit trail
curl -sS http://localhost:8000/v1/audit?action=approval_granted \
  -H "Authorization: Bearer ${USER_TOKEN}" | jq '.items[0]'
# 期望:有审批通过的 audit entry
```

### 4.3 Phase 4 Checklist

- [ ] artifact 跨 thread 可列 + 可下载
- [ ] cross-tenant 拒绝(用 OTHER_TENANT_TOKEN 取不到 gate-notes)
- [ ] 危险操作触发 interrupt
- [ ] Admin UI ApprovalCard 可 Approve / Reject
- [ ] Resume 后 run 状态变化:awaiting_approval → running → completed/failed
- [ ] Audit log 有完整 trail(APPROVAL_REQUESTED → APPROVAL_GRANTED → ACTION_EXECUTED)

---

## Phase 5 — 多模态(图像)输入

对应 STREAM-M § 2.2 ⑥:**多模态输入**(J.6 Path A + Path B 均在 staging 跑通真实图像)。

### 5.1 Path A — 主模型支持视觉(content block)

```sh
# 上传图片到 uploads
curl -sS -X POST http://localhost:8000/v1/uploads \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -F "file=@/path/to/some/screenshot.png" | jq .
# 拿 upload_id
```

```
# Playground - 主模型是 claude-sonnet-4-5(supports_vision=true)
user> [附加 upload_id 对应的图片] 描述这张图
agent> 这是一张 ... 的截图,我看到 ...
```

### 5.2 Path B — `ask_image` 工具 + 单独 VL 模型

把 canonical manifest 临时改为不支持视觉的模型(如 GPT-3.5),验证 fallback:

```yaml
# 临时修改 manifests/canonical-agent/v1.0.0.yaml
spec:
  model:
    provider: openai
    name: gpt-3.5-turbo  # supports_vision=false
```

```
# Playground - 主模型 GPT-3.5 不支持视觉,期望走 ask_image 工具
user> [附加 upload_id] 描述这张图
agent> [调用 ask_image 工具] → 这是一张 ...
```

### 5.3 Phase 5 Checklist

- [ ] Path A:主模型直接看到图,回答合理
- [ ] Path B:主模型不支持视觉,自动调 ask_image,回答合理
- [ ] 测试完后**还原 manifest 为 sonnet-4-5**

---

## Phase 6 — SLO 8 项指标采集联调

对应 STREAM-M § 2.1 — 验证 8 项 SLO 指标都能被 Prometheus 拉到,K10 大盘有数据。

### 6.1 触发足够流量

跑 5 个 thread,每个 thread 3-5 个 turn,确保指标有样本:

```sh
.venv/bin/python tools/eval/run_baseline.py --warmup
# (如果 run_baseline 不支持 warmup,改为手工 5 个 thread × 5 turn 真实对话)
```

### 6.2 逐项 Prometheus 查询

8 项查询(完整列表见 [`m0-m1-gate.md` § 1.2](./m0-m1-gate.md#12-daily-slo-check)):

```sh
PROM=http://localhost:9090

# 1. 可用性 5xx 错误率
curl -sS "${PROM}/api/v1/query?query=helix:sli:control_plane_availability:ratio5m" | jq .data.result[0].value[1]
# 期望:>= 0.999

# 2. TTFT P95
curl -sS "${PROM}/api/v1/query?query=histogram_quantile(0.95,sum%20by%20(le)(rate(helix_session_ttft_seconds_bucket[1h])))" | jq .data.result[0].value[1]
# 期望:< 2.0

# 3. End-to-end P95
curl -sS "${PROM}/api/v1/query?query=histogram_quantile(0.95,sum%20by%20(le)(rate(helix_session_duration_seconds_bucket{outcome=\"success\"}[1h])))" | jq .data.result[0].value[1]
# 期望:< 30.0

# 4. SSE 流断裂率
curl -sS "${PROM}/api/v1/query?query=sum(rate(helix_llm_stream_stale_total[1h]))/sum(rate(helix_llm_tokens_total[1h]))" | jq .data.result[0].value[1]
# 期望:< 0.0005

# 5. Sandbox 冷启动 P95
curl -sS "${PROM}/api/v1/query?query=histogram_quantile(0.95,sum%20by%20(le)(rate(helix_sandbox_cold_start_seconds_bucket[1h])))" | jq .data.result[0].value[1]
# 期望:< 5.0

# 6. Durable resume P95
curl -sS "${PROM}/api/v1/query?query=histogram_quantile(0.95,sum%20by%20(le)(rate(helix_durable_resume_seconds_bucket[1h])))" | jq .data.result[0].value[1]
# 期望:< 1.0

# 7. Memory recall@5
.venv/bin/python tools/eval/memory_recall.py tools/eval/datasets/memory_recall/zh_en_seed.yaml | jq .recall_at_5
# 期望:>= 0.7

# 8. P0 事故数 — 手工核查
ls docs/incidents/2026-05/ 2>/dev/null | wc -l
# 期望:= 0(本测试期间无 P0)
```

### 6.3 Grafana 大盘联调

打开 Grafana(localhost:3000),进 `Helix — Overview` 大盘,验证 8 项 panel 都有数据点(不是 No data)。

### 6.4 Phase 6 Checklist

- [ ] 8 项 Prometheus query 全部返回数据(非 NaN / empty)
- [ ] 8 项数值都在 Gate 阈值内
- [ ] Grafana `Helix — Overview` 大盘 panel 全部有数据

---

## Phase 7 — 安全 + 数据保护(staging)

⚠️ **必须 staging Linux 主机**,macOS 跑不动 gVisor。

### 7.1 gVisor 7/7 沙盒安全用例

```sh
# 在 staging Linux 主机上
ssh staging-host
cd /opt/helix-agent
cd services/sandbox-supervisor
.venv/bin/pytest tests/integration/test_gvisor_security.py -v
```

**期望**:7/7 PASS,含 `test_gvisor_cve_2019_5736_poc_fails` + `test_gvisor_timing_isolation`。

### 7.2 Cross-tenant 测试

```sh
.venv/bin/pytest \
  services/control-plane/tests/test_sse_cross_tenant.py \
  packages/helix-persistence/tests/test_memory_recall_cross_tenant.py \
  services/control-plane/tests/test_artifact_cross_tenant.py -v
```

**期望**:全部 reject(测试断言异常被正确抛出)。任何静默通过 → **P0**。

### 7.3 数据保护演练(各 1 次)

| 演练 | Runbook | 命令摘要 |
|------|---------|---------|
| PG 恢复 | [pg-restore.md](./pg-restore.md) | dump staging DB → restore 到临时 DB → 验证表 row count |
| WORM 恢复 | [audit-restore.md](./audit-restore.md) | export audit 段 → re-ingest → 验证 hash 匹配 |
| KMS 轮换 | (K13 drill,待补 runbook) | rotate KEK → 重读旧加密数据 → 验证解密成功 |
| Volume restore | [volume-restore.md](./volume-restore.md) | J.15 备份 → 新卷 restore → 验证文件 hash |

每项演练写入 `gate-log/drills/<date>-<drill>.md`(per `m0-m1-gate.md` § 4)。

### 7.4 Phase 7 Checklist

- [ ] gVisor 7/7 全 PASS
- [ ] cross-tenant 3 项测试全 reject
- [ ] PG 演练成功
- [ ] WORM 演练成功
- [ ] KMS 演练成功
- [ ] Volume restore 演练成功
- [ ] 所有 staging 演练写入 `gate-log/drills/`

---

## 8. 总验收清单(进 Gate 30 天观察期前)

所有 Phase 都 ✅ 才能开 30 天 Gate 窗口(per `m0-m1-gate.md` § 0):

| 维度 | Phase | Status |
|------|-------|--------|
| A. eval baseline | Phase 1 | ☐ |
| B. canonical agent 端到端 6 条 |  |  |
| &nbsp;&nbsp;① 多轮对话长记忆 | Phase 2 | ☐ |
| &nbsp;&nbsp;② 持久工作区 | Phase 3 | ☐ |
| &nbsp;&nbsp;③ hibernate restore | Phase 3 | ☐ |
| &nbsp;&nbsp;④ artifact 跨 thread | Phase 4 | ☐ |
| &nbsp;&nbsp;⑤ 审批门 | Phase 4 | ☐ |
| &nbsp;&nbsp;⑥ 多模态 | Phase 5 | ☐ |
| C. SLO 8 项采集 | Phase 6 | ☐ |
| D. 安全 sandbox 7/7 | Phase 7 | ☐ |
| D. 安全 cross-tenant 3 项 | Phase 7 | ☐ |
| E. PG / WORM / KMS / Volume 演练 | Phase 7 | ☐ |

**全 ✅ → 打开 Gate 30 天窗口(`m0-m1-gate.md` § 0 写 commit sha + 日期)**。
任一 ❌ → 进 retro,修完重新跑那个 Phase。

---

## 9. 常见失败 + 处理

| 症状 | 可能原因 | 处理 |
|------|---------|------|
| Phase 0 `POST /v1/agents` 401 | token 未注入 / 过期 | `keycloak admin login` 重发 / 用 dev token |
| Phase 0 manifest 校验失败 `MANIFEST_VALIDATION` | YAML 字段不符合 AgentSpec | 看 control-plane log error 详细 path |
| Phase 1 baseline diff 不空 | 上游 PR 影响 eval 分数 | retro 找根因;不允许"分数轻微下降但继续观察"|
| Phase 2 Thread #2 没复述 Thread #1 | 长记忆没写入 / embedder 不工作 | 看 `/v1/memory` 列表 + control-plane log search `mem_write` |
| Phase 3 文件丢失 | sandbox volume 没挂 named volume / TTL reaper 把 volume 也删了 | 看 sandbox-supervisor log + `docker volume ls` |
| Phase 4 审批不触发 | manifest `hitl.triggers` regex 不匹配 | 验证 regex `re.search` 命中,看 control-plane log search `hitl` |
| Phase 5 多模态 Path B 不走 ask_image | `supports_vision` 探测错误 | 看 `ModelSpec.supports_vision` 配置 |
| Phase 6 某项 Prometheus query 返回空 | 指标 emitter 没就位 / scrape job 漏 | 查 `tools/observability/rules/` + control-plane `/metrics` |
| Phase 7 gVisor 测试 SKIP | runsc 没装 / kernel 不支持 | staging Linux runner image 装 runsc |

---

## 10. References

- 测试目标定义:[STREAM-M-DESIGN.md](../streams/STREAM-M-DESIGN.md) § 2.1-2.5
- Gate 30 天观察 SOP:[m0-m1-gate.md](./m0-m1-gate.md)
- Eval baseline 制品:`tools/eval/baselines/m0_gate_baseline.yaml`
- SLO 文档:[STREAM-G-DESIGN.md](../streams/STREAM-G-DESIGN.md) § G.1
- Canonical agent 定义:[08-AGENT-CAPABILITY-ASSESSMENT.md](../architecture/08-AGENT-CAPABILITY-ASSESSMENT.md)
