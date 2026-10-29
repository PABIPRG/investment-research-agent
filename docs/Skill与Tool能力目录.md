# Skill 与 Tool 能力目录及聊天接入

更新：2026-10-27。适用产品：`@huohuo/research-agent` 1.0.0 候选；设计基线：V1.4。本轮在 `a439583` 基线上实现聊天业务操作，不代表截图实例版本、数据源在线、真实模型验收或公开发布。后续增删能力必须同时更新本目录、对应注册源和入口说明。

## 1. 使用入口与状态口径

- 用户从 **AI 对话** 提出研究、委托或投资记录需求；DSH 按任务加载 Skill 并选择已注册 Tool。无需用户记工具名。
- **委托查询、持仓与自选、消推配置** 是同一业务状态的页面入口。页面具备写操作，不代表聊天已接入该操作；差异见第 5 节。
- **设置** 的模型凭据由 DSH 原生安全界面维护；不在聊天中索取密钥。
- 开发者从 [开发指引](开发指引.md) 进入注册与验证流程；架构见 [当前架构与装配](当前架构与装配.md)，验收范围见 [交付与验收](交付与验收.md)。

| 标记 | 含义 |
|---|---|
| 已注册 | 名称、schema、执行桥与允许名单已接入；不保证这次调用成功 |
| 授权接入缺口 | 名称存在，但当前独立实例固定拒绝实际执行，不是让用户说一句“授权”即可解除 |
| 依赖实例/来源 | 需要对应数据源、服务、配置及有效证据，逐次以回执为准 |
| 拟接入 | 本文规划，尚无可调用工具；不能在 Skill 中描述为已具备 |
| 已验证 | 必须附对应代码/产物、环境、日期和证据；受控验证与真实使用分别记录 |

Skill 负责方法、澄清和解释；Tool 提供受控查询与业务命令；领域服务强制身份、权限、版本、幂等、持久化与副作用。不能只修改 Skill 来宣称获得写权限，也不通过通用 shell、任意文件或 HTTP 工具绕开领域接口。

## 2. 当前 Skill：聊天 5 个，后台 1 个

| 名称 | 触发场景与入口 | 当前能力与限制 | 正文 |
|---|---|---|---|
| `huohuo-research-chat` | 聊天研究证券、公司、行业、主题、任务或证据 | 对象解析与真实确认、按需研究、单次任务管理；数据源以回执为准 | [研究聊天](../product/skills/chat/research-chat/SKILL.md) |
| `huohuo-mandates` | 明确交代持续研究，或管理已有委托 | 创建、查询、修改、暂停、恢复、结束；联系备注不等于任意条件已编译执行 | [持续委托](../product/skills/chat/mandates/SKILL.md) |
| `huohuo-investment-facts` | 查询或录入持仓、自选、成交和修订 | 读取 → 预览 → 原生确认 → 保存；沪深股票及场内基金，未知成本保留未知 | [投资事实](../product/skills/chat/investment-facts/SKILL.md) |
| `huohuo-notifications` | 查询或调整联系偏好 | 脱敏读取、非密钥设置、清除渠道；密钥仍在安全表单填写 | [通知偏好](../product/skills/chat/notifications/SKILL.md) |
| `huohuo-strategies` | 建立候选、回测、影子验证、进化预案与确认应用 | 同一侧车策略状态；按需运行、仅研究模拟，不代表真实交易或框架修订 | [策略方法](../product/skills/chat/strategies/SKILL.md) |
| `huohuo-bounded-quote` | 后台已接受的固定研究执行 | 根据可信 Scope 执行报价、公司资料或财务摘要；不能自行扩大范围 | [后台研究](../product/skills/bounded-quote/SKILL.md) |

聊天 Skill 从 `product/skills/chat/` 加载，允许名单在 `product/chat/policy.ts`；guard 校验名称与参数，默认 home/cwd 扫描关闭。后台 Skill 由 `product/tools/index.ts` 注册。后台的名称保留了报价历史命名，具体范围以可信 operation 为准。

## 3. 当前 Tool：聊天 107 个，后台另有 1 个

聊天组成：63 个资料研究工具、2 个结构化研究审查工具，其余为任务、实体/委托、投资事实/集合/偏好、持仓风险、个性化、通知、页面、策略、产业链、导入和原生交互。总数由注册源检查，不能当作全部通过真实数据验收的数量。

