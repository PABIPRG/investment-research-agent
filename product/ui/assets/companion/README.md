# 火火 IP 资源 V1.4-r4-live-motion

保留已有 `huohuo-animated.glb` 的几何和 12 个动作片段，复用现有 Three.js 播放器。`renderer.js` 在身体局部坐标中加入与新版 Blender 对齐的柔粉腮红，所有动作统一使用；静态后备 `fallback.png` 同步采用新版待机形象。资产哈希见 `resource-manifest.json`。

顶部栏专用 `header-peek.png` 来自已确认的放大镜扒栏透明母图，显示一手握镜、一手扒栏的半脸构图。它与通用头像、favicon 分别导出，减少动态效果时也保持静态。可编辑 Blender/图标母版见仓库 `design/huohuo/`；执行 `python3 scripts/export-brand-assets.py` 可重复生成 PNG/ICO 和指纹，工具依赖 Pillow。

GLB 自身未烘焙 Blender 程序化材质；单独在其他播放器打开不等于产品中的暖橙腮红效果。产品模型、renderer 和静态后备作为同一资源修订交付；放大镜动画仍是独立设计源，顶部栏当前使用静态图标。

Three.js r180 及 GLTFLoader、BufferGeometryUtils、RoomEnvironment 为本地随包资源，许可证保存在 `vendor/THREE-LICENSE.txt`。相关模块的 three 导入已改为同目录相对路径；运行时不请求 CDN。

`renderer.js` 负责相机、材质、动画混合和生命周期。业务到动作的优先级在 `companion-state.ts`。模型/渲染器失败后显示静态 IP；隐藏标签暂停动画，减少动态效果使用静帧；卸载时释放渲染器和模型资源。

静态交互稿是经过确认的设计记录，产品实际动作由 DSH 当前状态驱动。资源修订应更新哈希；不可用新版资源覆盖已归档交互稿。


2026-10-27 显示校色：用户确认聊天角色相对顶部图标偏浅、偏黄。身体材质在 tone mapping 和输出色域转换后，以最大通道为基准增加1.6倍色度，并对橙黄色区减少0.04倍色度的绿色通道，保留高光峰值、体积与腮红；只作用于SpiritBody，不给整个canvas或页面施加滤镜。参数见resource-manifest.json的displayGrade；静态母图和GLB几何/12动作不变。


2026-10-28 实时动作接线：优先读取DSH当前trajectory的partial尾块和runningCalls。推理与工具参数准备为thinking，工具实际start为working，正文text输出为speaking；原生pendingInteraction最高优先，结束后不从历史推理文本推测仍在运行。移除DOM笼统data-streaming对正文／推理的误分类。

thinking和working复用现有8秒thinking_notes片段，分别从3.7秒咬笔前段和0.8秒笔记整理段起播，随后保留原片段的连贯循环；没有修改GLB或新增模型。相同clip的业务阶段切换仍更新起始时间与动作标签；不在每个token更新时重启动作。失败继续一次轻叹，普通完成回待命，不以动画宣称研究结论正确、发现机会或收益。
