# Stream H — Admin UI(设计先行)

> 落实 [docs/ITERATION-PLAN.md](../ITERATION-PLAN.md) § Stream H。
> Admin UI 是 helix-agent 给操作人群(平台 admin / agent 开发者 / 运营)的产品级前端入口。
> Business 系统通过 API 消费 helix 的 per-user 持久 agent 能力 —— **helix 自身不给末端用户做 UI**;
> 末端用户通过 business 系统自己的 UI 与 agent 对话(见 [memory:target-product-form](../../.claude/projects/-Users-mac-src-github-jone-qian-helix-agent/memory/project_target_product_form.md))。

设计先行规则([memory:feedback_design_first_iteration](../../.claude/projects/-Users-mac-src-github-jone-qian-helix-agent/memory/feedback_design_first_iteration.md)):
**任何一行 React 代码落地之前**,先完成 H.1a 的三件套(philosophy + language + mockups);
H.1b+ 的 PR 仅执行已锁定的设计基线,不再原地拍脑袋视觉决策。

---

## 0. 范围澄清(2026-05-25 用户确认)

**原 ITERATION-PLAN H.4(用户面 — per-user 持久 agent 形态)取消** —— Business 系统通过 API
消费 agent,helix 自身不需要给末端用户做对话/工作台 UI。原 H.4 的 memory CRUD / artifact 浏览
/ 沙盒会话查看 等 backend 能力**保留**(K6 memory / J.9 artifact / J.15 sandbox API 不动),
但**改由 business 系统的 UI 消费**;helix Admin UI 中作为 admin 视角的"跨 user / 跨 agent
记忆治理 / artifact 列表"出现在 Memory / Operations 区域。

debug 能力作为 **per-agent Playground tab**(嵌在 Agent 详情页的 tab 内),不是独立产品面。

---

## 1. 范围 & 边界

### 1.1 In-scope

| 子项 | 实现内容 | 关联 |
|------|---------|------|
| **H.1a 设计基线**(3-5 天) | `docs/design/admin-ui-philosophy.md` + `admin-ui-language.md` + `mockups/01..08-*.html` + `mockups/shared/{tokens.css, shell.css}`;**先于 H.1b 任何代码落地** | 本规划 PR1 |
| **H.1b React 19 + Vite + Antd 5 骨架**(5-7 天) | 仓库根 `apps/admin-ui/`(Vite 工程);Antd 5 ConfigProvider 把 `--hx-*` token 接入 design token;i18n(zh-CN/en);路由(`react-router-dom` v7);鉴权(API Key / JWT);CommandPalette(`kbar`);Lucide 图标;dark/light theme toggle | 接 control-plane `/v1/*` API |
| **H.2 Agent / Manifest 管理 + per-agent Playground tab** | Agents 列表 / Monaco YAML 编辑器(实时 Pydantic 校验回显)/ 版本对比 / 历史回滚 / **per-agent Playground tab(debug 会话:左 input + 可改 manifest snippet;右 SSE 消息流 + tool calls + trace timeline)** | 接 B.5 Agent CRUD + runs SSE + J.8 approval |
| **H.3 Runs + Trace + Approval** | thread / run 列表 / SSE 实时事件回放 / Langfuse trace 嵌入 / J.8 审批请求列表 + 批准/拒绝/修改入参面板 | 接 B.6/B.7 + E.5 + J.8 |
| **H.4 治理面 — Memory / Curation / Eval / Skills / Triggers / Settings** | 跨 agent / 跨 user 的治理视图:memory 列表+编辑+删除(接 K6)/ artifact 列表+下载(接 J.9)/ curation 候选评审(接 J.12)/ eval dataset CRUD(接 J.12)/ skill 库(接 J.7)/ trigger 列表(接 J.10)/ Settings(API Key / Service Account / Role Binding / Tenant Quota / Audit, 接 C/D/F/G) | 接 J.7/J.9/J.10/J.12/K.6 + C/D/F/G 治理面 |
| **H.5 docker-compose dev.yml** | 已在 I.1 `--profile full` 落地 | I.1 |

> **H.1a / H.1b 拆两个 PR**:H.1a 是纯文档 + CSS;H.1b 是真 Vite 工程。
> **H.2 / H.3 / H.4** 每个再切 2-3 个 PR,按子能力面切(每个 PR 接 1-2 个 backend router 端到端)。