| 分类 | 名称 | 用途与边界 |
|---|---|---|
| 结构化研究审查（2） | `review_research_decision`、`read_research_reviews` | 九视角研究与多空/风险审查方法接入 DSH；程序绑定当前已确认画像、事实版本、同会话主体证据并校准原建议。保留原始与有效建议和未知，不自动跟踪或交易 |
| 单次研究任务（7） | `submit_quote_research`、`list_research`、`get_research`、`research_events`、`research_evidence`、`cancel_research`、`retry_research` | 提交、读取最近任务/详情/事件/证据、显式取消或重试；queued 不等于完成 |
| 实体与委托（7） | `resolve_research_scope`、`search_securities`、`confirm_research_entities`、`create_mandate`、`list_mandates`、`get_mandate`、`manage_mandate` | 解析、候选搜索、保存真实选择、委托生命周期；确认对象不自动授予持续研究或通知许可 |
| 投资事实/集合（5） | `read_investment_facts`、`preview_investment_change`、`commit_investment_change`、`read_investment_collection`、`bind_mandate_investment_collection` | 同一台账的查询、预览、真实确认保存与集合关联；read_investment_facts(include_account=true)与首页共用账户行情投影，含来源时间/空值/缺口；版本冲突及提交未知不当成功 |
| 风险偏好（3） | `assess_risk_preference`、`parse_risk_preferences`、`preview_risk_adjustment` | 三题／八题、自然语言待核对答案、滑块调整和画像预算；程序计分并确认保存，原始推断与有效画像分别保留 |
| 持仓风险（2） | `preview_position_risk_change`、`read_investment_risk` | 全局／单仓止盈止损、成本冻结、删除覆盖和重新布防；复用投资事实确认和正式委托执行，程序比较价格，不额外调用研究模型 |
| 个性化（5） | `read_personalized_research`、`preview_personalization_change`、`commit_personalization_change`、`refresh_personalized_sources`、`record_personalized_interaction` | 同一实例卡片、策略匹配、本机反馈、开关／清除和偏好复盘；预览确认与回执核对，不修改风险偏好或联系授权 |
| 旧数据迁入（2） | `read_legacy_imports`、`import_legacy_data` | 从设置上传文件后，读取候选/回执/只读档案；生成分类差异并经原生确认后原子导入，不继承旧授权或运行队列 |
| 市场资料（1） | `query_market` | 行情、扫描、日线技术指标、新闻、盘前/盘后资料包；news/brief 可显式 include_slow 扩展全市场来源，逐源报告失败；只读结果留存证据，不自动创建监控 |
| `manage_industry_chain` | 管理实例产业链资料与研报增量 | 状态只读；下载、刷新、删除与增量需原生确认；增量绑定本会话证据 |
| 策略业务（2） | `read_strategy_records`、`manage_strategy` | 保存、回测、影子、预案和确认应用；原生确认、版本及幂等由程序验证 |
| 通知（4） | `read_notification_settings`、`list_notification_deliveries`、`update_notification_preferences`、`clear_notification_channel` | 脱敏查询及原生确认修改；不接收密钥或任意接收目标，不发送测试消息 |
| 页面入口（1） | `open_product_view` | 返回对话、委托、投资、提醒、动态、策略的受控链接，可定位所属委托；设置返回原生菜单路径，当前平台没有公开打开 API |
| 原生交互（2） | `ask_user_question`、`skill` | 问答与加载包内 Skill；Skill 加载不产生业务授权 |
| 后台研究（另计 1） | `read_security_snapshot` | 只读取本次执行绑定的研究范围；不能理解为后台拥有聊天的全部工具 |

业务 Tool 装配见 `product/chat/tools.ts`，实体确认见 `product/chat/entity-tools.ts`，委托见 `product/chat/mandate-tools.ts`，投资事实见 `product/chat/investment-tools.ts`，通知见 `notification-tools.ts`，页面入口见 `navigation-tools.ts`；最终由 `product/chat/guard.ts` 限制可调用范围。

### 63 个研究工具完整目录

下表依据 `product/tools/research-tools.generated.ts` 的当前 schema 整理。该文件保留 Python 契约生成的 67 项（原48项、主分支18项及研报正文1项）；产品装配排除三个旧私有台账入口与旧事件监控设置入口，对话实际暴露63项资料研究工具。结构化研究审查另走正式研究台账入口，不手工修改生成文件。更细参数、实体类型、来源和处理器见第6节注册源。

