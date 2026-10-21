# 来源与第三方组件

MiaoTask 基于 [MonsterNone/tmall-miao](https://github.com/MonsterNone/tmall-miao) 的 next 分支改造，感谢原作者及贡献者。来源基准为 [9318d3d138d5fa53cff00601740de012da831c65](https://github.com/MonsterNone/tmall-miao/tree/9318d3d138d5fa53cff00601740de012da831c65)。

原项目提供手机连接、Android / HarmonyOS 驱动及活动入口基础。本项目沿用并修改设备适配和搜索入口，重写双11任务流程，增加本地网页、OCR、进度核验、实例管理、日记录与便携分发；独立维护。

截至2026-10-18检查时，上游 next 未提供 LICENSE。本仓库保留来源与权利归属，不为上游代码另行声明 MIT、Apache 等许可。上游代码、改造代码和第三方组件的权利与义务分别保留。

便携包使用 Python、PyInstaller、uiautomator2、hmdriver2、ADB、RapidOCR、ONNX Runtime、NumPy、OpenCV 和 Pillow 等组件。构建脚本将许可与通知收集到 `licenses/`，ADB 通知原文附带，以各许可证原文为准。

## 图标

橙色猫头与完成勾图标由内置生图工具生成，母版和导出文件位于源码 `web/assets/`。PNG 覆盖16至1024像素，ICO 含16、20、24、32、40、48、64、128、256像素，用于网页、浏览器、EXE 和系统托盘。`scripts/export_icons.py` 只缩放与转换格式，保持图形统一。