### 1.2 Out-of-scope(明确推迟)

| 推迟项 | 落地 | 备注 |
|-------|------|------|
| 末端用户对话 UI / 客户工作台 | **不做** | Business 系统通过 API 自建(2026-05-25 用户确认) |
| 营销官网 / 落地页 / pricing | M2+(若有 GTM 时) | 独立产品 |
| 响应式 tablet/mobile | M1 | M0 仅支持 ≥1280px desktop(运营人群不在手机上做 ops) |
| logomark(独立 logo 图形) | 暂不做 | wordmark + DNA glyph favicon 已足够品牌识别 |
| 真实搜索后端(跨资源全文) | M1 | M0 CommandPalette 仅 client-side 模糊 |
| Storybook | 按需 | H.1b 视复用率而定;非 M0 强制 |
| E2E 测试(Playwright)| H.6(未排期) | M0 仅集成测试 happy path |

### 1.3 验收(Stream H Exit Criteria)

- **H.1a**:文档自洽(无 TBD / TODO);8 张 mockup `open *.html` Chrome/Safari/Firefox 渲染正常;dark/light 切换 OK;至少 3 张 mockup axe DevTools / Lighthouse contrast ≥ 4.5:1
- **H.1b**:Vite 工程 `npm run dev` 起 admin-ui 跑通,登录后能看到 Shell + 至少一个空页(Agents 列表 empty state)
- **H.2-H.4** 每个子项:
  - 产品级体验(不仅"能用") —— 键盘可达 / a11y 验证 / dark/light 双过 / i18n 双语完整
  - UI 集成测试 happy path(`@testing-library/react` + 真后端 mock)
  - 接入的 backend router 在 UI 上端到端可见(创建 → 列表 → 详情 → 修改 → 删除)
- **H 整体**:首屏 < 2s(在本地 dev compose 环境);Lighthouse Performance ≥ 90 / Accessibility ≥ 95

---

## 2. 架构

### 2.1 单 SPA,操作端唯一

```
                  ┌─────────────────────────────┐
                  │  apps/admin-ui (Vite SPA)   │
                  │  React 19 + Antd 5 + Lucide │
                  │  Shell: sidebar 220 + top 48│
                  └──────────────┬──────────────┘
                                 │  HTTPS + Bearer(API Key) / JWT
                                 │  SSE for runs / playground
                                 ▼
                  ┌─────────────────────────────┐
                  │  control-plane (FastAPI)    │
                  │  全部 /v1/* router(已 shipped)│
                  └─────────────────────────────┘
```

无 BFF,无 GraphQL,直接打 control-plane REST + SSE。

### 2.2 工程目录(H.1b 阶段建立)

```
apps/admin-ui/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── router.tsx
│   ├── api/                  (control-plane SDK,每个 router 一个 file)
│   │   ├── client.ts         (axios + auth interceptor)
│   │   ├── agents.ts
│   │   ├── runs.ts
│   │   ├── skills.ts
│   │   ├── triggers.ts
│   │   ├── memory.ts
│   │   ├── curation.ts
│   │   ├── eval_datasets.ts
│   │   └── api_keys.ts
│   ├── components/           (helix 自研组件)
│   │   ├── Shell.tsx
│   │   ├── Sidebar.tsx
│   │   ├── Topbar.tsx
│   │   ├── CommandPalette.tsx
│   │   ├── TenantSwitcher.tsx
│   │   ├── TraceViewer.tsx
│   │   ├── MonacoYamlEditor.tsx
│   │   ├── SSELiveLog.tsx
│   │   └── ConfirmDialog.tsx
│   ├── pages/
│   │   ├── agents/           (List, Detail with tabs)
│   │   ├── runs/
│   │   ├── curation/
│   │   ├── memory/
│   │   ├── skills/
│   │   ├── triggers/
│   │   └── settings/
│   ├── theme/
│   │   ├── tokens.css        (从 docs/design/mockups/shared/tokens.css 移植)
│   │   ├── shell.css         (基础排版,Antd 不能覆盖的细节)
│   │   └── antdTheme.ts      (Antd ConfigProvider 主题,把 --hx-* 映射到 Antd token)
│   ├── i18n/
│   │   ├── index.ts          (i18next init)
│   │   └── locales/
│   │       ├── zh-CN.json
│   │       └── en.json
│   ├── icons/                (DNA glyph + 自定义 SVG)
│   └── utils/
└── tests/
```