<!-- research-catalog:start -->
| Tool | 注册用途与限制 | 当前执行边界 |
|---|---|---|
| `announcement_search` | 公告检索：按公司代码/名称在最近 N 天公告列表中检索；不抓取公告正文。 | 已注册；依赖实例/来源 |
| `benchmark_lookup` | 基准映射：按证券板块给出主基准、兜底基准及指数代码。 | 已注册；依赖实例/来源 |
| `benchmark_performance_lookup` | 基准表现：基准指数历史行情与区间表现，数据来自新浪/中证指数。 | 已注册；依赖实例/来源 |
| `bond_terms_lookup` | 转债条款：可转债基本条款与发行信息。 | 已注册；依赖实例/来源 |
| `capital_flow_lookup` | 资金流向：同花顺即时资金流快照（流入/流出/净额）。 | 已注册；依赖实例/来源 |
| `commodity_price_lookup` | 商品价格：商品主力连续合约价格序列。 | 已注册；依赖实例/来源 |
| `company_governance_lookup` | 公司治理：法人代表、注册资本、成立/上市日期与机构简介；不含完整董监高名单。 | 已注册；依赖实例/来源 |
| `company_profile` | 公司资料：巨潮公司档案：法定名称、行业、法人代表、经营范围与简介。 | 已注册；依赖实例/来源 |
| `company_relationship_lookup` | 公司关系查询：本地实体关系为基础，产业链服务在线时补充上下游与关联关系。 | 已注册；依赖实例/来源 |
| `convertible_bond_lookup` | 可转债查询：可转债主数据检索（代码/简称）。 | 已注册；依赖实例/来源 |
| `dividend_history_lookup` | 分红送配：按报告期披露的分红送配历史（送转、现金分红、除权除息日）。 | 已注册；依赖实例/来源 |
| `dragon_tiger_lookup` | 龙虎榜：近期龙虎榜上榜记录与买卖额。 | 已注册；依赖实例/来源 |
| `event_timeline_lookup` | 事件时间线：优先盯盘服务事件流，服务不可用时回退个股新闻。 | 已注册；依赖实例/来源 |
| `financials_lookup` | 财务数据：A 股财务摘要指标，按报告期返回最近若干期。 | 已注册；依赖实例/来源 |
| `fund_holdings_lookup` | 基金持仓：基金季度持仓；当年为空时回退上一年。 | 已注册；依赖实例/来源 |
| `fund_lookup` | 基金查询：全市场基金名录检索（代码/简称）。 | 已注册；依赖实例/来源 |
| `fund_performance_lookup` | 基金表现：已核实交易所的 ETF 用新浪历史价格，其他基金用单位净值走势；市场未知不猜测。 | 已注册；依赖实例/来源 |
| `index_constituents_lookup` | 指数成分：指数成分股，新浪失败时回退中证指数。 | 已注册；依赖实例/来源 |
| `index_lookup` | 指数查询：指数实时快照与实体信息。 | 已注册；依赖实例/来源 |
| `index_performance_lookup` | 指数表现：指数历史行情与区间表现。 | 已注册；依赖实例/来源 |
| `industry_chain_lookup` | 产业链查询：产业链多层链路；服务不可用时回退实体库直接关系并明确告警。 | 已注册；依赖实例/来源 |
| `industry_lookup` | 行业查询：标准行业名称、别名与归属；可选返回本地名称表中的成员公司。 | 已注册；依赖实例/来源 |
| `industry_performance_lookup` | 行业表现：同花顺行业/概念板块行情；分类口径与本地行业不同，需复核。 | 已注册；依赖实例/来源 |
| `institution_survey_lookup` | 机构调研：近 N 天机构调研记录（接待日期、机构数量、接待方式与人员）。 | 已注册；依赖实例/来源 |
| `inventory_lookup` | 库存数据：期货品种库存序列。 | 已注册；依赖实例/来源 |
| `macro_event_search` | 宏观事件检索：基于新闻关键词检索宏观事件，不是结构化事件库。 | 已注册；依赖实例/来源 |
| `macro_series_lookup` | 宏观序列：CPI/PPI/PMI/GDP/M2/社融/LPR/SHIBOR 等宏观序列。 | 已注册；依赖实例/来源 |
| `margin_balance_lookup` | 融资余额：沪深两融明细，按最近交易日回溯查询。 | 已注册；依赖实例/来源 |
| `official_document_search` | 官方文件检索：中国政府网政策文件库检索（国务院/部门文件），返回标题、文号、发布机构与原文链接。 | 已注册；依赖实例/来源 |
| `peer_group_builder` | 可比公司构建：按本地行业归属与市值构建可比组，未做业务相似度核验。 | 已注册；依赖实例/来源 |
| `policy_search` | 政策检索：基于新闻关键词检索政策报道，不等同于官方文件库。 | 已注册；依赖实例/来源 |
| `quote_history` | 历史行情：A 股前复权日线行情；新浪不可用时回退东方财富。 | 已注册；依赖实例/来源 |
| `regional_policy_search` | 区域政策检索：基于新闻关键词检索区域政策报道。 | 已注册；依赖实例/来源 |
| `restricted_release_lookup` | 限售解禁：查询个股在给定窗口内的限售解禁记录；计划可能随公告调整。 | 已注册；依赖实例/来源 |
| `security_lookup` | 证券名称/代码查询：本地实体库精确查询证券；返回实体状态，未核验数据会显式标注。 | 已注册；依赖实例/来源 |
| `shareholder_count_lookup` | 股东户数：历史股东户数与环比变化，用于观察筹码集中度；户数受股本变动影响。 | 已注册；依赖实例/来源 |
| `strategy_attribution_lookup` | 策略影子归因：影子组合整体收益/回撤与每策略贡献；数据不足时显式说明，不做外推。 | 已注册；依赖实例/来源 |
| `strategy_evolution_preview` | 策略进化预案查询：只读当前待确认的升级/降级/淘汰/变异预案；应用预案必须由用户确认。 | 已注册；依赖实例/来源 |
| `strategy_pool_lookup` | 策略池状态查询：策略池阶段、影子数据天数与每策略判定；服务未启动时返回 unavailable。 | 已注册；依赖实例/来源 |
| `style_constituents_lookup` | 风格成分：返回风格代理指数的成分股，并披露代理关系。 | 已注册；依赖实例/来源 |
| `style_performance_lookup` | 风格表现：用有明确口径的指数代理风格表现，并披露代理关系。 | 已注册；依赖实例/来源 |
| `supply_demand_lookup` | 供需数据：已核查库存、价格与新闻接口，均无可复现的供需平衡表；不得用库存/价格冒充供需。 | 已注册；缺可复现供需来源 |
| `theme_constituents_lookup` | 主题成分：按主题名称匹配同花顺概念板块，抓取涨幅排序的前若干页成分股；不是完整成分列表。 | 已注册；依赖实例/来源 |
| `theme_lookup` | 主题/赛道查询：本地主题词典，提供标准名、别名与本地关系；不含成分股。 | 已注册；依赖实例/来源 |
<!-- research-catalog:end -->

