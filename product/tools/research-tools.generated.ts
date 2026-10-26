// 自动生成；请修改 Python tool_contracts.py 后运行 npm run tools:generate。
export const researchToolCatalog = [
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
    "description": "资金流向：同花顺即时资金流快照（流入/流出/净额）。 返回真实状态、来源、时间及证据编号。",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "external_service",
    "description": "事件监控设置：写入监控规则必须由用户明确授权；服务未启动时不写入。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "event_monitor_setup",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
    "description": "产业链查询：产业链多层链路；服务不可用时回退实体库直接关系并明确告警。 返回真实状态、来源、时间及证据编号。",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
    "description": "用户持仓查询：读取用户持仓；执行前必须确认授权状态。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "portfolio_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    }
  },
  {
    "availability": "configured",
    "description": "持仓风险分析：持仓集中度与成本权重；执行前必须确认授权状态。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "portfolio_risk_analysis",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "external_service",
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
    }
  },
  {
    "availability": "external_service",
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
    }
  },
  {
    "availability": "external_service",
    "description": "策略池状态查询：策略池阶段、影子数据天数与每策略判定；服务未启动时返回 unavailable。 返回真实状态、来源、时间及证据编号。",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "unconfigured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
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
    }
  },
  {
    "availability": "configured",
    "description": "用户自选查询：读取用户自选；执行前必须确认授权状态。 返回真实状态、来源、时间及证据编号。当前独立实例未接通此项授权流程，调用只返回 needs_authorization，不会执行。",
    "name": "watchlist_lookup",
    "parameters": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    }
  }
]
