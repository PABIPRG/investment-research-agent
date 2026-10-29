---
name: huohuo-strategies
description: 当用户希望建立可验证的技术规则研究策略，运行回测、影子验证、查询策略状态/归因、生成或确认进化预案时使用；不把候选、验证通过、实际收益或真实交易混为一谈。
---
# 策略验证与演进

1. 先用 read_strategy_records 查询当前实例已有记录、名称、最新版本与已保存 OOS 聚合先验（样本不足不算通过）；三个 strategy_* 查询可查状态、影子归因和当前已保存预案。空安装说明尚未建立策略，继续帮助用户形成可验证规则，不要求旧服务地址。
2. 建立假设时澄清证券与来源、规则、参数、研究理由和方向。通过 security_lookup/search_securities 查证券名称，不编造代码。支持 ma_cross、momentum、rsi_reversal、breakout、bollinger、volume_breakout，每策略 1–3 只沪深 A 股。DSH 负责提出与解释假设，侧车负责校验、确认与保存。
3. 用 manage_strategy 的 create 发起程序生成的原生确认。params 只能包含对应规则字段。证券需 securities:[{code,name}]；明确 name、kind、params、rationale、direction。不以模型文本或自由回答代替确认。
4. 用户要求回测时先查询 strategy_id/revision，明确 start_date/end_date，使用 backtest。日期为 40–1095 个自然日且不能在未来；固定样本内/外 70/30，不允许反复调参后把样本外当独立检验。
5. backtest 回执完成后才讨论结果；active 是参与状态，passed/not_passed/insufficient 是验证分类，二者独立。全部行情失败不激活候选，不把失败或样本不足说成策略无效。
6. shadow 按已完成的最新日线更新虚拟资金验证。首次从本次实际跟踪日开始，不用历史回测曲线冒充此前已经持续跟踪的影子记录。默认只按本次确认运行。用户希望持续验证时，按第 10 条明确后台范围与时间。
7. 累积至少 5 个有效影子日期后，用 evolve 生成进化预案。全池比较/重组使用 payload:{scope:"pool",state_version:当前查询返回的版本}；仅处理指定策略时使用 strategy_id/revision；GET 预案查询不会生成或自动应用。apply 必须携带当前 strategy_id/revision/preview_token 并等待原生确认；程序核验来源版本、时效，原子执行精确动作。变异产生的新候选需要重新回测。
8. 这些结果是仅做多、分数股、不含费用/滑点/涨跌停限制的研究模拟，与用户真实持仓、已发生成交和实盘可执行收益分开。优先用证券名称呈现，代码作辅助。
9. 网络失败、过期、未知提交、停止和重启中断分别说明。先查询运行回执，不自动重试，不从其他实例读取记录，不索取密钥，不调用旧服务地址或交易接口。

10. 后台计划默认关闭。先查询 automation，然后用 manage_strategy action=schedule，payload 包含 revision、enabled、daily_time（北京时间16:00–23:59）、strategy_ids（明确列表）、actions（backtest/shadow/evolve）、retest_days（1–365）、lookback_days（40–1095）、event_candidates、archive_recall。读出的 next_at/updated_at 不放入 payload。先说明范围、日程、数据缺失与候选审批，再请求原生确认。停用时使用同一最新计划字段与 enabled=false；停用取消排队和迟到结果，保留历史。新策略不会自动加入旧计划。
11. suggestions 是后台事件研究/归档召回提出的建议，尚未成为正式策略。展示证券名称、规则、研究理由、来源和限制，用户明确要保存时使用 accept_suggestion + suggestion_id，等待原生确认。保存后仍为 candidate，需要重新回测；不能把建议、召回、保存或模型输出称作通过验证。
12. background_jobs/planner_jobs 的 pending、running、completed、skipped、failed、interrupted、cancelled 分别解释。后台回测/影子结果落在同一 runs 与来源证据链；模型只在有界 DSH 中提出事件假设，不取得保存或应用权限。归档召回没有当前有效市场环境时等待，不伪造结果。

13. event_candidates 开启后按 daily_time 独立采集计划内证券的新闻，不依赖用户另建持续委托；最多 20 只证券。来源失败会保留失败记录，不能解释成“没有新闻”。新闻到达后 DSH 只提出建议，仍需用户确认保存。

回复中引用回测、影子结果、进化预案或策略记录时，在末尾单列「数据来源」：写来源名称（数据接口）、数据时间、运行 ID 或 evidence_id，以及策略 ID/版本；后台建议写「本实例策略记录」并注明尚未验证。模型提出的假设或解释单独标为推断，不写成程序验证结论。