必须区分这些边界：

- `portfolio_lookup`、`portfolio_risk_analysis`、`watchlist_lookup` 已从聊天装配撤下；旧注册源为兼容保留，不再让用户进入无法完成的授权流程。当前投资查询、预览与保存统一使用投资事实工具；旧成本集中度由同一事实返回的 `cost_analysis` 计算，未知成本时不归一化为完整账户权重。`event_monitor_setup` 撤下，能力统一由 create_mandate / manage_mandate 的可执行联系规则替代；条件、每日研究交付、定时检查和直接提醒使用同一正式委托、版本及通知资格。
- `supply_demand_lookup` 没有可复现的供需平衡表来源，不用库存或价格冒充供需数据。
- 策略三项查询已直接复用本实例侧车策略领域；不依赖旧服务地址。部分产业链、公司关系、结构化事件能力仍缺服务/关系数据，缺失不能称为完成；不自行连接旧实例补救。
- 研究工具保存会话证据，不自动创建持续委托。ETF 台账已单独接通；研究来源成功与台账保存分别验收。

### 3.5 主分支追加研究数据能力（2026-10-28）

以下随 main 的数据覆盖修复整合。注册不保证来源在线；对象型查询继续要求本会话实体确认。

| Tool | 用途 | 状态与边界 |
|---|---|---|
| `announcement_document_lookup` | 公告正文链接：巨潮公告清单与原文链接，可按日期和关键词过滤；不解析 PDF 正文。 | 已注册；依赖实例/来源 |
| `bond_yield_curve_lookup` | 债券收益率曲线：国债、国开债与中短期票据收益率，按曲线名称与期限返回；引用必须写明曲线。 | 已注册；依赖实例/来源 |
| `etf_ranking_lookup` | ETF 排行：场内 ETF 实时行情排行，可按涨幅、跌幅、成交额与成交量排序或按名称过滤。 | 已注册；依赖实例/来源 |
| `forex_rate_lookup` | 人民币汇率：外汇即期快照，可按名称过滤；不是银行牌价或远期汇率。 | 已注册；依赖实例/来源 |
| `hot_stock_rank_lookup` | 个股人气榜：东方财富人气榜/飙升榜，反映股吧关注度，不代表资金或基本面。 | 已注册；依赖实例/来源 |
| `ipo_detail_lookup` | IPO 发行信息：发行日期、发行价、发行市盈率、募资净额与主承销商。 | 已注册；依赖实例/来源 |
| `limit_pool_lookup` | 涨停板股池：涨停、跌停、强势与炸板股池，含连板数、封板资金与所属行业；自动回溯最近交易日。 | 已注册；依赖实例/来源 |
| `market_news_lookup` | 市场快讯：东方财富全球财经快讯与财联社电报，可按关键词过滤；快讯是未核实线索。 | 已注册；依赖实例/来源 |
| `market_overview_lookup` | 市场概览：主要宽基指数快照与全市场涨跌家数、涨停跌停等情绪指标；部分来源失败时明确告警。 | 已注册；依赖实例/来源 |
| `market_valuation_lookup` | 市场估值：全 A 或主要宽基指数的市盈率水平与历史分位，用于判断整体估值位置。 | 已注册；依赖实例/来源 |
| `minute_bar_lookup` | 分钟线：A 股 1/5/15/30/60 分钟线，覆盖最近几个交易日，未复权。 | 已注册；依赖实例/来源 |
| `overseas_quote_lookup` | 港美股行情：港股与美股历史日线与区间摘要，当地货币计价，不可与 A 股直接比较。 | 已注册；依赖实例/来源 |
| `performance_forecast_lookup` | 业绩预告：按报告期列示 A 股业绩预告，含预告类型、变动幅度与原因；可按类型排序或按名称检索。 | 已注册；依赖实例/来源 |
| `performance_express_lookup` | 业绩快报：按报告期列示营收、净利润与同比，可按名称或行业检索；是初步核算数。 | 已注册；依赖实例/来源 |
| `research_report_document_lookup` | 研报正文读取：从已确认公司的列表选定报告，每次读取1至5页，保留正文页码、校验和与截断；不接受任意URL，扫描件保持不可用。 | 已注册；依赖公开来源 |
| `research_report_lookup` | 研报与一致预期：个股卖方研报清单、评级、机构与年度盈利预测；评级是卖方观点。 | 已注册；依赖实例/来源 |
| `sector_fund_flow_lookup` | 板块资金流排行：行业/概念/地域板块主力净流入排行，支持今日、5日、10日周期。 | 已注册；依赖实例/来源 |
| `sector_ranking_lookup` | 板块排行：同花顺行业与概念板块当日涨幅、净流入、上涨家数与成交额排行，可按涨幅、跌幅等排序；不绑定具体板块实体。 | 已注册；依赖实例/来源 |
| `stock_valuation_lookup` | 个股估值：单只 A 股的市值、市盈率、市净率、市现率时间序列与所选区间分位。 | 已注册；依赖实例/来源 |

