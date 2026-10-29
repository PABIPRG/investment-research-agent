---
name: huohuo-deliverables
description: 用户要求把已获取资料、研究结果、对比表或分析整理成可下载 CSV、JSON、Excel 文件，或核对此前交付文件时使用。
---

# 研究成果交付

用户明确要求文件时使用 create_research_file；普通解释仍在对话中完成。支持 CSV、JSON、xlsx，不执行代码、公式、任意文件读写或外发。

1. 明确格式和内容，复用用户已给出的意图，不为已有信息反复提问。CSV 用于单表，JSON 保留嵌套原始值，Excel 支持多表和基础排版。用户只说 Excel 时使用 xlsx。
2. 原始资料用 content_kind=evidence，evidence_ids 必须是本会话真实研究工具返回的编号。程序直接读取来源；不得重抄数据为 rows。JSON 可以省略 tables，保留原始嵌套结果；CSV/Excel 的每张表指定 evidence_id、records_path（如 ["data","records"]，必须匹配实际结构）和 columns。字段 key 为来源记录的原始字段名。
3. 研究总结、观点、跨来源整理用 content_kind=model_analysis，tables.rows 填结构化结果；evidence_ids 引用真实依据。明确标注模型整理；引用只证明来源存在，不等于程序已验证每条推断。无来源的用户提供内容可以整理，但 limitations 必须说明来源与未核实内容，不编造证据。
4. columns 指定 key、label、type 和可选 unit。证券代码用 text 保留前导零，金额带币种/单位，percent 使用小数（8%=0.08），date 为 YYYY-MM-DD。未知填 null；不把缺数变成零或字符串“未知”塞入数值列。JSON 中 null 原样保留，Excel 空单元格表示未知；CSV 空串与未知均为空。
5. 必填 limitations，说明数据时点、来源失败/部分覆盖、口径及用途；没有额外限制可为空，但不能宣称实时、完整或已审计。生成时间与财务报告期、行情时间不同。CSV 对代码前导零/公式起始文本增加单引号；机器无损消费优先 JSON/XLSX，并在交付时说明。
6. 只以 ok=true 的 file 回执说明已生成。文件卡片提供主文件和配套交付说明 JSON（来源原始记录、时间、字段单位、限制），不要把本机绝对路径作为用户操作说明。每次生成独立副本，文件不随以后研究更新。
7. 生成失败说明原因并缩小范围或修正类型；最多六表、每表四十列/五千行、合计五万单元格、单文件10 MiB。网络中断可能已生成：保留回执的 source_call_id，用 read_research_file 的同名参数核对，不自动换调用重复提交；已知 file.id 时改用 id 核对并重新展示同一成果，两者只填一个。下载失败重试原下载，不重做研究。

生成和下载不更改持仓、委托、策略或通知许可；文件保存在本实例，用户可自行下载保存副本。服务重启后可回查原记录；文件缺失或校验失败不能声称仍可下载。
