# Stream MCP-OAUTH — per-user OAuth 2.1 for MCP connectors

> 解锁 OAuth-only 的托管 MCP 连接器(Notion / Linear / Jira / Confluence / Sentry /
> Asana …)。这些 server 的托管端点**只支持交互式 OAuth 2.1 授权码流程**,不接受
> 粘贴静态 token,因此现有 `auth_type ∈ {none, bearer}` 的 catalog 无法接入。
> 本 Stream 给 catalog 增加 `oauth2`,实现 MCP 授权规范要求的 per-user 授权流程。

**拍板(AskUserQuestion):** 授权主体 = **per-user**(每用户授权自己的账号,agent 以
该用户身份访问);首个端到端验证连接器 = **Linear**。

---

## 1. 背景:MCP 授权规范(已核实)

MCP 授权 = **OAuth 2.1 + PKCE(强制)** + 资源/授权服务器**元数据发现**:

1. client 调 MCP server → `401` + `WWW-Authenticate` 指向 **Protected Resource
   Metadata**(RFC 9728)。
2. 从 PRM 发现 **Authorization Server Metadata**(RFC 8414)→ 拿 authorize /
   token 端点。
3. 浏览器跳转 authorize(带 `code_challenge`/PKCE + `state`)→ 用户登录授权 →
   回调带 `code`。
4. `code` + `code_verifier` 换 `access_token`(短期)+ `refresh_token`。
5. 后续以 `Authorization: Bearer <access_token>` 调 MCP server;过期用
   refresh_token 续。

动态客户端注册(DCR / RFC 7591)已被规范标注 deprecated(转向 Client ID Metadata
Documents);**本 Stream 优先用静态预注册的 client_id**(在平台为每个连接器登记一次
OAuth app),DCR/CIMD 留后续。

## 2. 现状与改造点(grep 核实)

- `CatalogAuthType` / `McpServerAuthType` = `Literal["none","bearer"]` →
  **加 `"oauth2"`**(双 Literal:protocol + 任何 control-plane 镜像;[[project_audit_literal_drift]] 同理)。
- orchestrator `MCPServerConfig.auth_type` 已含 `oauth2`,但 `_build_mcp_client`
  对 oauth2 **fail-fast**(`MCPOAuthNotImplementedError`,Mini-ADR U-12)→ 本 Stream
  替换为"解析 per-user access token → 注入 Bearer 头(临过期先 refresh)"。
- `Principal.subject_id: str`(用户身份)、`tenant_id: UUID` → 连接按
  **(tenant_id, subject_id, connector)** 维度存。
- `TenantMcpPoolService` 仅按 `tenant_id` 缓存 pool;OAuth 连接器是 per-user →
  **pool 解析要按 (tenant_id, user_id) 维度**(见 Mini-ADR OA-4)。
- token 进 `secret_store`(明文不入 DB,只存 `secret://` ref;沿用 U-11)。

## 3. 数据模型

新表 **`mcp_oauth_connection`**(per-user 连接实例,与 `tenant_mcp_server` 区分:
后者是 bearer/none 的租户级实例,前者是 oauth2 的用户级实例):

| 列 | 说明 |
|---|---|
| `id UUID` PK | |
| `tenant_id UUID` FK, NOT NULL | RLS 租户隔离 |
| `user_id TEXT` NOT NULL | = `principal.subject_id` |
| `catalog_id UUID` FK → mcp_connector_catalog | 来自哪个 catalog 连接器 |
| `name TEXT` | 解析后的 server 名(同 slug 规则) |
| `status TEXT` | `pending`(发起未回调)/ `connected` / `expired` / `revoked` / `error` |
| `access_token_ref TEXT` NULL | `secret://…/access`,临过期由 refresh 刷新 |
| `refresh_token_ref TEXT` NULL | `secret://…/refresh` |
| `token_expires_at TIMESTAMPTZ` NULL | 提前 N 秒触发 refresh |
| `scopes TEXT` | 已授权 scope |
| `resolved_url TEXT` | 实例化时快照(同 W-2 快照原则) |
| `last_refresh_at` / `last_error` | #2 风格的状态可观测(与 health Stream 一致) |
| `created_at` / `updated_at` | |
| unique `(tenant_id, user_id, catalog_id)` | 一个用户对一个连接器一条连接 |

catalog 侧:`auth_type` 增 `"oauth2"`;新增可空列 `oauth_client_id`、
`oauth_scopes`(平台为该连接器登记的 OAuth app 信息)。token 端点/PRM 走运行时发现,
不入库。

**PKCE/state 暂存**:`pending` 连接的 `code_verifier` + `state` 短期存(进程内 TTL
缓存或 `mcp_oauth_connection` 上的临时列 + 过期清理);回调用 `state` 找回。

