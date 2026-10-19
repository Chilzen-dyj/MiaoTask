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

Windows 可使用 `start.bat`。自动打开活动会优先寻找首页可见入口，找不到时尝试搜索活动词。
分身应用建议手动进入活动后执行；恢复能力取决于驱动暴露的包名及用户上下文，尚未验证分身场景。

```powershell
# 只识别任务，自动选择已连接手机
python main.py --cli --scan

# 指定手机并限制本轮次数
python main.py --cli --serial YOUR_SERIAL --max-tasks 5

# 鸿蒙、自动进入活动、关闭跨应用访问
python main.py --cli --device harmony --auto-open --no-cross-app

# 修改控制台端口
python main.py --port 8766 --no-browser
```

默认配置见 `configs/double11.json`。`--config 文件路径` 可加载覆盖项，设备信息无需写进公共配置。
网页设置在当前服务期间保留。暂停时间不计入浏览时长；停止后保留手机现场。

## 测试、构建与发布

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py modules scripts tests
python scripts/check_public_files.py
```

测试使用模拟设备，不连接真实手机。覆盖任务解析、搜索、原生输入、动态任务、跨应用恢复、有限重试、
累计奖励、HTTP 校验和公共文件边界。代表性 Android 任务及便携包已实机验证。

构建器从已提交的干净源码生成全新目录，执行离线 OCR、内置 ADB、本地网页、浏览器请求头、重复启动及退出自检。
GitHub Actions 可手动构建，版本标签会触发构建并生成 Release 草稿；正式发布可附加经验证的 ZIP 和校验文件。
详细命令与清洁构建步骤见 [RELEASING.md](../RELEASING.md)。
