# 测试、打包与发布

## 工具入口

所有工具随源码一并维护在 GitHub。Windows x64 / Python 3.13 为便携包构建环境；从 Git 克隆仓库并保留干净提交，构建器会记录源码提交号。

| 工具 | 用途 |
| --- | --- |
| `scripts/check_public_files.py` | 审计实际 Git 索引中的公开文件和敏感信息 |
| `scripts/fetch_platform_tools.py` | 获取官方 Android platform-tools |
| `scripts/package_windows.py`、`build.spec` | 独立目录构建 exe、运行自检并生成 ZIP |
| `scripts/smoke_packaged.py` | 对解压后的 exe 检查运行环境、网页和退出 |
| `scripts/release_notes.py` | 从统一发布记录提取指定版本正文 |
| `scripts/export_icons.py` | 从统一母版导出 PNG / ICO |
| `.github/workflows/release.yml` | 锁定环境构建、保存附件和创建 Release 草稿 |

## 验证修改

在开发环境运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m compileall -q main.py modules scripts tests
node --check web/app.js
```

Python 用例使用模拟设备，覆盖解析、任务更新、搜索提交、返回核验、重试、累计领奖、实例隔离、日记录、连接与公开文件边界。涉及界面脚本时再执行 Node 语法检查，并在浏览器检查相应交互。

改变任务行为、配置字段或数据格式时，应验证原配置仍可加载、旧记录仍可延续，并补充对应回归。导航、分身或驱动修改宜补充真机复现和停止/恢复检查；不消耗无关任务，也不将未核验的访问计作成功。PR 中写明命令、结果与覆盖限制，要求见[贡献规范](CONTRIBUTING.md)。

提交前明确选择要公开的文件，再运行：

```powershell
.\.venv\Scripts\python.exe scripts/check_public_files.py
git diff --cached --check
git diff --cached --stat
```

审计读取暂存内容；仅修改工作区而未暂存的新文件不会纳入检查。本地已知设备标识可放在仓库外的 JSON 字符串数组，通过 `--forbid-file 文件路径` 额外检查。截图的视觉脱敏仍需人工核对。

## 构建 Windows 便携包

使用独立的锁定环境，避免混入开发环境的临时依赖：

```powershell
python -m venv build/release-env
.\build\release-env\Scripts\python.exe -m pip install -r requirements-windows.lock
.\build\release-env\Scripts\python.exe scripts/fetch_platform_tools.py
# 审阅并提交源码，确认 git status 无待提交修改后构建
.\build\release-env\Scripts\python.exe scripts/package_windows.py --adb-dir build/vendor/platform-tools
```

已有官方 platform-tools 可传入对应目录；必须包含 adb.exe、必要 DLL 和 NOTICE.txt。需要 HDC 时可传 `--hdc-dir`，默认包只包含 Android ADB。从源码 ZIP 开始构建时需先建立 Git 仓库并提交；不需要构建的用户直接下载便携 ZIP。

构建器先审计、运行用例，再从新目录执行 PyInstaller，包含当前入口可达代码、网页、公共配置、离线 OCR、ADB 和第三方许可。不会整体压缩项目目录或携带开发虚拟环境、个人日志、设备配置、旧 exe 和手机截图。

输出为 `dist/<version>-windows-x64.zip`。包内包含：

* `MiaoTask.exe` 和 `_internal/` 运行环境。
* `README.md`、`docs/` 使用、风险和发布说明，以及 `licenses/`。
* `build-manifest.json` 的源码提交与依赖信息，`self-test.json` 的离线自检结果。

## 检查实际 ZIP

完整解压到新目录，不将新 exe 复制到旧运行库中：

```powershell
$releaseVersion = (Get-Content version.json -Raw | ConvertFrom-Json).version
$verifyFolder = "dist/verify-$releaseVersion"
if (Test-Path -LiteralPath $verifyFolder) { throw '请改用新的验证目录' }
Expand-Archive -LiteralPath "dist/$releaseVersion-windows-x64.zip" -DestinationPath $verifyFolder
.\build\release-env\Scripts\python.exe scripts/smoke_packaged.py "$verifyFolder/MiaoTask/MiaoTask.exe"
```

自检会从 PATH 中移除 Python / ADB，检查内置 ADB、离线 OCR、图标、HTTP、浏览器来源头、重复启动和退出，不操作手机。另检查随包文档和构建清单与发布提交一致；升级、托盘和涉及手机的变更按影响范围补充检查。SHA256 为可选完整性附件。

## 版本规则

版本与标签使用 `MiaoTask-v0.0.9` 形式，去掉日期和活动限定；两个版本字段保持一致。功能优化递增末位（如 `0.0.9 → 0.0.10`），架构升级或扩展应用递增中位（如 `0.0.x → 0.1.0`）。下一次 `0.1.0` 只调整架构，保持当前功能和配置兼容；暂不规划 `1.0.0` 定稿版本。历史标签保留。

## 发布

1. 在 `version.json` 更新版本，在 [RELEASES.md](RELEASES.md) 顶部添加完全同名的 `## 版本号` 小节，集中维护用户可见变化。
2. 审阅源码、文档和附件，提交最终修改，从该干净提交重新构建。文档修改后不要继续使用旧包。
3. 维护者确认后推送源码，再推送与版本一致的标签。手动运行 Actions 只保存构建附件；标签触发构建并创建 Release 草稿。
4. 工作流通过 `scripts/release_notes.py` 提取已审阅的小节；不会用自动提交摘要替代正文。检查草稿与 ZIP 后再公开。

已有同标签 Release 时工作流保留其附件，不覆盖已审阅的资产。发布状态以 GitHub Releases 为准；源码仓库不跟踪 exe 和 ZIP。
