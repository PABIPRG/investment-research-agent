# 火火独立产品协作约定

- 先读 README、docs/设计基线/V1.4-团队Brief.md，再读 docs/当前架构与装配.md 和对应验证记录；完整契约见 docs/设计基线/V1.4-产品与架构设计.md。历史状态不冒充当前进度，工程装配图不能替换业务主图。
- 图的唯一结构源是文档中的 Mermaid；scripts/render-architecture.py 直接渲染 SVG，禁止另手写一套近似节点/边。修改图后执行其 --check 并检查实际 SVG。精选导出须保留可移植设计基线，不因原稿含本地路径整组排除。
- DSH 拥有完整 Agent、会话、工具和 Skill 基础；product 只装配与适配；sidecar 拥有正式业务状态、证据和有界研究；distribution 拥有实例与进程生命周期。不得恢复旧 Python 全功能 Agent。
- 身份、权限、版本、取消代次、租约、幂等、证据准入和通知资格由程序强制。Skill 不授予权限。unknown/error 不折叠成 false；通知 unknown 不自动重发。
- 一项独立任务使用独立特性分支、worktree、主要写入者及端口/实例/缓存。写前核对目录、HEAD、状态、远端和分配，保留不相关改动。默认分支以实际仓库为准，不沿用来源仓的跨仓 remote 规则。
- 未获本次目标与具体操作授权，不访问用户远程服务器（包括只读），不部署、不发真实通知。提交、推送、PR、合并与发布授权分别处理；AI 提交/PR 标题使用 `[AI] `。
- 项目追踪使用 Linear：workspace/team `PABIPRG`，team key `PAB`，项目“投研智能体”，ID `08905897-5bb3-4f89-8a07-5729018a65b4`。创建 issue 前展示草稿并取得确认；代码/CI/UAT/发布分开记录，提交不等于 Done。
- TypeScript 用于产品与前端，Python 用于现有业务；沿用代码风格和接口，不为局部改动引入平行体系。
- 运行最小必要检查：npm run check/build、相关 Node/Python 测试；按需 npm run smoke:skills，涉及安装/worker 再跑 npm run smoke。命令和端口见 docs/开发指引.md。
- 用户可见行为必须在真实浏览器验证关键交互、失败和持久性。区分受控模型/合成数据与真实研究，不以截图或构建代替业务证据。
- 实例、凭据、数据库、缓存和 node_modules 不进入源码或发布；不读取他人的旧实例作为测试捷径。
