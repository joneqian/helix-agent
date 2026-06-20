# 技能 Marketplace IA — 市场浏览 + 一键启用订阅

> 状态:草案(待评审)。范围:admin-ui 技能"市场"信息架构 + 轻量订阅表/端点 + merged view 标记。
> 延伸 [skill-authoring-ia](./skill-authoring-ia.md)(创作链已交付 #709-718)/ MCP Stream W(对照参照)。

## 0. 一句话

技能是**纯内容**(prompt + tools + supporting files),不需要 MCP 式"实例化成租户副本"。Marketplace 化只补两件:① 一张轻量订阅表 `tenant_skill_subscription`(租户→平台技能,只记"选用了",不复制内容)+ 启用/停用端点;② 一个面向租户的"技能市场"货架页(对标 MCP `CatalogBrowser`)。**订阅是记账/UX 标记,不改运行期解析。**

## 1. 背景:为什么技能 ≠ MCP(不照搬 Stream W)

MCP 必须实例化,因为**实例承载租户私有状态**:`url_template` 用租户参数解析成 URL、bearer token 存 per-tenant secret(`mcp_servers.py:520,574-591`)。没副本无处放 token。

技能是纯内容:`prompt_fragment` + `tool_names` + `required_models`(`skill_version` 表),**零租户私有字段**。运行期 `agent_factory._load_skills` 拿平台 `SkillVersion` 直接渲染,不改写。复制租户副本 = 纯冗余 + 版本漂移。

而且技能**已有 MCP 没有的三件套**(后端几乎不用动):
- **merged view**:`GET /v1/skills` 返 `items`(租户自有) + `platform_items`(平台库,含 `source`/`entitled`/name-shadowing)(`skills.py:1000-1037`)。
- **运行期 fallback**:agent 按 `name@version` ref,resolver 租户优先→平台 fallback,**tier 闸就在热路径**(`runtime.py:332-348`)。agent 无需实例化即可绑平台技能。
- **fork 覆盖**:`fork_skill` 把平台技能 fork 成租户行微调,name-shadowing 自动遮蔽。

⇒ 真正缺的不是实例化,是"市场浏览 UX + 订阅记账"。

## 2. 决策

| # | 决策 |
|---|---|
| M1 | **订阅 = 记账/UX 标记,不影响运行期 fallback**(语义 A)。tier 闸已是真门槛;订阅闸是重复门控且高风险。 |
| M2 | **轻量订阅表** `tenant_skill_subscription(tenant_id, platform_skill_id, enabled, created_at, created_by)`,标准 tenant-scoped RLS(ENABLE+FORCE+严格相等),**不复制技能内容**。 |
| M3 | **启用/停用端点** + merged view 加 `subscribed` 标记。 |
| M4 | **独立"技能市场"货架页**(对标 `CatalogBrowser`),非在 SkillsList 混排;tier 锁标 + 订阅状态按钮。 |
| M5 | **不做实例化副本 / 不加 catalog_id 字段**(技能无私有状态,与 MCP 本质不同)。 |

> 演进留口:M1 选 A 不阻断未来"未订阅不可绑"——届时只需在 `runtime.py:333` 之后接 `is_subscribed`,A 是 B 的真子集。

## 3. 数据模型

新表 `tenant_skill_subscription`(套 `0054_tenant_mcp_server.py` 模板):
- `id UUID PK` / `tenant_id UUID NOT NULL` / `platform_skill_id UUID NOT NULL` / `enabled bool default true` / `created_at` / `created_by`
- `UNIQUE(tenant_id, platform_skill_id)` + `tenant_idx` on tenant_id
- RLS:ENABLE + **FORCE** + 严格相等 policy(`tenant_id = NULLIF(current_setting('app.tenant_id',true),'')::uuid`)。订阅表无跨租户扫描需求,可 FORCE(区别于 skill 表 0057 刻意不 FORCE)。
- **不存** platform_skill 的 FK(平台行是 NULL-tenant,跨 RLS;且订阅是软关联,平台技能归档/删除时订阅行变悬空但无害——merged view 只 join ACTIVE 平台技能)。
- migration `0086_tenant_skill_subscription`(31 字符,≤32 ✓),`down_revision="0085_provider_secret_multikey"`。

store 三件套 `persistence/tenant_skill_subscription/{base,sql,memory}.py`(套 `tenant_mcp_server/`):
- `subscribe(tenant_id, platform_skill_id, created_by)` / `set_enabled(...)` / `unsubscribe(...)` / `list_for_tenant(tenant_id)` / `is_subscribed(...)`(后者留给未来语义 B)。
- protocol record `protocol/tenant_skill_subscription.py`。

## 4. 端点

加在 `skills.py` router(`/v1/skills` prefix):
- `POST /v1/skills/{platform_skill_id}/subscribe` → 订阅(幂等:已订阅则 enabled=true)
- `DELETE /v1/skills/{platform_skill_id}/subscribe` → 取消(或 `enabled=false`,软停)
- 校验:目标必须是 ACTIVE 平台技能(bypass_rls 读校验);幂等。

**RBAC**:`skills.py` 现有惯例是 `ensure_tenant_scope` + 内联角色检查(非 `require()`)。订阅端点**跟随该惯例**(内联 admin/operator 角色),避免同 router 两种风格;不动 rbac.py `Resource` 矩阵。(若后续统一改 `require("skill",...)` 另立。)

## 5. merged view 标记

`skills.py:list_skills`(1000 前,租户 RLS scope 内)读 `subs = sub_store.list_for_tenant(tenant_id)` → `subscribed_ids: set`;1015 后每条 platform item 加 `entry["subscribed"] = p.id in subscribed_ids`。SDK `skills.ts` `SkillRecord` 加 `subscribed?: boolean`。

## 6. 前端

新页 `SkillMarketplace.tsx`(仿 `components/mcp_catalog/CatalogBrowser.tsx`):
- 卡片墙:平台技能(`platform_items`),分类 Tag + `required_tier` Tag + 描述 ellipsis。
- **tier 锁**:`entitled===false` → 置灰 + Lock + "需 {tier} 套餐",订阅按钮 disabled。
- **订阅按钮**:`subscribed` → "已启用"(可停用);未订阅 + entitled → "启用"。调 `subscribeSkill/unsubscribeSkill`。
- SkillsList 保持现状(混排只读展示 + fallback 绑定不变);市场页是**主动选用**入口。

SE-8 接线点:router(`/skill-marketplace`)/ Sidebar(紧邻技能)/ CommandPalette / SDK / i18n(en+zh)/ Storybook / Playwright。

## 7. 分期

1. **Phase 1 — 后端表+store+端点**:migration 0086 + 三件套 + protocol + app.py 注入 + subscribe/unsubscribe 端点 + 单测(sql/memory store + RLS 用例)。不碰运行期。
2. **Phase 2 — merged view subscribed**:list_skills 读订阅集 + 标记 + SDK 字段 + 测。
3. **Phase 3 — 前端市场页**:SkillMarketplace + SE-8 全接线 + stories + e2e。

每 Phase 独立合并:P1 不碰运行期、P3 不碰后端契约,回滚面最小。

## 8. 不做(本轮外)

- 订阅作为运行期准入闸(语义 B)——留口,独立迭代。
- 实例化副本 / catalog_id(M5)。
- 每租户私有技能目录(平台库已够;对照 MCP 也只有平台全局目录)。
- 技能评分/评论/使用量榜(纯 marketplace 增强,后续)。

## 9. 风险

- **订阅悬空行**:平台技能删除后订阅行残留 → merged view 只 join ACTIVE 平台技能,残留无害;可加后台清理(非 M0)。
- **订阅 vs 实际可用不一致**(语义 A 固有):agent 可绑未订阅的平台技能(只要 tier 够)。前端绑定 UI 加"建议先启用"引导(纯提示),运行期不强制。文档明示此取舍。
- RLS:新表标准 tenant-scoped,集成测真 PG 验证 FORCE + policy。

## 10. 确认点(已拍板 2026-06-20)

1. **订阅端点 RBAC = 跟随 skills.py 内联角色惯例**(`ensure_tenant_scope` + 内联 admin/operator 检查),不动 rbac.py `Resource` 矩阵。同 router 单一风格(surgical)。
2. **取消订阅 = `enabled=false` 软停**(非硬删):留审计痕迹,重新启用幂等翻 true,与表的 `enabled` 字段一致。
3. **市场页路径 = `/skill-marketplace`**(租户 scope 独立顶级路径,Sidebar 紧邻"技能")。
