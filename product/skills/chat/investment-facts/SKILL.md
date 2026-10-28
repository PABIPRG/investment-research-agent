---
name: huohuo-investment-facts
description: 用户要求查看、录入、校正持仓或 ETF，添加移除自选，记录、更正或撤销已成交操作，或关联投资集合时使用。聊天与页面共享预览、确认和正式事实。
---

# 投资事实与用户记录

先调用 read_investment_facts，区分未录入、已确认空仓与读取失败。已有记录的代码、成交编号、版本来自实际回执，不从记忆补造。建议、计划、模拟与已发生成交不同。

## 从聊天录入

1. 确认用户要记录哪只证券；名称有歧义时先检索候选。股票可用 search_securities，基金用 fund_lookup；“恒科 ETF”应按恒生科技 ETF 检索并列出具体代码和名称，请用户选择，不能默选首项。目录失败不能说不存在；可让用户提供明确代码。当前台账支持沪深 A 股和场内基金，基金研究目录存在不代表后台委托支持 ETF。
2. 补齐当前操作必要信息。期初持仓问数量、已知成本和确认时间/原因；未知成本填 null。用户明确说“目前持有”时可依据工具/可信当前时间记录确认时点，不能伪造买入时间。已有记录可复用，但须说明变化。不要把现有持仓录成一次买入。
3. 调用 preview_investment_change。holding 必填 ticker/name/quantity/cost_price/effective_at/reason；watchlist 必填 ticker/name/reason/remove；trade 必填 ticker/side/quantity/price/traded_at/affects_holdings，并传递用户选择或明确提供的证券 name，fees 可为已明确的费用；revision 必填 trade_request_id/operation/affects_holdings，可带修改字段和原因。不要因旧请求兼容代码录入而删除已取得的证券名称；目录结果冲突时先澄清。request_id/revision_id 由程序生成，不填写。
4. 展示预览影响后调用 commit_investment_change，工具直接从后端读取预览并呈现原生确认。用户跳过、取消、关闭、超时和自由文字不构成确认；按补充内容重新预览，不能说已保存。
5. 只以 saved 回执和事实版本说明完成；结果未知时用同一 preview_id 核对回执，不能创建另一份预览盲目重复成交。409 冲突先读取最新事实重新预览。需要页面核对可用 open_product_view 的 investment 链接。

持仓校正数量 0 表示清仓校正；移除自选不清仓、不结束委托。真实成交须明确“只补记录”还是“同时更新持仓”，防止重复计入。更正与撤销保留原记录，不作为新增成交；跨期初快照或负余额失败时先核对，不伪造历史。股票数量用股、基金用份，未知成本不显示为零。

读取时名称优先使用 `display_name`，并保留 `name_source`。旧记录的目录补充名称只用于展示，不修改原事实、数量、成本、版本或旧成交；不能说成当时已记录名称。缺名时可复用 `search_securities` 精确查询股票代码，再读取事实；目录不可用不猜测名称，不通过重复录入成交补名。

## 集合与委托

read_investment_collection 可读取当前或指定事实版本。用户明确要求关联既有委托时，先读 get_mandate 和集合，确认固定快照还是动态集合，再调用 bind_mandate_investment_collection；工具展示真实成员并取得确认。关联只提供研究上下文，不自动展开多证券研究、不恢复暂停委托。读取持仓、自选变化和用户选中证券都不自动授权持续研究或外发。

## 成本集中度

`read_investment_facts` 返回程序计算的 `cost_analysis`，承接原持仓风险分析的单位成本乘数量、成本权重和最大单仓权重。它不是实时市值、当日盈亏或风险预测；部分成本未知时完整权重和总成本保持未知，不把已知部分归一化成完整组合。优先解释名称、权重及具体缺口，不向用户输出内部字段。旧 portfolio/watchlist 授权工具不再暴露，统一使用此读模型。

## 迁入旧产品记录

文件由用户在「设置 → 旧数据导入」上传；不能索取本机路径、密钥或任意 URL。用 `read_legacy_imports` 的 uploads 读取当前用户候选，按明确分类调用 `import_legacy_data`。该工具生成差异并等待原生确认；文字回答不能代替确认。默认保留当前冲突值；用户明确要求时才选择 use_import。

未知提交先读取同一 preview_id 的 status，禁止更换标识重试。旧成交只补历史记录，不再加到当前持仓；未知成本和费用保持未知。旧策略重新待验证、委托暂停、研究与对话成为只读档案，不能说成已恢复旧运行、通知许可或可续聊 DSH 历史。