### 2.3 设计基线 → 工程的映射

| 设计文档产物 | 工程对应位置 |
|---|---|
| `docs/design/mockups/shared/tokens.css` | `apps/admin-ui/src/theme/tokens.css`(直接 copy) |
| `docs/design/mockups/shared/shell.css` | 部分迁移至 `apps/admin-ui/src/theme/shell.css`;Antd 能覆盖的部分用 ConfigProvider |
| `docs/design/admin-ui-language.md` § 3 (component override) | `apps/admin-ui/src/theme/antdTheme.ts` |
| `docs/design/admin-ui-language.md` § 11 (术语表) | `apps/admin-ui/src/i18n/locales/{zh-CN,en}.json` 的 keys |
| `docs/design/mockups/0X-*.html` | `apps/admin-ui/src/pages/*` 的初始视觉参考 |

---

## 3. IA(对应 [philosophy.md § 4](../design/admin-ui-philosophy.md#4-ia-心智模型--agent-是中心实体))

### 一级导航(瘦左边栏,220px)

| Order | label | route | 主要 backend 端点 |
|---|---|---|---|
| 1 | Agents | `/agents` | `/v1/agents` |
| 2 | Runs | `/runs` | `/v1/sessions/*/runs`(跨 agent 视角) |
| 3 | Curation+Eval | `/curation` / `/eval-datasets` | `/v1/curation`, `/v1/eval-datasets` |
| 4 | Memory | `/memory` | `/v1/memory` |
| 5 | Skills | `/skills` | `/v1/skills` |
| 6 | Triggers | `/triggers` | `/v1/triggers` |
| 7 | Settings | `/settings/*` | `/v1/api_keys`, `/v1/service_accounts`, `/v1/role_bindings`, `/v1/tenants/*/quotas`, `/v1/tenants/*/config`, audit |

### Agent 详情页 7 个 tabs(per-agent 视角)

`/agents/:id/{overview,manifest,playground,runs,skills,triggers,memory}`

| Tab | 端点 |
|---|---|
| Overview | `/v1/agents/:id` + 衍生 stats |
| Manifest | `/v1/agents/:id/manifest`(YAML + 版本) |
| **Playground** | `/v1/sessions`(临时 thread)+ `/v1/sessions/:id/runs`(SSE) |
| Runs | `/v1/sessions/*/runs?agent_id=:id` |
| Skills | `/v1/agents/:id/skills`(per-agent skill bindings) |
| Triggers | `/v1/triggers?agent_id=:id` |
| Memory | `/v1/memory?agent_id=:id` |

---

## 4. 关键页面 mockup 索引(详见 [mockups/README.md](../design/mockups/README.md))

| # | 页面 | 对应 H 子项 |
|---|---|---|
| 01 | Agents 列表 | H.2 |
| 02 | Agent 详情 — Overview | H.2 |
| 03 | Agent 详情 — **Playground** | H.2 |
| 04 | Run 详情 + Trace | H.3 |
| 05 | Curation 候选评审 | H.4(Curation) |
| 06 | Memory admin | H.4(Memory) |
| 07 | Settings — API Keys | H.4(Settings) |
| 08 | Cmd+K 命令面板 | H.1b(全局) |

---

## 5. Mini-ADR

### Mini-ADR H-1:Antd 5 + 设计基线 over headless UI / 自研组件库
**Context**:M0 周期紧(2.5-3 周做完 Stream H),从零写组件库不现实;headless UI(Radix / Headless UI)灵活但要补很多无障碍 / state 细节。
**Decision**:用 Antd 5 + helix 设计基线 override —— Antd 自带 a11y / i18n / form / table 全套,我们只要 token + override 几个关键组件细节即可。
**Consequences**:与 Antd 5 升级节奏耦合(可接受);特化组件(CommandPalette / TraceViewer / SSELiveLog / MonacoEditor)仍要自研。

