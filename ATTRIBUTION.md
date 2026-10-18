# 项目来源与第三方组件

喵任务双11助手基于 [MonsterNone/tmall-miao](https://github.com/MonsterNone/tmall-miao)
的 `next` 分支改造，感谢原作者 MonsterNone 及上游贡献者。

来源基准：[9318d3d138d5fa53cff00601740de012da831c65](https://github.com/MonsterNone/tmall-miao/tree/9318d3d138d5fa53cff00601740de012da831c65)。
原项目提供了电脑连接手机、Android / HarmonyOS 驱动适配、活动入口与自动化工具基础。
本仓库沿用并修改了驱动适配和搜索入口等代码，重写双11任务识别与执行流程，
新增本地控制台、离线 OCR、进度核验、跨应用恢复及便携发布流程。
本仓库独立维护；改动见 [CHANGELOG.md](CHANGELOG.md) 和 [架构设计](docs/ARCHITECTURE.md)。

截至 2026-10-18，所检查的上游 `next` 分支未提供 LICENSE。
本仓库保留上游来源与权利归属，不为上游代码另行声明 MIT、Apache 等许可。
上游代码、改造代码与随包第三方组件各自的权利归属应分别保留。

便携包使用 Python、PyInstaller、uiautomator2、hmdriver2、ADB、RapidOCR、ONNX Runtime、
NumPy、OpenCV、Pillow 等组件。相应许可及通知由构建脚本从安装包收集到 `licenses/`。
ADB 的上游通知文件按原文附带。各组件的权利与义务以其许可证原文为准。