## 4. 恒科 ETF 持仓：原因及当前实现

截图对应旧实现确实只有聊天读取，投资校验还只接受沪深 A 股。仅在页面填写也无法解决 ETF 身份问题。新实现复用原来的投资领域服务，没有建立聊天专用台账：

1. 明确具体 ETF；“恒科 ETF”有歧义时先查候选、补问代码，不能默选。修复 `fund_lookup` 仅名称搜索时错误返回全部基金的问题。
2. 补齐用户提供的数量、日期及已知成本；调用 `preview_investment_change` 生成主体与事实版本绑定的预览。
3. `commit_investment_change` 从后台读取预览真实内容，在原生确认卡呈现影响；模型不能自填 `confirmed=true`。取消不提交。
4. 用户确认后保存，返回回执及版本；重复确认同一预览复用回执，版本冲突要求重新核对，提交未知先对账。
5. ETF 使用基金身份和“份”，兼容既有目录身份；历史快照、集合和事件同时使用该身份。代码格式合法不等于已核验交易所主数据。股票仍用“股”。

可直接表达：“记录 513130 的期初持仓 1000 份，成本未知，确认日期是……”。记录实际成交需明确是否更新持仓；校正不伪造买卖历史。保存后可在持仓与自选页刷新核对。

## 5. 页面操作到聊天能力的映射

**所有页面业务操作都必须评估聊天入口。** Tool 按业务命令设计，Skill 按任务流程组织，不为每个按钮复制一份 Skill。下表区分本轮已接通业务能力与原生界面保留项；业务仍只有一份权威状态。

范围是当前 `product/ui` 的四入口、产品导航以及继承的 DSH 设置/会话入口；DSH 设置内部全部选项尚未逐项验收，不能据此声称已覆盖原生平台每个按钮。纯展示行为也列出处理方式，避免被误认为遗漏。

