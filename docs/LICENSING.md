# 许可与来源

## 项目声明的范围

MiaoTask 原创的新增内容和修改，在贡献者有权授权的范围内采用 [Apache License 2.0](../LICENSE)。[NOTICE](../NOTICE) 说明适用范围与上游来源；第三方代码、模型和工具继续遵循各自条款。

本项目基于 [MonsterNone/tmall-miao next 的固定提交](https://github.com/MonsterNone/tmall-miao/tree/9318d3d138d5fa53cff00601740de012da831c65) 改造。2026-10-22 核查该提交的完整文件树、README 与源文件，未发现明确的许可证授予；GitHub 当前许可证接口也返回未找到。这不能证明上游已同意 Apache 2.0，项目声明不能代替其授权。

**待确认：上游原有部分及其衍生内容的再分发授权。** 在权利人明确许可前，不应把整份仓库或便携包描述为已获得统一 Apache 2.0 授权。若已有书面授权，应记录其适用内容与可核验来源；只写感谢或保留来源无法补足授权。

核查依据：[固定提交文件树 API](https://api.github.com/repos/MonsterNone/tmall-miao/git/trees/9318d3d138d5fa53cff00601740de012da831c65?recursive=1)、[该提交 README](https://raw.githubusercontent.com/MonsterNone/tmall-miao/9318d3d138d5fa53cff00601740de012da831c65/README.md)、[GitHub 的无许可证说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)、[Apache 2.0 原文](https://www.apache.org/licenses/LICENSE-2.0.txt)。

## 随包保留的声明

| 内容 | 许可材料与来源 |
| --- | --- |
| MiaoTask 原创贡献 | 包根目录的 `LICENSE`、`NOTICE`，以及 `licenses/MiaoTask/` 副本；适用范围同上 |
| Python 及 Python 依赖 | 构建环境提供的许可证、COPYING、LICENCE 和通知文件，按发行包保存在 `licenses/`；版本见包内 `build-manifest.json` |
| ONNX Runtime | 同时保留包内 `LICENSE` 与 `ThirdPartyNotices.txt`，不只收集 `.dist-info` 文件 |
| RapidOCR 与模型 | 保留发行包的 `LICENSE` 与 `MODEL_LICENSES.md`；模型权利归属与转换说明独立保留，不能只标注推理程序的许可 |
| FlatBuffers 25.12.19 | 该 Python wheel 未带独立许可文件，补入[官方固定版本 LICENSE](https://github.com/google/flatbuffers/blob/v25.12.19/LICENSE)及 [Python 文件中的原始声明](https://github.com/google/flatbuffers/blob/v25.12.19/python/flatbuffers/__init__.py)，来源记录随源码 `docs/licenses/flatbuffers-25.12.19.txt` 维护，随包放入 `licenses/flatbuffers/` |
| Android platform-tools | 保留官方发行包的 `NOTICE.txt`；缺失时拒绝构建 |

随包文件用于保留声明，不能据此推断所有依赖具有相同许可证。当前构建器会收集构建环境中的声明，其中也可能包含构建工具的许可；实际程序和环境信息以构建清单为准。

## 后续贡献

新增或替换依赖、模型、图片或上游代码时，在同一 PR 中记录准确版本、官方来源、许可范围和随包声明位置；不能只根据包元数据中的许可简称判断。FlatBuffers 补充材料仅对应已核查的固定版本，升级时重新核对。保留原有权利归属，不将未获授权的第三方内容自动归入项目许可。验证与打包步骤见 [BUILDING](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11/blob/main/docs/BUILDING.md)。