## 4. 端点(per-user,RBAC `mcp_server`)

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/v1/mcp-servers/catalog/{catalog_id}/oauth/initiate` | 发现 PRM/authz → 生成 PKCE+state → 建 `pending` 连接 → 返回浏览器 authorize URL |
| GET | `/v1/mcp-oauth/callback` | **公网回调**:校验 state(CSRF)→ code+verifier 换 token → 存 secret ref → 置 `connected` → invalidate 该用户 pool |
| GET | `/v1/mcp-servers/oauth/connections` | 列当前用户的 OAuth 连接 + 状态 |
| DELETE | `/v1/mcp-servers/oauth/connections/{id}` | 断开(撤销 + 删 secret + 删行 + invalidate) |

回调是平台公网 redirect URI(部署需登记到各连接器 OAuth app 的 allowlist;`state`
做 CSRF + 关联租户/用户)。

## 5. token 生命周期 / 运行时

- agent 构建时(server-side、用户不在场):按 (tenant_id, user_id) 解析该用户的
  OAuth 连接 → 取 access_token;**临过期(< skew)先 refresh**(refresh_token 换新
  access)→ 注入 `Authorization: Bearer`。
- refresh 失败(被撤销/refresh 过期)→ 连接置 `expired`/`revoked`,该连接器对该
  用户**不可用**(工具不装配 + 状态可见,提示重新授权);不拖垮其余工具。
- `_build_mcp_client` 的 oauth2 分支:从 `auth_config` 解析 access_token_ref(由
  pool 解析层在 refresh 后填入),注入 Bearer。

## 6. per-user pool 解析(OA-4)

`TenantMcpPoolService` 现按 tenant 缓存。引入 **per-(tenant,user) 维度**:OAuth 连接
按用户解析/缓存;bearer/none 的 `tenant_mcp_server` 仍按 tenant。两类合并进该用户
agent 的工具集。invalidate 粒度细化到 (tenant,user)(发起/回调/断开/refresh 失败时)。

## 7. 分阶段(每阶段独立 PR,设计先行已完成)

- **OA-0 设计**(本文档)。
- **OA-1 数据面**:`oauth2` 双 Literal + catalog oauth 列 + `mcp_oauth_connection`
  表/model/store + migration(revision ≤ 32 字符,[[feedback_alembic_revision_id_32_chars]])。
- **OA-2 OAuth 引擎**:PRM/authz 发现 + PKCE + initiate/callback + token 交换 + refresh;
  纯逻辑 + secret 存储,单测覆盖发现/PKCE/state/refresh。
- **OA-3 Linear 垂直切片**:catalog 加 Linear(oauth2)+ per-user pool 解析 +
  `_build_mcp_client` oauth2 分支 + 端到端(发起→回调→agent 用 Linear 工具)。
- **OA-4 per-user pool 维度** + 连接管理端点(list/disconnect)+ 状态可观测。
- **OA-5 扩连接器(env-seed 模板)**:带占位符的 catalog seed 模板 + 启动期
  env-seed loader,占位符填 env 即生效;未填则跳过。见 §13。
- **OA-6 刷新硬化**:pool 构建期惰性刷新(临过期 refresh)+ 失败分类(撤销/瞬态)
  + 状态回写(OA-4 list 暴露)。见 §12。

## 8. 安全

PKCE 强制;`state` 防 CSRF + 绑 tenant/user;redirect URI allowlist;token 仅
`secret://` ref(不入 DB / audit / 日志);scope 最小化;回调严格校验
`state`/`code`;RLS 租户隔离 + 行内 user_id 过滤(用户只见/删自己的连接)。
[[feedback_codeql_clear_text_logging_secret_name]] / [[feedback_codeql_log_injection_request_taint]] 注意脱敏。

## 9. Out of scope

- per-tenant 共享 OAuth 连接(本轮只 per-user;确认过)。
- DCR / CIMD(用静态预注册 client_id;后续按需)。
- 非 MCP 的通用 OAuth(本 Stream 专注 MCP 连接器)。

## 10. Verification

- 发现:对 Linear 端点解析 PRM(RFC 9728)→ authz metadata(RFC 8414)。
- PKCE/state:verifier/challenge 配对正确;回调 state 不匹配 → 拒。
- token:code 换 token 存 secret ref;临过期触发 refresh;refresh 失败置 expired。
- 隔离:用户 A 看不到/删不了用户 B 的连接;RLS 跨租户零行。
- e2e:发起 → 回调(mock 授权服务器)→ agent 以该用户身份成功调用 Linear 工具。
- 降级:连接 expired → 该连接器不装配,其余工具照常。

## 11. CI / 约束

`oauth2` 双 Literal(protocol + control-plane 镜像);migration revision ≤ 32 字符;
pytest `-m "not integration"`(回调/refresh/隔离的真 PG 用例进 integration);
CodeQL 脱敏(token / state 不进日志);每 PR 零技术债 + 同步 ITERATION-PLAN。

## 12. OA-6 token 刷新硬化(设计)

**目标**:access token 临过期时透明换新,连接器不静默掉线;refresh 真正失败(被
撤销)时把连接置终态并经 OA-4 list 提示用户重连。

**惰性刷新(不做后台调度)**:刷新发生在 `UserMcpOAuthPoolService.get_or_build`
内、既有 per-(tenant,user) 锁下(刷新天然串行、无进程内竞态)。后台预刷新不做:不活跃
用户无需新 token,且跨副本调度器的复杂度对收益不成比例(诚实记于"限制")。

