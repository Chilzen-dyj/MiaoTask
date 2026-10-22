# 本机构建目录

此目录保留构建环境和临时文件，除本说明外不提交到 Git。

* `release-env/`：需要隔离发布环境时，按锁文件创建的 Python 环境。
* `vendor/platform-tools/`：构建所需 ADB、DLL 和 NOTICE；开发启动也可使用此副本。
* `pyinstaller-*/`：每次全新构建的分析与临时输出。

PyInstaller 配置为根目录 `build.spec`，入口为 `scripts/package_windows.py`；输出到 `dist/`。具体步骤见 [测试与打包](../docs/BUILDING.md)。不要把开发环境、设备记录或旧版本文件复制进便携包。
