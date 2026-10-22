# 发布记录

按新到旧维护用户可见变化。GitHub Release 正文从对应的 `## 版本号` 小节提取，发布状态以 [Releases](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11/releases) 为准。

## MiaoTask-v0.1.0

多设备工作区、无线连接与可扩展活动框架。

* 【新增】同页多设备并行与批量配置启动；无线配对向导、IP 复用、MuMu 实例发现及不同屏幕适配。
* 【新增】任务行实时选择“执行 / 跳过”，选择与失败次数按设备、实例、日期保存。
* 【优化】框架、应用与前端分层，支持活动注册、分层配置，接续旧版日记录。
* 【文档】更新首页、连接教程和公共接口手册，统一 Issue/PR 与维护者手动发布流程，补齐许可声明。

下载 Windows x64 ZIP，完整解压后运行 `MiaoTask.exe`，保留 `_internal/`。升级前退出旧助手。安全认证需本人处理，诊断截图分享前请脱敏。

基于 [MonsterNone/tmall-miao next](https://github.com/MonsterNone/tmall-miao) 改造。[使用说明](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11/blob/main/docs/USAGE.md) · [项目介绍](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11#readme) · [许可范围](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11/blob/main/docs/LICENSING.md)

## MiaoTask-v0.0.9

分身管理、滚动设置与系统托盘。

* 【新增】淘宝主应用/分身选择与串行队列，按包名和用户空间锁定实例，统计独立保存；分身功能默认关闭。
* 【新增】Windows 托盘支持打开控制台、停止并退出。统一图标，任务、滚动和高级设置按需展开。
* 【优化】滚动距离、时长、连续次数和额外间隔范围可调，默认不增加额外等待；随机节奏不保证规避风控。
* 【修复】重启后实例确认失败，限定再次唤起同一实例；搜索键盘、多级跳转优先逐层返回，必要时回到桌面再重启恢复。
* 【修复】首页弹窗遮挡入口时先尝试返回；搜索兜底等待真实输入框。实际确认缺失的应用当天跳过。

下载 Windows x64 ZIP，完整解压后运行 `MiaoTask.exe`，保留 `_internal/`。升级前退出旧助手。安全认证需本人处理，诊断原图分享前请脱敏。

基于 [MonsterNone/tmall-miao next](https://github.com/MonsterNone/tmall-miao/tree/9318d3d138d5fa53cff00601740de012da831c65) 改造。[使用说明](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11/blob/main/docs/USAGE.md) · [项目介绍](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11#readme)

## v20261020-double11.8

* 兼容「去赚能量 / 赚能量」，同页重新定位后再考虑重启。
* 优化桌面冷启动、截图共享、OCR 缓存与预览刷新。

## v20261019-double11.7

* 分别等待开屏、首页、活动与任务菜单，正常首页路径不下滑，加载中不返回。
* 同时读到「做任务赚能量」标题和任务行后才执行，修复进入活动但未打开任务菜单的问题。

## v20261019-double11.6

* 活动菜单有限补点，搜索官方卡片优先右侧「进入」，避免同名搜索框误点。
* 普通异常限定冷重启恢复；认证停止并弹出 Windows 提醒，保留失败现场。
* 合并保留前版的一键执行、每日记录与诊断功能。

## v20261019-double11.5

此版本的 Release 已撤下，入口问题在后续修复。

* 合并识别与执行，增加自动活动定位、设备日累计和不可用任务缓存。
* 增加首次连接兼容、固定搜索文字及失败现场导出。

## v20261019-double11.4

* 改进搜索框聚焦、搜索提交与内嵌商品结果识别，不安装或切换输入法。
* 增加任务类型选择、前台弹层复核和操作演示。

## v20261018-double11.3

* 从上游 next 改造双11任务流程，提供本地网页、OCR、持续浏览、搜索与跳转核验。
* 支持动态任务和累计领奖，提供 Windows 便携包及公开文件审计。