| 用户动作 / 页面入口 | 现有接口与状态所有者 | 聊天现状 / 缺口 | 当前接入方式 | 确认、影响及验收重点 |
|---|---|---|---|---|
| 查询、刷新、筛选单次研究，查看结果/事件/证据/来源 | `client.tsx`；`/executions`；执行与证据领域 | 已有 list/get/events/evidence 工具 | 复用；由研究 Skill 编排，筛选作用于真实读取结果 | 最近 50 条边界；不声称筛选覆盖全部历史；来源链接只作资料 |
| 提交、取消、重试单次研究 | 执行服务；页面主要查询，聊天发起命令 | 已有 submit/cancel/retry 工具 | 复用 | 取消与重试显式意图、当前 revision、连接中断先对账 |
| 解析和确认对象、创建委托 | 实体确认服务、`/mandates` | 已接入 | 复用研究与委托 Skill | 真实用户确认回执；多对象逐项保留；不默选第一项 |
| 查询/刷新/筛选委托，展开范围、基准、决定、来源版本和证据 | `Mandates.tsx`；`/mandates`、`/mandates/{id}` | 已有 list/get | 复用 | 失败与空数据不同；内容版本不是发布时间；返回资料可解释 |
| 修改研究目标、备注；暂停、恢复、结束委托 | 同一委托命令服务 | `manage_mandate` 已覆盖基本操作 | 复用 | 当前 revision/generation；结束不可恢复、暂停撤销资格；在途通知无法撤回 |
| 修改每日提醒开关/时间、本委托允许联系渠道 | `Mandates.tsx` 提交 `reminder_time`、`contact_channels` | 已扩展 `manage_mandate.definition`，原生确认 | 复用既有委托 Tool 与 Skill，不另建第二份约定 | 明确时区/每日语义；渠道配置与本委托授权分开；版本更新和发送资格 |
| 查看持仓/自选/成交、刷新/搜索，展开校正与修订历史 | `Investment.tsx`；`GET /investment` | `read_investment_facts` 已接入 | 复用投资事实 Skill；大数据量需要时再扩展领域查询 | 读取失败不当空仓；搜索无结果不当未录入；引用事实版本 |
| 录入期初持仓、校正数量/成本/确认时间、清仓校正 | `preview(command=holding)` → `commit`；投资事实领域 | 已接通股票与场内基金 | `preview_investment_change` / `commit_investment_change`；投资事实 Skill | 先解释影响；数量 0 的清仓含义、未知成本、原因与时间；不联动结束委托 |
| 添加/移除自选、记录关注原因 | `preview(command=watchlist)` → `commit` | 已接通预览与原生确认保存 | 复用同一投资变更工具 | 关注不等于持仓、订阅或委托；不由模型推断兴趣替用户添加 |
| 录入实际买入/卖出、数量/价格/费用/发生时间，选择只补记录或更新持仓 | `preview(command=trade)` → `commit` | 已接通预览与原生确认保存 | 复用同一投资变更工具 | 计划不记成交；防重复入账；不明持仓影响时必须补问 |
| 更正/撤销成交，查看修订前后 | `preview(command=revision)` → `commit` | 已接通预览与原生确认保存 | 复用同一投资变更工具 | 保留原记录和审计；核对余额、时间顺序与版本；不当成新增成交 |
| 预览、返回修改、取消编辑、确认保存 | 页面草稿 + 领域预览记录 | 已接通预览确认闭环 | 组合补齐后的 Tool 与原生问答；取消草稿不调用 commit | 预览绑定主体/版本/内容；修改失效旧预览；真实确认不能由模型自填；提交未知先核对 |
| 预览持仓/自选集合，选择固定/动态模式，确认关联委托，查看执行快照 | `InvestmentContext.tsx`；`/investment/collection`、`snapshot`、`bind-collection` | 已接通 | `read_investment_collection`、`bind_mandate_investment_collection`；编排归委托与投资事实 Skill | 绑定产生新委托版本；不恢复暂停委托；当前仅补充上下文，不自动变为多证券研究 |
| 读取/刷新消推配置、渠道可用状态和投递记录 | `Notifications.tsx`；`/notifications/config`、`/notifications` | 已接通 | `read_notification_settings`、`list_notification_deliveries`；通知 Skill | 只返回脱敏配置；accepted/delivered/unknown 的语义与页面一致 |
| 启停提醒、选择渠道、设置或关闭每日静默时段 | 同一通知配置服务 | 已接通 | `update_notification_preferences` 与通知 Skill | 只修改已声明非密钥字段；版本校验；跨午夜/全天静默；不得扩展委托授权或自动发测试消息 |
| 填写/修改/清除企业微信、Server 酱、邮件凭据与目标 | 安全配置表单 → 通知领域 | 填写/修改保留安全表单，清除已接通 | 聊天链接到消推配置；完成后脱敏读取核对，`clear_notification_channel` 原生确认清除 | 密钥不进入聊天/Tool 输出；清除、接收目标变更须明确确认；不开放任意主机/凭据工具 |
| 从投递记录回访委托和证据 | 页面 `visit` + 委托详情 | 已可查委托并生成页面链接 | 现有 get 工具与 `open_product_view` | 校验所属主体与真实 ID；不将回访当作新委托 |
| 回到对话、切换业务页、定位记录 | `Shell.tsx` / DSH layout；无新业务状态 | 已注册页面入口 | `open_product_view`，仅枚举本产品页面及所属记录 | 导航不保存业务、不授权；不开放任意 URL 或 JS；UI 不可用时返回明确入口 |
| 新建/打开历史对话、侧栏展开/收起、重连 | DSH 会话/布局/连接服务 | 页面调用原生服务 | 复用 DSH；聊天需要导航时再接受控适配，不复制会话存储 | 不清除会话、不冒充后台业务取消；权限与连接错误保留 |
| 模型配置、其他原生设置、复制/分享/导出等原生会话动作 | DSH 原生界面；具体装配与 API 待逐项确认 | 未验证完整能力矩阵 | 先审计原生能力；方法可归 Skill，能调用且有明确需求再适配 Tool | 模型密钥留在安全表单；分享/导出明确范围与用户授权；不将未核实按钮写成已支持 |
| 页签、搜索清除、展开/折叠、返回列表、滚动定位、取消未保存编辑 | 页面局部状态 | 不需要持久业务 Tool | 复用 UI；聊天以查询、结果分组和取消待提交草稿承接 | 不为纯视觉状态增加业务服务；取消草稿不撤销已保存事实 |

### 实施顺序与证据要求

1. **优先补投资事实闭环与 ETF 身份。** 复用预览/提交/版本/审计，补受控聊天确认；先复现不支持，再验证页面与聊天读到同一事实。接入不能新增独立聊天台账。
2. **补齐委托页与聊天参数等价。** 每日提醒、渠道授权、投资集合关联分别验证，不把提醒备注当作可执行规则。
3. **补通知读取和非密钥设置。** 导航到安全凭据表单；关闭、清除、换目标保持可追溯和发送前复核。真实外发需另获具体授权。
4. **补受控导航并审计 DSH 原生操作。** 先复用原生服务，不实现第二套会话或设置系统；不可用项写明原因和可达入口。

