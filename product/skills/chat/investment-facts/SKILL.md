---
name: huohuo-investment-facts
description: 用户要求查看、录入、校正持仓或 ETF，添加移除自选，记录、更正或撤销已成交操作，或关联投资集合时使用。聊天与页面共享预览、确认和正式事实。
---

# 投资事实与用户记录

先调用 read_investment_facts，区分未录入、已确认空仓与读取失败。已有记录的代码、成交编号、版本来自实际回执，不从记忆补造。建议、计划、模拟与已发生成交不同。

## 从聊天录入

1. 确认用户要记录哪只证券；名称有歧义时先检索候选。股票可用 search_securities，基金用 fund_lookup；“恒科 ETF”应按恒生科技 ETF 检索并列出具体代码和名称，请用户选择，不能默选首项。目录失败不能说不存在；可让用户提供明确代码。当前台账支持沪深 A 股和场内基金，基金研究目录存在不代表后台委托支持 ETF。
2. 补齐当前操作必要信息。期初持仓问数量、已知成本和确认时间/原因；未知成本填 null。用户明确说“目前持有”时可依据工具/可信当前时间记录确认时点，不能伪造买入时间。已有记录可复用，但须说明变化。不要把现有持仓录成一次买入。
3. 调用 preview_investment_change。holding 必填 ticker/name/quantity/cost_price/effective_at/reason；watchlist 必填 ticker/name/reason/remove；trade 必填 ticker/side/quantity/price/traded_at/affects_holdings，fees 可为已明确的费用；revision 必填 trade_request_id/operation/affects_holdings，可带修改字段和原因。request_id/revision_id 由程序生成，不填写。
4. 展示预览影响后调用 commit_investment_change，工具直接从后端读取预览并呈现原生确认。用户跳过、取消、关闭、超时和自由文字不构成确认；按补充内容重新预览，不能说已保存。
5. 只以 saved 回执和事实版本说明完成；结果未知时用同一 preview_id 核对回执，不能创建另一份预览盲目重复成交。409 冲突先读取最新事实重新预览。需要页面核对可用 open_product_view 的 investment 链接。

持仓校正数量 0 表示清仓校正；移除自选不清仓、不结束委托。真实成交须明确“只补记录”还是“同时更新持仓”，防止重复计入。更正与撤销保留原记录，不作为新增成交；跨期初快照或负余额失败时先核对，不伪造历史。股票数量用股、基金用份，未知成本不显示为零。

## 集合与委托

read_investment_collection 可读取当前或指定事实版本。用户明确要求关联既有委托时，先读 get_mandate 和集合，确认固定快照还是动态集合，再调用 bind_mandate_investment_collection；工具展示真实成员并取得确认。关联只提供研究上下文，不自动展开多证券研究、不恢复暂停委托。读取持仓、自选变化和用户选中证券都不自动授权持续研究或外发。
