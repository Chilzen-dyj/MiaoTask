# 公共资源

框架和各应用共用的资源约定放在此层。当前图标由 `frontend/assets/` 维护，离线 OCR 权重随锁定的 RapidOCR 依赖打包，不重复复制模型。

便携包中的 ADB / 可选 HDC 放在 `_internal/shared/tools/`；源码构建使用 `build/vendor/` 的工具副本，二进制与模型不提交 Git。未来独立模型或设备资源可放入此层，并通过资源解析器及构建清单显式打包。

构建脚本统一保留在 `scripts/`，项目文档统一保留在 `docs/`，不在本层再维护副本。
