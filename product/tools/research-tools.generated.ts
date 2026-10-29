// 自动生成；请修改 Python tool_contracts.py 后运行 npm run tools:generate。
export const researchToolCatalog = [
  {
    "availability": "configured",
    "category": "公告",
    "description": "公告正文链接：巨潮公告清单与原文链接，可按日期与关键词过滤；不解析 PDF 正文。 返回真实状态、来源、时间及证据编号。",
    "name": "announcement_document_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "公告正文链接"
  },
  {
    "availability": "configured",
    "category": "披露",
    "description": "公告检索：按公司代码/名称在最近 N 天公告列表中检索；不抓取公告正文。 返回真实状态、来源、时间及证据编号。",
    "name": "announcement_search",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "公告检索"
  },
  {
    "availability": "configured",
    "category": "基准",
    "description": "基准映射：按证券板块给出主基准、兜底基准及指数代码。 返回真实状态、来源、时间及证据编号。",
    "name": "benchmark_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "基准映射"
  },
  {
    "availability": "configured",
    "category": "基准",
    "description": "基准表现：基准指数历史行情与区间表现，数据来自新浪/中证指数。 返回真实状态、来源、时间及证据编号。",
    "name": "benchmark_performance_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "基准表现"
  },
  {
    "availability": "configured",
    "category": "债券",
    "description": "转债条款：可转债基本条款与发行信息。 返回真实状态、来源、时间及证据编号。",
    "name": "bond_terms_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "转债条款"
  },
  {
    "availability": "configured",
    "category": "债券",
    "description": "债券收益率曲线：国债、国开债与中短期票据收益率曲线，按曲线名称与期限返回；引用必须写明曲线。 返回真实状态、来源、时间及证据编号。",
    "name": "bond_yield_curve_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "债券收益率曲线"
  },
  {
    "availability": "configured",
    "category": "资金",
    "description": "资金流向：东方财富个股资金流近 20 个交易日（主力/超大单/大单/中单/小单净流入及占比）。 返回真实状态、来源、时间及证据编号。",
    "name": "capital_flow_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "资金流向"
  },
  {
    "availability": "configured",
    "category": "大宗",
    "description": "商品价格：商品主力连续合约价格序列。 返回真实状态、来源、时间及证据编号。",
    "name": "commodity_price_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "商品价格"
  },
  {
    "availability": "configured",
    "category": "公司",
    "description": "公司治理：法人代表、注册资本、成立/上市日期与机构简介；不含完整董监高名单。 返回真实状态、来源、时间及证据编号。",
    "name": "company_governance_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "公司治理"
  },
  {
    "availability": "configured",
    "category": "公司",
    "description": "公司资料：巨潮公司档案：法定名称、行业、法人代表、经营范围与简介。 返回真实状态、来源、时间及证据编号。",
    "name": "company_profile",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "公司资料"
  },
  {
    "availability": "configured",
    "category": "公司",
    "description": "公司关系查询：本地实体关系为基础，产业链服务在线时补充上下游与关联关系。 返回真实状态、来源、时间及证据编号。",
    "name": "company_relationship_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "公司关系查询"
  },
  {
    "availability": "configured",
    "category": "债券",
    "description": "可转债查询：可转债主数据检索（代码/简称）。 返回真实状态、来源、时间及证据编号。",
    "name": "convertible_bond_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "description": "公开数据源代码；查询候选用，不表示已确认对象",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "name": {
          "description": "名称或检索词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "可转债查询"
  },
  {
    "availability": "configured",
    "category": "公司",
    "description": "分红送配：按报告期披露的分红送配历史（送转、现金分红、除权除息日）。 返回真实状态、来源、时间及证据编号。",
    "name": "dividend_history_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "分红送配"
  },
  {
    "availability": "configured",
    "category": "资金",
    "description": "龙虎榜：近期龙虎榜上榜记录与买卖额。 返回真实状态、来源、时间及证据编号。",
    "name": "dragon_tiger_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "龙虎榜"
  },
  {
    "availability": "configured",
    "category": "基金",
    "description": "ETF 排行：场内 ETF 实时行情排行，可按涨幅、跌幅、成交额与成交量排序或按名称过滤。 返回真实状态、来源、时间及证据编号。",
    "name": "etf_ranking_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "etf_sort": {
          "enum": [
            "涨幅",
            "跌幅",
            "成交额",
            "成交量"
          ],
          "type": "string"
        },
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "ETF 排行"
  },
  {
    "availability": "external_service",
    "category": "事件",
    "description": "事件监控设置：写入监控规则必须由用户明确授权；服务未启动时不写入。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "event_monitor_setup",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    },
    "requires_authorization": true,
    "title": "事件监控设置"
  },
  {
    "availability": "configured",
    "category": "事件",
    "description": "事件时间线：优先盯盘服务事件流，服务不可用时回退个股新闻。 返回真实状态、来源、时间及证据编号。",
    "name": "event_timeline_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "事件时间线"
  },
  {
    "availability": "configured",
    "category": "财务",
    "description": "财务数据：A 股财务摘要指标，按报告期返回最近若干期。 返回真实状态、来源、时间及证据编号。",
    "name": "financials_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "periods": {
          "maximum": 20,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "财务数据"
  },
  {
    "availability": "configured",
    "category": "宏观",
    "description": "人民币汇率：外汇即期快照（含人民币货币对），可按名称过滤；不是银行牌价或远期汇率。 返回真实状态、来源、时间及证据编号。",
    "name": "forex_rate_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "人民币汇率"
  },
  {
    "availability": "configured",
    "category": "基金",
    "description": "基金持仓：基金季度持仓；当年为空时回退上一年。 返回真实状态、来源、时间及证据编号。",
    "name": "fund_holdings_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "year": {
          "pattern": "^20\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "基金持仓"
  },
  {
    "availability": "configured",
    "category": "基金",
    "description": "基金查询：全市场基金名录检索（代码/简称）。 返回真实状态、来源、时间及证据编号。",
    "name": "fund_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "description": "公开数据源代码；查询候选用，不表示已确认对象",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "name": {
          "description": "名称或检索词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "基金查询"
  },
  {
    "availability": "configured",
    "category": "基金",
    "description": "基金表现：ETF 用新浪历史价格，其他基金用单位净值走势。 返回真实状态、来源、时间及证据编号。",
    "name": "fund_performance_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "基金表现"
  },
  {
    "availability": "configured",
    "category": "行情",
    "description": "个股人气榜：东方财富人气榜/飙升榜，反映股吧关注度，不代表资金或基本面。 返回真实状态、来源、时间及证据编号。",
    "name": "hot_stock_rank_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "rank_type": {
          "enum": [
            "人气榜",
            "飙升榜"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "个股人气榜"
  },
  {
    "availability": "configured",
    "category": "指数",
    "description": "指数成分：指数成分股，新浪失败时回退中证指数。 返回真实状态、来源、时间及证据编号。",
    "name": "index_constituents_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "指数成分"
  },
  {
    "availability": "configured",
    "category": "指数",
    "description": "指数查询：指数实时快照与实体信息。 返回真实状态、来源、时间及证据编号。",
    "name": "index_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "description": "公开数据源代码；查询候选用，不表示已确认对象",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "name": {
          "description": "名称或检索词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "指数查询"
  },
  {
    "availability": "configured",
    "category": "指数",
    "description": "指数表现：指数历史行情与区间表现。 返回真实状态、来源、时间及证据编号。",
    "name": "index_performance_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "指数表现"
  },
  {
    "availability": "configured",
    "category": "产业",
    "description": "产业链查询：查询已确认证券对应公司或行业主题的产业链；资料未准备时明确说明，不探测旧服务。 返回真实状态、来源、时间及证据编号。",
    "name": "industry_chain_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "depth_down": {
          "maximum": 3,
          "minimum": 0,
          "type": "integer"
        },
        "depth_up": {
          "maximum": 3,
          "minimum": 0,
          "type": "integer"
        },
        "top_down": {
          "maximum": 20,
          "minimum": 1,
          "type": "integer"
        },
        "top_up": {
          "maximum": 20,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "产业链查询"
  },
  {
    "availability": "configured",
    "category": "行业",
    "description": "行业查询：标准行业名称、别名与归属；可选返回本地名称表中的成员公司。 返回真实状态、来源、时间及证据编号。",
    "name": "industry_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "include_members": {
          "type": "boolean"
        },
        "member_limit": {
          "maximum": 500,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "行业查询"
  },
  {
    "availability": "configured",
    "category": "行业",
    "description": "行业表现：同花顺行业/概念板块行情；分类口径与本地行业不同，需复核。 返回真实状态、来源、时间及证据编号。",
    "name": "industry_performance_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "行业表现"
  },
  {
    "availability": "configured",
    "category": "公司",
    "description": "机构调研：近 N 天机构调研记录（接待日期、机构数量、接待方式与人员）。 返回真实状态、来源、时间及证据编号。",
    "name": "institution_survey_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "机构调研"
  },
  {
    "availability": "configured",
    "category": "大宗",
    "description": "库存数据：期货品种库存序列。 返回真实状态、来源、时间及证据编号。",
    "name": "inventory_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "库存数据"
  },
  {
    "availability": "configured",
    "category": "新股",
    "description": "IPO 发行信息：单只新股的发行日期、发行价、发行市盈率、募资净额与主承销商。 返回真实状态、来源、时间及证据编号。",
    "name": "ipo_detail_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "IPO 发行信息"
  },
  {
    "availability": "configured",
    "category": "行情",
    "description": "涨停板股池：涨停、跌停、强势与炸板股池，含连板数、封板资金与所属行业；自动回溯最近交易日。 返回真实状态、来源、时间及证据编号。",
    "name": "limit_pool_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "pool_type": {
          "enum": [
            "涨停",
            "跌停",
            "强势",
            "炸板"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "涨停板股池"
  },
  {
    "availability": "configured",
    "category": "宏观",
    "description": "宏观事件检索：基于新闻关键词检索宏观事件，不是结构化事件库。 返回真实状态、来源、时间及证据编号。",
    "name": "macro_event_search",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "keyword"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "宏观事件检索"
  },
  {
    "availability": "configured",
    "category": "宏观",
    "description": "宏观序列：CPI/PPI/PMI/GDP/M2/社融/LPR/SHIBOR 等宏观序列。 返回真实状态、来源、时间及证据编号。",
    "name": "macro_series_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "宏观序列"
  },
  {
    "availability": "configured",
    "category": "资金",
    "description": "融资余额：沪深两融明细，按最近交易日回溯查询。 返回真实状态、来源、时间及证据编号。",
    "name": "margin_balance_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "融资余额"
  },
  {
    "availability": "configured",
    "category": "事件",
    "description": "市场快讯：东方财富全球财经快讯与财联社电报，可按关键词过滤；快讯是未核实线索。 返回真实状态、来源、时间及证据编号。",
    "name": "market_news_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "news_source": {
          "enum": [
            "全部",
            "财联社",
            "东方财富"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "市场快讯"
  },
  {
    "availability": "configured",
    "category": "行情",
    "description": "市场概览：主要宽基指数快照与全市场涨跌家数、涨停跌停等情绪指标；部分来源失败时明确告警。 返回真实状态、来源、时间及证据编号。",
    "name": "market_overview_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "市场概览"
  },
  {
    "availability": "configured",
    "category": "估值",
    "description": "市场估值：全 A 或主要宽基指数的市盈率水平与历史分位，用于判断整体估值位置。 返回真实状态、来源、时间及证据编号。",
    "name": "market_valuation_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "index_name": {
          "enum": [
            "全A",
            "沪深300",
            "上证50",
            "中证500",
            "中证1000",
            "中证800"
          ],
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "市场估值"
  },
  {
    "availability": "configured",
    "category": "行情",
    "description": "分钟线：A 股 1/5/15/30/60 分钟线，覆盖最近几个交易日，未复权。 返回真实状态、来源、时间及证据编号。",
    "name": "minute_bar_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "minute_period": {
          "enum": [
            "1",
            "5",
            "15",
            "30",
            "60"
          ],
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "分钟线"
  },
  {
    "availability": "configured",
    "category": "政策",
    "description": "官方文件检索：中国政府网政策文件库检索（国务院/部门文件），返回标题、文号、发布机构与原文链接。 返回真实状态、来源、时间及证据编号。",
    "name": "official_document_search",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "doc_type": {
          "enum": [
            "国务院文件",
            "部门文件"
          ],
          "type": "string"
        },
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "page": {
          "maximum": 10,
          "minimum": 1,
          "type": "integer"
        },
        "sort": {
          "enum": [
            "date",
            "score"
          ],
          "type": "string"
        }
      },
      "required": [
        "keyword"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "官方文件检索"
  },
  {
    "availability": "configured",
    "category": "行情",
    "description": "港美股行情：港股与美股的历史日线行情与区间摘要，当地货币计价。 返回真实状态、来源、时间及证据编号。",
    "name": "overseas_quote_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "description": "公开数据源代码；查询候选用，不表示已确认对象",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "market": {
          "enum": [
            "港股",
            "美股"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "港美股行情"
  },
  {
    "availability": "configured",
    "category": "基准",
    "description": "可比公司构建：按本地行业归属与市值构建可比组，未做业务相似度核验。 返回真实状态、来源、时间及证据编号。",
    "name": "peer_group_builder",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "可比公司构建"
  },
  {
    "availability": "configured",
    "category": "业绩",
    "description": "业绩快报：按报告期列示 A 股业绩快报的营收、净利润与同比，可按名称或行业检索；是初步核算数。 返回真实状态、来源、时间及证据编号。",
    "name": "performance_express_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "report_period": {
          "description": "报告期，形如 20260930",
          "pattern": "^20\\d{2}(0331|0630|0930|1231)$",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "业绩快报"
  },
  {
    "availability": "configured",
    "category": "业绩",
    "description": "业绩预告：按报告期列示 A 股业绩预告，含预告类型、变动幅度与原因；可按类型排序或按名称检索。 返回真实状态、来源、时间及证据编号。",
    "name": "performance_forecast_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "forecast_type": {
          "enum": [
            "全部",
            "预增",
            "预减",
            "扭亏",
            "首亏",
            "续盈",
            "续亏",
            "略增",
            "略减",
            "不确定"
          ],
          "type": "string"
        },
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "report_period": {
          "description": "报告期，形如 20260930",
          "pattern": "^20\\d{2}(0331|0630|0930|1231)$",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "业绩预告"
  },
  {
    "availability": "configured",
    "category": "政策",
    "description": "政策检索：基于新闻关键词检索政策报道，不等同于官方文件库。 返回真实状态、来源、时间及证据编号。",
    "name": "policy_search",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "keyword"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "政策检索"
  },
  {
    "availability": "configured",
    "category": "用户事实",
    "description": "用户持仓查询：读取用户持仓；执行前必须确认授权状态。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "portfolio_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    },
    "requires_authorization": true,
    "title": "用户持仓查询"
  },
  {
    "availability": "configured",
    "category": "用户事实",
    "description": "持仓风险分析：持仓集中度与成本权重；执行前必须确认授权状态。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "portfolio_risk_analysis",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    },
    "requires_authorization": true,
    "title": "持仓风险分析"
  },
  {
    "availability": "configured",
    "category": "行情",
    "description": "历史行情：A 股前复权日线行情；新浪不可用时回退东方财富。 返回真实状态、来源、时间及证据编号。",
    "name": "quote_history",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "adjust": {
          "enum": [
            "qfq",
            "hfq"
          ],
          "type": "string"
        },
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "历史行情"
  },
  {
    "availability": "configured",
    "category": "区域",
    "description": "区域政策检索：基于新闻关键词检索区域政策报道。 返回真实状态、来源、时间及证据编号。",
    "name": "regional_policy_search",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "keyword": {
          "description": "公开资料检索关键词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "keyword"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "区域政策检索"
  },
  {
    "availability": "configured",
    "category": "研究",
    "description": "研报正文读取：读取已确认公司研报列表中选定报告的1至5页正文，保留页码、文档校验和与截断；不接受任意URL，扫描件与失败保持不可用。 返回真实状态、来源、时间及证据编号。",
    "name": "research_report_document_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "page_count": {
          "maximum": 5,
          "minimum": 1,
          "type": "integer"
        },
        "report_id": {
          "description": "研报列表返回的 report_id，不是 URL",
          "maxLength": 26,
          "minLength": 14,
          "pattern": "^AP[0-9]{12,24}$",
          "type": "string"
        },
        "start_page": {
          "maximum": 400,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id",
        "report_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "研报正文读取"
  },
  {
    "availability": "configured",
    "category": "研究",
    "description": "研报与一致预期：个股卖方研报清单、东财评级、机构与年度盈利预测（一致预期线索）；评级是卖方观点，不是事实。 返回真实状态、来源、时间及证据编号。",
    "name": "research_report_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "研报与一致预期"
  },
  {
    "availability": "configured",
    "category": "公司",
    "description": "限售解禁：查询个股在给定窗口内的限售解禁记录；计划可能随公告调整。 返回真实状态、来源、时间及证据编号。",
    "name": "restricted_release_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "限售解禁"
  },
  {
    "availability": "configured",
    "category": "资金",
    "description": "板块资金流排行：行业/概念/地域板块主力净流入排行，支持今日、5日、10日周期。 返回真实状态、来源、时间及证据编号。",
    "name": "sector_fund_flow_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "flow_type": {
          "enum": [
            "行业资金流",
            "概念资金流",
            "地域资金流"
          ],
          "type": "string"
        },
        "indicator": {
          "enum": [
            "今日",
            "5日",
            "10日"
          ],
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "板块资金流排行"
  },
  {
    "availability": "configured",
    "category": "行业",
    "description": "板块排行：同花顺行业与概念板块当日涨幅、净流入、上涨家数与成交额排行，可按涨幅、跌幅等排序；不绑定具体板块实体。 返回真实状态、来源、时间及证据编号。",
    "name": "sector_ranking_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "sector_sort": {
          "enum": [
            "涨幅",
            "跌幅",
            "净流入",
            "上涨家数",
            "成交额"
          ],
          "type": "string"
        },
        "sector_type": {
          "enum": [
            "行业",
            "概念"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "板块排行"
  },
  {
    "availability": "configured",
    "category": "证券",
    "description": "证券名称/代码查询：本地实体库精确查询证券；返回实体状态，未核验数据会显式标注。 返回真实状态、来源、时间及证据编号。",
    "name": "security_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "code": {
          "description": "公开数据源代码；查询候选用，不表示已确认对象",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "name": {
          "description": "名称或检索词",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "证券名称/代码查询"
  },
  {
    "availability": "configured",
    "category": "公司",
    "description": "股东户数：历史股东户数与环比变化，用于观察筹码集中度；户数受股本变动影响。 返回真实状态、来源、时间及证据编号。",
    "name": "shareholder_count_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "股东户数"
  },
  {
    "availability": "configured",
    "category": "估值",
    "description": "个股估值：单只 A 股的市值、市盈率、市净率、市现率时间序列与所选区间分位。 返回真实状态、来源、时间及证据编号。",
    "name": "stock_valuation_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "valuation_indicator": {
          "enum": [
            "总市值",
            "市盈率(TTM)",
            "市盈率(静)",
            "市净率",
            "市现率"
          ],
          "type": "string"
        },
        "valuation_period": {
          "enum": [
            "近一年",
            "近三年",
            "近五年",
            "近十年",
            "全部"
          ],
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "个股估值"
  },
  {
    "availability": "configured",
    "category": "策略",
    "description": "策略影子归因：影子组合整体收益/回撤与每策略贡献；数据不足时显式说明，不做外推。 返回真实状态、来源、时间及证据编号。",
    "name": "strategy_attribution_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "strategy_id": {
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "策略影子归因"
  },
  {
    "availability": "configured",
    "category": "策略",
    "description": "策略进化预案查询：只读当前待确认的升级/降级/淘汰/变异预案；应用预案必须由用户确认。 返回真实状态、来源、时间及证据编号。",
    "name": "strategy_evolution_preview",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "strategy_id": {
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "策略进化预案查询"
  },
  {
    "availability": "configured",
    "category": "策略",
    "description": "策略池状态查询：策略池阶段、影子数据天数与每策略判定；无记录时显示空态，不伪造策略。 返回真实状态、来源、时间及证据编号。",
    "name": "strategy_pool_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "strategy_id": {
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "策略池状态查询"
  },
  {
    "availability": "configured",
    "category": "风格",
    "description": "风格成分：返回风格代理指数的成分股，并披露代理关系。 返回真实状态、来源、时间及证据编号。",
    "name": "style_constituents_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "风格成分"
  },
  {
    "availability": "configured",
    "category": "风格",
    "description": "风格表现：用有明确口径的指数代理风格表现，并披露代理关系。 返回真实状态、来源、时间及证据编号。",
    "name": "style_performance_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "days": {
          "maximum": 1095,
          "minimum": 1,
          "type": "integer"
        },
        "end_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "start_date": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "风格表现"
  },
  {
    "availability": "unconfigured",
    "category": "大宗",
    "description": "供需数据：已核查库存、价格与新闻接口，均无可复现的供需平衡表；不得用库存/价格冒充供需。 返回真实状态、来源、时间及证据编号。",
    "name": "supply_demand_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "供需数据"
  },
  {
    "availability": "configured",
    "category": "主题",
    "description": "主题成分：按主题名称匹配同花顺概念板块，抓取涨幅排序的前若干页成分股；不是完整成分列表。 返回真实状态、来源、时间及证据编号。",
    "name": "theme_constituents_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        },
        "pages": {
          "maximum": 5,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "主题成分"
  },
  {
    "availability": "configured",
    "category": "主题",
    "description": "主题/赛道查询：本地主题词典，提供标准名、别名与本地关系；不含成分股。 返回真实状态、来源、时间及证据编号。",
    "name": "theme_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "confirmation_id": {
          "description": "当前对话用户已选择的实体确认回执 ID；不能使用其他会话回执",
          "maxLength": 200,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "confirmation_id"
      ],
      "type": "object"
    },
    "requires_authorization": false,
    "title": "主题/赛道查询"
  },
  {
    "availability": "configured",
    "category": "用户事实",
    "description": "用户自选查询：读取用户自选；执行前必须确认授权状态。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "watchlist_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    },
    "requires_authorization": true,
    "title": "用户自选查询"
  }
]