本轮已实现上述投资事实、集合、委托参数、通知及业务页入口，复用原数据库结构。DSH 原生设置缺少公开打开 API，工具返回“设置 → 模型”的准确路径；复制/分享/导出等原生会话动作仍使用原界面。它们未被宣称为聊天可自动执行。

| 状态 | 聊天与页面必须一致的行为 |
|---|---|
| 加载/刷新 | 明确在读取；旧数据标明版本/可能过期，不能作为新保存回执 |
| 未录入/空数据/筛选无结果 | 三者分别表达；不补造零值和空仓 |
| 部分成功/过期 | 逐项说明已保存与待处理内容，不将整组标成功 |
| 错误/无权限/禁用 | 不静默降级为成功；保持草稿并说明可执行的恢复入口 |
| 版本冲突/取消 | 读取最新状态，旧预览失效；取消未确认变更不产生业务副作用 |
| 提交结果未知 | 使用同一幂等身份核对回执，不换请求重复写入或重发通知 |
| 成功/确认/修订 | 保存回执、版本、前后变化可查；刷新/重开后仍存在；修订不抹掉原记录 |

体验契约：用户在对话中表达任务，必要信息只问一次，看到真实影响和保存回执，在业务页可核对同一状态。本轮真实浏览器受控验收及尚未覆盖项见第 7 节。

## 6. 注册文件与维护入口

沿用下列注册源，不新建一份独立且可能漂移的运行时总注册表。本文件是面向用户和开发者的索引，不代替可执行契约。

| 变更类型 | 必须维护的事实源 / 装配点 | 必须同步的入口与证据 |
|---|---|---|
| 新增/调整研究 Tool | `sidecar/huohuo/research_entities/registry/tools.py` 能力定义；`tool_contracts.py` 参数；`toolbox/registry.py` 处理器映射与对应 handler；按需核对实体类型/范围和授权 | 运行 `npm run tools:generate` 更新 `product/tools/research-tools.generated.ts`，用 `npm run tools:check` 查漂移；工具 schema、失败语义和真实来源覆盖另测 |
| 新增/调整聊天业务 Tool | `product/chat/*-tools.ts` 的名称/schema/执行器；`product/chat/tools.ts` 的创建与允许名单组合；`product/chat/guard.ts` 消费名单；对应 sidecar 命令 | 核对参数、可信会话、幂等和确认；适用 Skill、第 3/5 节、页面等价行为与回归 |
| 新增/调整聊天 Skill | `product/skills/chat/<任务>/SKILL.md` 的名称/描述/正文；`product/chat/policy.ts` 的名称名单 | 原生目录可发现、loader 真正加载、外部 Skill 被拒；第 2 节与用户触发示例；无需为按钮机械拆 Skill |
| 后台能力 | `product/tools/index.ts`、后台 Skill、`product/bundle/cordis.patch.yml`，以及 `runtime`/`distribution` 对执行工具的限制 | 检查可信 Scope、attempt/租约、证据准入与迟到结果；不自动继承聊天写权限 |
| 新增页面操作或聊天导航 | `product/ui` 对应组件、bridge、`host.ts`，及 DSH 原生服务适配 | 第 5 节必须登记：已有/缺口/决策/权限/验收；用户能从 README 找到入口与限制 |
| Profile/Bundle 装配变化 | `product/bundle/chat.patch.yml`、`cordis.patch.yml`、`distribution/chat.ts` 等实际装配源 | 新安装及已有 Profile 升级的发现/加载/guard；不得仅改文件未验证装配 |
| 目录与文档新增 | 本文、README、`docs/阅读入口.md`、`docs/开发指引.md` | `package.json.files`、`scripts/export-handoff.mjs` 导出白名单；发布校验的 required 清单，防止源码可读但安装包缺文档 |

### 每次新增、修改或删除能力的完成清单

1. 先查现有接口与相似 Tool；登记使用者、入口、读写类型、权威状态、必要权限与可用性。删除/改名同时考虑旧会话、Profile 和兼容期。
2. 在对应注册源完成名称/schema/执行器/允许名单/Skill 路由；研究工具生成产物不得手改。记录新增工具是否仅声明、已接通或受限。
3. 更新本目录中的名称、数量、来源限制、页面操作映射；README 保留稳定入口，新增重要使用路径同步开发说明。拟议名称不能计入已注册数量。
4. 运行 `npm run capabilities:check` 及与变化匹配的工具契约检查、聚焦测试及必要类型/构建；涉及发现/装配再做原生 Skill/Tool 回放。页面和聊天同一操作验证同一持久结果、取消、冲突与结果未知分支。
5. 核对文档链接和源码/发行收录。文档改动不重复完整模型/UAT；新增用户行为须真实入口验收，不用工具数量或文档代替完成证据。
6. 更新对应 Linear 事项的证据链须遵守授权；代码、自动化、受控 UAT、真实资料、真实通知、发布分别标记。没有证据则明确“未验证”。