### Mini-ADR H-2:per-agent Playground 而非独立 Sessions 区
**Context**:debug 能力是 helix 操作人群的核心诉求;放哪里取决于谁需要看 + 看的时候手边有什么。
**Decision**:Playground 作为 Agent 详情页 tab,**不独立顶级导航**。理由见 [philosophy.md § 5](../design/admin-ui-philosophy.md#5-operator--debug-双能力同面)。
**Consequences**:跨 agent debug 比较只能开多 tab;后续若数据表明 ops 真有跨 agent 比较高频诉求,M1 再加顶级 Sessions 区(增量,不矛盾)。

### Mini-ADR H-3:dark-first + light 同样产品级
**Context**:LLM ops 长读 trace / log / JSON;dark 适眼。但 light 仍有 screenshot / 打印 / 演示场景。
**Decision**:两个主题都过 WCAG AA + 完整 token 双套;默认 dark;`html[data-theme]` 切换不依赖 `prefers-color-scheme`。
**Consequences**:实施成本 +30%(双 token + 双套对比度验证);收益:覆盖所有真实场景。

### Mini-ADR H-4:CSS variable + ConfigProvider over Tailwind / Styled-components
**Context**:与 Antd 集成 + 主题切换 + 实施成本三角。
**Decision**:用 CSS custom properties(`--hx-*`)+ Antd ConfigProvider 注入 token + 极少 inline override。**不引入 Tailwind**(与 Antd 默认样式冲突 + 学习成本);**不用 styled-components**(运行期成本 + 与 Antd 主题割裂)。
**Consequences**:主题切换 = 改 `<html data-theme>`,纯 CSS,零 JS;Antd token 通过 antdTheme.ts 一处映射;mockup 阶段 token 可直接复用。

### Mini-ADR H-5:Lucide,禁止混用 Antd IconFont
**Context**:Antd 5 自带 `@ant-design/icons`(800+ 图标);Lucide 1500+ 现代风格(线 1.5 / 圆角)。
**Decision**:**全栈用 Lucide**,禁止用 Antd IconFont。Antd 组件需 icon 时显式传 `icon={<LucideIcon />}`。
**Consequences**:bundle 多 ~50KB(可接受;tree-shake 后实际更小);视觉一致性 ↑↑(混用会显得拼接)。

### Mini-ADR H-6:`GET /v1/runs` 跨 thread 索引 — 偿还 Mini-ADR J-41 deferred 项
**Context**:H.1b PR 3 RunDetail 备注里写"There is no cross-thread 'list all runs' endpoint yet (Mini-ADR J-41 keeps the per-thread shape); PR 4 wires a control-plane index when it lands" —— H.3 PR 1 兑现这条挂账。今日 RunStore 只有 `list_by_thread(thread_id, tenant_id)`,跨 thread 列表 = N+1 调用,不可接受。
**Decision**:
- `RunStore` ABC 加两个抽象方法,InMemory + SQL 各加实现:
  - `list_for_tenant(*, tenant_id, status: RunStatus | None = None, limit: int = 100, offset: int = 0) -> list[RunInfo]` — newest first(ORDER BY created_at DESC)
  - `list_all_tenants(*, status, limit, offset) -> list[RunInfo]` — 跨租户;调用方 MUST 包 `bypass_rls_session()`(Stream N 同 [trigger sql.py:117](../../packages/helix-persistence/src/helix_agent/persistence/trigger/sql.py))
- 在 `api/runs.py` 旁加 `build_runs_list_router()` 一个新 router(prefix `/v1/runs`),只挂 `GET /v1/runs?status&tenant_id&limit&offset`;走 Stream N `ensure_tenant_scope` + `applied_scope` 框架,响应字段 `{ items, total, cross_tenant }` 与 agents/triggers 列表对齐。
- 在 `app.py` `include_router(build_runs_list_router())`;复用同一 RunStore 单例。
- 不动现有 `/v1/sessions/{thread_id}/runs/*` 端点 —— 这次只是**加**列表入口,旧的按 thread 查询保留。
**Consequences**:Mini-ADR J-41 的 deferred 项("`GET .../runs` 列表 endpoint → H.3")正式偿还,挂账可在 ITERATION-PLAN J.8 行划除;后续 J.10 trigger run 列表 / J.12 curation 候选评审都能复用 `list_for_tenant` 而不必各自实现。

### Mini-ADR H-7:SSE 实时回放推 M1 — H.3 M0 只做状态轮询
**Context**:H.3 原描述含"SSE 实时回放"。要真做"re-attach to existing run's stream",得改:(1) 新 endpoint `GET .../runs/{id}/events`(SSE 重订阅);(2) `StreamBridge` 支持多消费者;(3) 重连游标处理。— 都是非平凡 backend 工作。Playground tab(H.2 PR 6)已有 live SSE(POST 时同时拿流),所以"new run + 同时观察流"已经覆盖;真正缺的是**事后**回看完成的 run 的事件流。事后回看依赖 trajectory recorder(J.13a)或 event_log,这两个都没 API-fronted。
**Decision**:**M0 RunDetail 仅做状态轮询**(`paused` / `running` 时每 3s `getRun` 一次,terminal 时停);**SSE 实时回放推 M1**(与 J.13a trajectory API 一起做)。审批面板仍可立即操作(已具备所有所需数据);用户事后回看缺历史事件流 —— 在 M0 显式可见的 `(a)` 推迟。
**Consequences**:H.3 M0 体感:Runs 列表 + 详情(状态 + approval + 元数据)+ 状态自动刷新;**不**显示历史事件帧。运维语境足够;开发 / debug 语境用 Playground tab(同 agent 起新 thread 直接看)。M1 再补回看。

### Mini-ADR H-8:Trace 嵌入 = 外链跳 Langfuse,不 iframe — H.3 M0
**Context**:Langfuse 自带完整 trace UI(span 树 / token 消耗 / LLM 输入输出对比),自研一份性价比极低。iframe 嵌入需要 Langfuse staging 部署 + CORS / X-Frame-Options 配置 + 跨域 token 转 —— 都是 backend infra 工作(Stream G.7 大盘正在做)。
**Decision**:**M0 = 外链跳**。RunDetail 给一个"Open in Langfuse"按钮,带 `trace_id` 作为 query / path 参数,新窗口打开。`LANGFUSE_BASE_URL` 配在 `apps/admin-ui/.env`(已有 OIDC env 范式);未配则按钮隐藏,显示"trace_id"明码 + 复制按钮兜底。
**Consequences**:M0 体感:点开一次 Langfuse,完整 trace 即得;不破坏 Antd 5 风格;不引入 iframe 通信 / postMessage 复杂度。M1 与 Stream G.7 一起做 inline embed(若 ops 表态要)。

### Mini-ADR H-9:Approval `override_args` 用 Monaco JSON inline 编辑
**Context**:J.8 API 已支持 `POST .../resume {approved, override_args}` 让审批者修改 agent 提议的工具参数(典型场景:agent 提议删 50 条记录,审批者改成 10 条)。当前 H.1b PR 3 的 RunDetail 只显示 `proposed_args` JSON pretty-print + Approve/Reject 二选,没 override UI。
**Decision**:Approval Alert 里:
- 默认显示 `proposed_args` 为只读 Monaco JSON。
- 顶上加 toggle "Edit arguments" — 切到 edit 模式后 Monaco 可编辑;Approve 按钮文案变 "Approve with edits"(若用户编辑过 JSON;否则正常 "Approve")。
- Save-side 校验:JSON.parse 失败时 Approve 禁用 + 显示语法错误。
- Reject 不需 override(`override_args=null`)。
**Consequences**:复用 H.2 PR 5 已经引入的 `@monaco-editor/react`,零新增 dep;审批者获得正确的"修订入参"能力(原始 J.8 设计目标);M0 关闭 H.1b 的 approval 半成品状态。

---

## 6.5 H.3 详细设计

参考:[`STREAM-J-DESIGN.md § 14`](./STREAM-J-DESIGN.md)(J.8 审批 API + audit + reason_kind 5 类型)/ [`STREAM-N-DESIGN.md`](./STREAM-N-DESIGN.md)(cross-tenant 框架,本节 PR 1 直接复用)。

### 6.5.1 范围 & 出入

| 项 | M0 ✓ | (a) 推迟 |
|---|---|---|
| **跨 thread Runs 列表**(`GET /v1/runs`)| ✓(Mini-ADR H-6) | — |
| **Status / tenant 筛选**(系统 admin 跨租户) | ✓(Stream N 框架) | — |
| **RunDetail 状态轮询**(`paused` / `running` 时每 3s 拉一次) | ✓ | — |
| **Approval Approve / Reject**(继承 H.1b PR 3) | ✓ | — |
| **Approval `override_args` Monaco 编辑** | ✓(Mini-ADR H-9) | — |
| **Approval pending 总数 badge**(顶 nav / Runs 列表头) | ✓ | — |
| **Trace 跳 Langfuse 外链** | ✓(Mini-ADR H-8) | iframe 嵌入推 M1 |
| **历史 SSE 回放** | — | M1 与 J.13a trajectory API 一起(Mini-ADR H-7) |
| **审批 SLA 监控指标** | — | M1+(J.8 § 500 显式推迟项) |
| **多审批人 / 升级链** | — | M1 高级 UI(J.8 § 500) |
| **审计日志 inline 显示** | — | H.4 Audit 查询(同 stream H 后续 PR) |

### 6.5.2 后端契约 — `GET /v1/runs`

```
GET /v1/runs?status=paused&tenant_id=*&limit=50&offset=0
Authorization: Bearer <jwt>

200 OK
{
  "success": true,
  "data": {
    "items": [
      {
        "run_id": "...",
        "tenant_id": "...",
        "thread_id": "...",
        "user_id": "..." | null,
        "status": "paused" | "running" | "success" | "error" | "interrupted" | "timeout" | "pending",
        "is_resume": true | false,
        "error": "..." | null,
        "created_at": "...",
        "updated_at": "...",
        "finished_at": "..." | null
      },
      ...
    ],
    "total": 123,
    "cross_tenant": true | false
  },
  "error": null
}
```

- `tenant_id=*` 仅 `system_admin` 可用;否则 `ensure_tenant_scope` 抛 403 + audit。
- `status` 是单值;多 status 用多 query(`?status=paused&status=running`)推迟。
- `total` 严格等于 `items` 长度(M0 不做 COUNT(*) per-tenant 二次查询;`limit + offset` 决定的窗口,前端用 `items.length < limit` 判 last-page);响应字段保持与 agents/triggers 列表一致。
- 404 不存在;403 Stream N 跨租户拒绝;429 quota(走标准 admission 框架)。

### 6.5.3 前端 IA — `/runs` 页

```
[Runs] (顶 nav 等级,左侧栏一级链接,Bot 图标右下角 Activity 标)

  ┌────────────────────────────────────────────────┐
  │ Breadcrumb  Home / Runs                        │
  │ ┌──────────────────────────────────────────┐   │
  │ │ Runs                  [Approval pending: 3] │
  │ │                                            │   │
  │ │ Status: [All ▼]  Tenant: [Home ▼]  [↻]    │   │
  │ ├──────────────────────────────────────────┤   │
  │ │ Run ID      Status   Thread     Agent      │   │
  │ │ a1b2c3…    paused   t-d4e5…    code-reviewer  │
  │ │ a1b2c3…    success  t-d4e5…    code-reviewer  │
  │ │ ...                                        │   │
  │ └──────────────────────────────────────────┘   │
  └────────────────────────────────────────────────┘
```

- **列**:Run ID(8-char 截断 + tooltip 完整 + 点击进 detail)/ Status(Tag 颜色)/ Thread(8-char 截断 + Link)/ Created at(相对时间 + tooltip 绝对)/ Agent(thread 不直接含 agent 字段;**M0 用 thread query;**或在响应里加一次性 JOIN — 见 § 6.5.5)。
- **筛选**:`Status` Select(单选);`Tenant` 复用 `TenantSwitcher`(`home` / `*` / `UUID`)。无搜索框 M0(Mini-ADR J-41 没 agent_name 索引,加是 M1)。
- **状态**:Empty(无 run)/ Loading(Skeleton)/ Error(Alert)/ Pagination(50 一页;客户端按 `items.length < limit` 判末页;total 仅作 hint)。
- **可点击行**:点行 → `/runs/:thread_id/:run_id`(已有 RunDetail 接住)。

### 6.5.4 前端 IA — RunDetail 增强(M0 增量,不重写)

- 状态轮询(Mini-ADR H-7):当 `run.status in {paused, running, pending}`,每 3s `getRun`;一旦进 terminal,立即停轮询。**前提**:页面可见才轮(`document.visibilityState === "visible"`),否则后台 tab 暂停。
- Approval 区(Mini-ADR H-9):
  - 默认 Monaco read-only(`proposed_args`)。
  - "Edit arguments" toggle → 切 edit;Monaco language=json + 错误标。
  - "Approve" / "Approve with edits"(根据 buffer 是否变过)/ "Reject"。
  - 错误 JSON → Approve 禁用 + 显示 `JSON.parse` 错。
- Trace 跳转(Mini-ADR H-8):
  - 顶 toolbar 显示 `trace_id` 8-char + 复制按钮。
  - 若 `VITE_LANGFUSE_BASE_URL` 配置 → 加按钮 "Open in Langfuse"(target=_blank);否则只显示 trace_id。
- Approval pending badge:左侧主导航 Runs 项右侧加红点(`useQuery` 每 60s 拉 `GET /v1/runs?status=paused&limit=1` 看 `total`;0 时不显示)。

### 6.5.5 已知不解决的耦合

- **RunInfo 不含 `agent_name`**:`agent_run` 表只存 `(run_id, thread_id, tenant_id, user_id, status, ...)`;agent 信息住 `thread_meta`。M0 RunsList "Agent" 列要么(a) 每条 run 多查一次 `thread_meta`,要么(b) 在 `GET /v1/runs` 服务端做一次 JOIN 并把 `agent_name + agent_version` 加进响应。
  - **决策**:走(b)。响应字段加 `agent_name: str | None` / `agent_version: str | None`(thread 可能已删 → null)。这不变更 `RunInfo` DTO 持久层 schema,仅在 API 层组合;`build_runs_list_router` 取数后对每个 thread 查一次 thread_meta(M0 量级 ≤ 50 行,N+1 可接受;M1 改成 SQL JOIN)。
- **Trace ID 不直接挂在 `RunInfo`**:trace_id 来自 OTel,在 SSE `metadata` 事件里;不在 `agent_run` 行。M0 RunDetail 的 trace_id = 从 SSE metadata 接到的最新 trace(对 paused / running 有;对 terminal 没有 — 显示"trace 已结束,见 Langfuse 历史")。M1 把 trace_id 持久到 `agent_run` 表(expand-contract 加列)。
- **`override_args` JSON Schema 校验**:M0 仅做 JSON.parse 客户端校验;后端 J.8 resume 接 `override_args: dict` 不做 schema 校验(已有 tool 模板内部校验)。

### 6.5.6 PR 拆分

| PR | 范围 | 估时 |
|---|---|---|
| **H.3 PR 1**(原 PR7 拆出)| Backend `GET /v1/runs` + RunStore `list_for_tenant` / `list_all_tenants` + SDK `listRuns` + RunsList 页(Mini-ADR H-6)| 2-3 天 |
| **H.3 PR 2** | Approval override_args Monaco UX + 状态轮询(Mini-ADR H-7 / H-9) | 1.5 天 |
| **H.3 PR 3** | Trace 链接外跳(Mini-ADR H-8)+ Approval pending badge + RunsList 体感打磨 | 1 天 |

> 总估时 4.5-5.5 天(略大于原 PR7 的 3-4 天估时,因增加了 backend endpoint)。

### 6.5.7 验收

- **零债 6 条** 每 PR 各跑:无 TODO/FIXME/XXX、ruff/mypy 全过、新增方法测试覆盖、设计文档同步、可观测齐全(`/v1/runs` 加 audit + counter 与现有列表端点一致)、CI 全绿。
- **跨租户冒烟**:`system_admin` 切 "All tenants" → `/runs` 表头 banner `cross-tenant view`;切回 home → banner 消失;两个动作都进 audit。
- **审批端到端**:Playground 起一个 agent → 审批 gate → `/runs?status=paused` 列表见 → 点进 RunDetail → 编辑 override_args → Approve with edits → 状态变 running → 终态 success。
- **a11y**:RunsList axe 0 critical;状态 Tag 颜色不是唯一信号(同时带文字)。

---

## 6. PR 链(预估)

| PR | 内容 | 估时 |
|----|------|------|
| PR1 ✅ | H.1a 设计基线 PR1 — philosophy.md + language.md + STREAM-H-DESIGN.md + tokens.css + shell.css + ITERATION-PLAN 修订 #262 | 1.5 天 |
| PR2 ✅ | H.1a 设计基线 PR2 — 8 张 mockup HTML + mockups/README.md + brand glyph SVG + a11y 自检截图 #263 | 2-3 天 |
| PR3 ✅ | H.1b — `apps/admin-ui/` Vite 工程 scaffold + Antd 5 + i18n + 路由 + 鉴权 + Shell #264 #272 #274 | 3-4 天 |
| PR4 ✅ | H.1b — CommandPalette + TenantSwitcher + 主题切换 + Lucide 接入 + OIDC + 6 SDK + Storybook/E2E #277 #278 #279 #280 #281 | 1-2 天 |
| PR5 ✅ | H.2 — Agent 详情 Manifest tab Monaco YAML(view/edit/save)+ Create Agent drawer + POST/PUT /v1/agents #284 #285 | 3-4 天 |
| PR6 ✅ | H.2 — Agent 详情 Playground tab(fetch+ReadableStream SSE + 色彩分类事件日志 + Stop)#286;**(a) 推迟**:改 manifest 重跑(需后端 ad-hoc spec override)/ 工具调用语义化时间线 / 审批 mid-run UX(H.3) | 3-4 天 |
| PR7a | H.3 PR 1 — Backend `GET /v1/runs` 跨 thread 索引 + SDK + RunsList 页(Mini-ADR H-6)| 2-3 天 |
| PR7b | H.3 PR 2 — Approval `override_args` Monaco UX + 状态轮询(Mini-ADR H-7 / H-9)| 1.5 天 |
| PR7c | H.3 PR 3 — Trace 链接外跳(Mini-ADR H-8)+ Approval pending badge + 体感打磨 | 1 天 |
| PR8 | H.4(Curation+Eval)— 候选评审 + eval dataset CRUD | 2 天 |
| PR9 | H.4(Memory)— per-user memory 列表 + 编辑 + 删除 | 1.5 天 |
| PR10 | H.4(Skills+Triggers)— 跨 agent skill / trigger 列表 + CRUD | 2 天 |
| PR11 | H.4(Settings)— API Keys + Service Accounts + Role Bindings + Quotas + Tenant Config | 2-3 天 |
| PR12 | H.4(Audit)— audit 查询 + 过滤 + 详情 | 1 天 |

> 总估时 25-32 天 = 2.5-3 周(一个全职前端)。可与后端 / 其他 stream 并行。

---

## 7. 验证

### H.1a 验收(本规划 PR1+PR2 完成)
- philosophy.md 6 条原则 → language.md tokens 实现 → mockup 视觉呈现,三层链路自洽
- 8 张 mockup `open mockups/*.html` 在 Chrome / Safari / Firefox 渲染正常
- mockup 顶部主题切换按钮(dark ⇆ light)无破坏性视觉差异
- 至少 3 张 mockup 跑 axe DevTools 报告 0 critical;Lighthouse a11y ≥ 95
- 术语表覆盖所有 mockup 中可见英中字符串
- `tokens.css` + `shell.css` 无外部依赖,无 SCSS,无 build —— 浏览器直接渲染

### Stream H 整体验收(所有 PR 合并后)
1. UI/UX 设计基线文档先于实现合入(H.1a PR1+PR2 在最前) ✓
2. 每个 H.* 子项产品级体验:响应式(≥1280px desktop)/ 键盘可达 / a11y(axe 0 critical)/ 性能(首屏 < 2s, Lighthouse Performance ≥ 90)
3. UI 集成测试覆盖 happy path(`@testing-library/react`)
4. 接入的 B/E/J/K 能力面在 UI 上端到端可见

---

## 修订记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-05-25 | v1.0 | 初稿:设计基线 PR 链 + IA + 工程目录 + 5 个 Mini-ADR + 12 个 PR 估时;H.4 用户面取消,改为治理面;Playground 嵌 per-agent tab |
| 2026-05-25 | v1.1 | H.1a / H.1b / H.2 全部完成(PR1–6,合并 #262–264 / #272 / #274 / #277–281 / #284–286);PR 链表加 ✅ 标记 + #PR 引用;H.2 PR 6 显式推迟项落到 PR 行尾 |
| 2026-05-26 | v1.2 | 加 § 6.5 **H.3 详细设计** + Mini-ADR H-6 / H-7 / H-8 / H-9;原 PR7 拆为 PR7a/b/c 3 个;锁定:`GET /v1/runs` 跨 thread 索引兑现 Mini-ADR J-41 deferred / SSE 实时回放推 M1 / Trace = 外链跳 Langfuse / Approval `override_args` Monaco inline 编辑 |
