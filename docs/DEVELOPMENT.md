# 源码运行与二次开发

面向开发者；下载便携版请先看 [项目首页](../README.md)。

## 源码运行

开发与发布验证环境为 Python 3.13。需要 Android ADB 或 HarmonyOS HDC，并已允许手机调试。

```powershell
git clone https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11.git
cd tmall-miao-double11
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Windows 可使用 `start.bat`。网页默认自动定位淘宝活动，一键开始会先重新读取任务；普通返回失效时可重开淘宝，再寻找首页活动入口，找不到时尝试搜索活动词。
v9 支持按包名与 Android 用户空间选择分身；默认关闭，需要时在网页展开「应用分身」，可调整顺序串行执行。当前已有红米主应用与用户空间 999 分身的代表性实测，其他厂商与第三方容器需另行验证，见 [v9 验证记录](PREVIEW-v9.md)。

```powershell
# 只识别任务，自动选择已连接手机
python main.py --cli --scan

# 指定手机并限制本轮次数
python main.py --cli --serial YOUR_SERIAL --max-tasks 5

# 指定 Android 淘宝分身（用户空间以手机实际发现结果为准）
python main.py --cli --instance com.taobao.taobao@999 --auto-open --max-tasks 2

# 鸿蒙、自动进入活动、关闭跨应用访问
python main.py --cli --device harmony --auto-open --no-cross-app

# 修改控制台端口
python main.py --port 8766 --no-browser
```

默认配置见 `configs/double11.json`。`--config 文件路径` 可加载覆盖项，设备信息无需写进公共配置。
网页设置在当前服务期间保留。暂停时间不计入浏览时长；停止后保留手机现场。
CLI 仍保留 `--scan` 供开发调试，网页已将识别并入开始按钮。详细路径和数据结构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 本地数据与诊断

源码模式写入 `runtime/`，便携模式写入 `%LOCALAPPDATA%\MiaoTask`，可由 `MIAO_DATA_DIR` 覆盖。
每台设备以驱动类型和实际标识计算哈希键，按本机自然日存储 `daily/YYYY-MM-DD/<device_key>/`。
主应用保留旧路径；其他实例在其下使用 `instances/<instance_hash>/`，分别累计与导出，避免共用缺失应用事实。
当天 `state.json` 保存增量累计统计及不可用任务，`events.jsonl` 保存日志；`failures/` 保存失败 JSON 和可取得的截图。
重新扫描不会累计同一批执行数，同日重开会延续记录，跨日另建一份并重新判断应用可用性。

控制台状态的 `stats` 表示本轮，`daily.stats` 表示该设备、所选实例当天累计；`image_sequence` 标记新预览。
GET `/api/diagnostics` 下载当前设备、所选实例当天的诊断 ZIP。文字设备标识隐藏，截图不自动脱敏；样例测试必须使用模拟数据，不将真实记录提交仓库。
同一设备、同一实例内切换账号仍共用当天统计；不同分身独立。见 [隐私说明](PRIVACY.md)。

Android 实例操作显式传入 `--user`，具体命令见 [Android ADB 官方文档](https://developer.android.com/tools/adb)。前台身份来自当前焦点窗口的包名和用户字段；身份无法核定时不继续操作淘宝。Windows 托盘使用系统 API，无额外 GUI 依赖；关闭浏览器后停止额外预览截图，托盘退出会停止任务并关闭 HTTP 服务。

## 测试、构建与发布

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py modules scripts tests
python scripts/check_public_files.py
```

测试使用模拟设备，不连接真实手机。覆盖任务解析、搜索、原生输入、动态任务、跨应用恢复、有限重试、
累计奖励、设备日统计与跨日重启、诊断导出、HTTP 校验和公共文件边界。
前版代表性 Android 浏览、搜索及累计领奖已实机验证；本轮新增路径的验证范围以 [CHANGELOG](../CHANGELOG.md) 为准。

构建器从已提交的干净源码生成全新目录，执行离线 OCR、内置 ADB、本地网页、浏览器请求头、重复启动及退出自检。
GitHub Actions 可手动构建，版本标签会触发构建并生成 Release 草稿；正式发布可附加经验证的 ZIP 和校验文件。
详细命令与清洁构建步骤见 [RELEASING.md](../RELEASING.md)。