本目录关联已有事项：[PAB-43 研究工具注册与清单](https://linear.app/pabiprg/issue/PAB-43)、[PAB-52 投资事实](https://linear.app/pabiprg/issue/PAB-52)、[PAB-54 事实快照与委托范围](https://linear.app/pabiprg/issue/PAB-54)、[PAB-51 消推配置与回访](https://linear.app/pabiprg/issue/PAB-51)。关联表示追溯，不宣称这些事项已完成；本轮不创建新 issue，也不修改其状态。

## 7. 本轮实现与验证

2026-10-26，独立分支 `codex/capability-catalog`，本地源码候选。实施与兼容说明见 [聊天业务操作实施计划](聊天业务操作实施计划.md)；具体证据见 [聊天业务操作验收](聊天业务操作验收.md)。

已完成聚焦的投资台账/ETF/名称查找/通知/委托后端测试，聊天确认/取消/版本冲突/提交未知/脱敏参数测试，以及 TypeScript 检查和客户端构建。受控浏览器通过真实 DSH loader、工具、原生问答与领域服务，验证 ETF 保存后刷新可见、取消不入账、通知偏好与页面一致、固定持仓集合关联和每日 09:00 应用内提醒。

受控模型与合成资料仅证明装配和业务闭环；真实模型理解任意自然语言、实时 ETF 来源、真实外发及安装升级未在本轮验收。原生设置直接调用的尝试因平台未公开 API 撤回，保留明确菜单入口。未提交、推送、合并或发布，不代表截图中的已运行实例已升级。

逐项迁移核对见 [V1.4 旧版 48 项研究工具迁移核对](设计基线/V1.4-旧版48项研究工具迁移核对.md)。


### 成交证券名称与历史展示补全

成交名称由页面已选对象或聊天中明确的名称进入 `preview_investment_change`，在服务端预览与原生确认后随持仓、成交保存。外层投资事实适配名称元数据，原资金计算、成交请求指纹和数值快照不增加名称字段。旧代码录入保持兼容，不能用同一成交编号修改名称。

`read_investment_facts` 与页面共享 `display_name`／`name_source` 投影。已记录名称优先；旧缺名股票可由现有 `security-search` 精确查询暖目录缓存，随后重新读取同一事实视图。目录信息只补展示，不写事实、快照、审计、outbox，不增加事实版本。过期、其他代码、占位文字和纯代码不能成为有效名称；目录不可用时保留待补充。名称读取不等待目录联网锁。查询只发送公开证券代码，不发送持仓数量、成本或账户数据。

### 账户行情读模型（2026-10-29）

首页账户与read_investment_facts(include_account=true)复用Investment只读账户投影、MarketData现有来源及缓存；不新增Tool、账户状态或独立调度器。固定GET /investment/account由DSH已认证桥转发；只向来源发送本地持仓/当日成交涉及的公开证券代码，不发送数量、成本、主体或交易明细。账户显式investment行情范围支持instrument识别的沪深股票与场内基金；默认研究市场查询仍为A股。最多20只，缺失/未知单位/时间/报价不会作为0参与合计。空本地记录显示0并注明尚未录入；不是券商空仓确认。旧报价金额带时间标为参考；日盈亏核对昨收、当日成交/费用及数量更正，无法对齐时保留未知；未录入分红税费不在口径内。

### 确定性价格提醒（2026-10-29）

`create_mandate` / `revise_mandate` 仍是聊天接入，页面和聊天共用正式联系规则及同一委托状态。market_quote 范围中已确认的纯价格数值条件（以及只含它们的 all/any）由程序在原 research_jobs → execution/attempt → evidence → contact_decisions → notification 链执行，不额外调用模型；语义条件、其他指标和研究仍使用既有 DSH Skill。价格和时间可核验而量比/换手率缺失时，价格可判断，其他指标保持未知。过期、错误身份、错误单位、撤销代次和失效租约不获得发送资格。

`/worker/attempts/:id/price-run` 是有 worker 身份和 attempt 能力约束的内部执行入口，不是新增聊天Tool，也不接受客户端自定规则/对象。状态投影提供 execution_mode 和 requires_comparison_baseline；纯价格委托不要求比较基准。结果解析兼容整段单个JSON代码块，仍经过正式结构、执行和证据校验，不自动重试或重放历史失败。


### 实体提及归并（2026-10-29）

`resolve_research_scope` 继续持有解析入口，侧车按相同的已解析标准实体 ID 生成 `discussion_subjects`，原始 `mentions` 保留。`confirm_research_entities` 按讨论对象提问、保存单份回执；Scope 同步去重。同名、同代码或候选重叠不能直接合并；公司与证券仍是有关联的不同实体，不扩大回执 operations。新快照使用 `discussion_subjects_v1`，旧快照继续兼容原提及协议，不改写历史回执。无新增 Tool/Skill。