**组件 `McpOAuthRefresher`**(`mcp_oauth_refresh.py`,单一职责):
`ensure_fresh(record) -> McpOAuthConnectionRecord | None`。pool 用它替代原 `_usable`:
返回可用 record(必要时已刷新)或 `None`(不可用,不装配该连接器)。

判定(`skew` 默认 60s):
- `status != connected` 或无 `access_token_ref` → `None`。
- token 距过期 > skew → 原样返回(仍可用)。
- 临/已过期:
  - 无 `refresh_token_ref`:已过期 → 置 `expired` + `None`;未过期 → 原样返回。
  - 有 refresh token:经 OA-2 引擎 refresh。
    - 成功 → 覆写既有 secret ref(access、轮换的 refresh)+ 回写 `token_expires_at`/
      `last_refresh_at`/`scopes`、清 `last_error`、置 `connected` → 返回更新后的 record。
    - 终态失败(`invalid_grant` 等)→ 置 `revoked` + `last_error` + `None`。
    - 瞬态失败(网络/5xx):已过期 → 置 `error` + `None`(下次构建重试);未过期 →
      原样返回当前 token(临过期预刷新失败不应弄坏仍有效的 token)。

**引擎增强**:`_post_token` 在非 200 时解析 RFC 6749 §5.2 的 `error` 字段,经
`McpOAuthError.oauth_error` 暴露,供 refresher 区分终态(撤销)vs 瞬态(重试)。

**状态恢复**:成功刷新清 `last_error`——新增 `McpOAuthConnectionPatch.clear_last_error`
(镜像 `clear_flow_state`;Optional=不改语义无法表达"清空")。

**可观测**:结构化日志仅记 `connection_id`(UUID,安全),不记 token/state/请求派生值
([[feedback_codeql_clear_text_logging_secret_name]] / [[feedback_codeql_log_injection_request_taint]]);
状态/过期经 OA-4 list 暴露。刷新是例行系统动作,不新增 `AuditAction`(避免双 Literal 漂移)。

**限制(诚实)**:刷新仅在进程内 per-user 锁下串行;跨副本并发刷新可能在 refresh-token
轮换上竞争(多数 AS 有宽限窗口、且仅在过期边界触发,影响有限)。分布式锁本轮不做。

## 13. OA-5 连接器 env-seed(设计)

**问题**:catalog 现状纯 API 驱动(system_admin 调 `POST /v1/platform/mcp-catalog`
逐条 upsert),无 seed 机制;且 oauth2 连接器需要平台先在各家注册 OAuth app 拿到
`oauth_client_id` 才能填。要在"尚未注册"时先把模板/占位符备好,注册后无缝生效。

**方案**:带占位符的 seed 模板 JSON + 启动期 env-seed loader(补上 W-6 规划的能力)。

- **模板**(`configs/mcp-catalog-seed.json`):**默认空数组 `[]`** —— 不预置任何
  连接器,平台管理员经 admin-ui 目录手工配。需要开箱预置时,往该文件追加
  `McpConnectorCatalogUpsert` 结构条目,`oauth_client_id` 用
  `${MCP_OAUTH_<NAME>_CLIENT_ID}` 占位,URL/transport 按各家文档填。
- **loader**(`catalog_seed.py`,纯逻辑可单测):`load_catalog_seed(raw, env)` 解析
  JSON → 对字符串字段做 `${VAR}` 替换(env 取值)→ 构造校验后的 upsert 列表。
  - 某条目有**未解析占位符**(env 缺)→ **跳过该条**(收集名字),平台照常启动。
  - JSON 非法 / upsert 校验失败 → **fail-fast**(模板本身写错,启动即报,运维即知)。
- **idempotent seed**(`seed_catalog`):对每条 `get_by_name` → 不存在则 `create`
  (`actor_id="catalog-seed"`,bypass RLS 写 NULL-tenant 平台行),存在则跳过(不覆盖
  运维经 API/UI 的改动)。重启幂等。
- **接线**:`settings.mcp_catalog_seed_file: str | None = None`(默认不 seed,向后兼容);
  lifespan 启动期若设置则加载并 seed,log 每条 created/skipped(missing-env)/existing。
- **"填 env 即生效"**:首次启动 env 未填 → 跳过;运维注册拿到 client_id → 填
  `MCP_OAUTH_LINEAR_CLIENT_ID=...` 重启 → get_by_name 缺 → create。无需改模板文件。

**可观测/安全**:`oauth_client_id` 是**公开**的 OAuth client 标识(非 secret),走 env
即可;日志只记**连接器名 + 缺失的 env 变量名**,不记解析后的值
([[feedback_codeql_clear_text_logging_secret_name]])。

**限制(诚实)**:seed 只 create-if-absent,不更新已存在条目;换 client_id / URL 需经
admin API `PATCH`(或先删再 seed)。runbook 注明。模板里的 URL/transport 为默认值,
各家以官方 MCP 文档为准。
