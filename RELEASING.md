# 清洁构建与 GitHub Release

默认产物面向 Windows x64 + Android，包含 Python、ADB、网页和离线 OCR 模型。
采用目录型便携包：完整解压后双击 `MiaoTask.exe`，运行库留在 `_internal/`，避免每次启动解压模型。

## 0. 发布前文档审阅

当前 v9 处于候选发布阶段：只准备本地提交与 ZIP，待维护者审阅 README、随包说明、更新记录、风险与隐私、开发架构及对应 Release 文案后再推送和打标签。
Release 文案使用 `docs/RELEASE-<version.json 中的版本>.md`，本次为 [v9 文案](docs/RELEASE-v20261021-double11.9.md)。历史发布说明保留其原始测试范围。
文档审阅后如发生修改，重新提交、构建并自检，确保包内说明与最终源码一致。发布时将 CHANGELOG 和随包说明中的「候选发布、待审阅」状态改为实际发布状态。

## 1. 提交前测试与隐私检查

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py modules scripts tests
git add .gitignore .gitattributes README.md ATTRIBUTION.md CHANGELOG.md PORTABLE_README.md RELEASING.md
git add main.py build.spec start.bat version.json requirements.txt requirements-build.txt requirements-windows.lock
git add modules configs web scripts tests docs .github
python scripts/check_public_files.py
git diff --cached --check
git diff --cached --stat
git commit -m "Prepare Double 11 portable release"
```

`check_public_files.py` 读取实际 Git 索引，按允许目录、扩展名、文件大小和敏感内容检查。
本地设备标识可通过仓库外的私有文件额外检查，见 [PRIVACY.md](docs/PRIVACY.md)。
版本保存在 `version.json`；构建器要求工作区干净，并将 HEAD 提交号写进构建清单。

## 2. 创建独立锁定环境

在 Windows x64 / Python 3.13 上：

```powershell
python -m venv build/release-env
.\build\release-env\Scripts\python.exe -m pip install -r requirements-windows.lock
.\build\release-env\Scripts\python.exe scripts/fetch_platform_tools.py
.\build\release-env\Scripts\python.exe scripts/package_windows.py --adb-dir build/vendor/platform-tools
```

也可用 `uv venv` 与 `uv pip sync`，从同一锁文件创建全新环境。
已有官方 Android platform-tools 时，可将其目录传给 `--adb-dir`。
HDC 默认不在 Android 便携包中；需要同时包含合法取得的 HDC 时，可加 `--hdc-dir HDC目录`。

构建脚本会：

1. 校验 Git 索引与工作区，记录源码提交号。
2. 运行回归测试，使用独立的新工作目录执行 PyInstaller。
3. 收集当前代码可达依赖、明确声明的网页和配置、模型、ADB 与第三方许可。
4. 清除测试进程 PATH 中的 Python / ADB，执行不连接手机的离线自检。
5. 从新输出目录生成 ZIP 和 `.zip.sha256`，附 `build-manifest.json` 与 `self-test.json`。

`runtime/`、开发虚拟环境、截图、旧 exe、日志和设备信息不参与打包。
输出为 `dist/MiaoTask-版本-windows-x64.zip`；中间目录为 `dist/windows-构建时间/MiaoTask/`。
应将 ZIP 完整解压到新目录测试，勿把新 exe 单独复制到旧运行库中。

## 3. GitHub 发布

将提交推送到仓库后，创建与 `version.json` 一致的版本标签。
Actions 会使用锁定环境重新构建、审计和自检，核对标签与版本、对应 Release 文档，随后创建带附件的 Release 草稿。
手动发布已验证的本地资产时，先检查是否已有同标签的草稿；附件应与发布提交一致。
工作流检测到同标签 Release 已存在时保留现有资产，避免覆盖已审阅的便携包。
草稿正文直接读取仓库中对应的 Release 文档，不以自动生成的提交摘要替换已审阅内容。创建草稿和正式公开发布是两个步骤；维护者确认前不公开。

Release 说明至少包含：

* 来源项目、上游基准和具体改造范围。
* 相比原版新增的任务流程、控制台、核验和失败处理设计。
* 平台范围、解压使用与升级方法。
* 测试及离线自检范围；源码提交与依赖信息可在包内构建清单查看。SHA256 可作为可选附件，无需占用主要说明篇幅。

首个公开版本的说明见 [docs/RELEASE-v20261018-double11.3.md](docs/RELEASE-v20261018-double11.3.md)。
保留 [ATTRIBUTION.md](ATTRIBUTION.md) 和便携包中的 `licenses/`。
