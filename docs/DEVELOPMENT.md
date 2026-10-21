# 开发与设计

## 源码运行

使用 Python 3.13，准备可用的 Android ADB；手机保持解锁并允许调试。HarmonyOS 驱动接口需要另行提供 HDC，当前便携包不包含 HDC。

```powershell
git clone https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11.git
cd tmall-miao-double11
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Windows 也可用 `start.bat`。网页无需 npm 或额外构建步骤。命令行参数示例：

```powershell
# 自动进入活动，限制本轮次数
.\.venv\Scripts\python.exe main.py --cli --auto-open --max-tasks 2
# 仅识别当前页面
.\.venv\Scripts\python.exe main.py --cli --scan
# 指定实际发现的 Android 用户空间（数字仅为示例）
.\.venv\Scripts\python.exe main.py --cli --instance com.taobao.taobao@999 --auto-open
# 修改网页端口
.\.venv\Scripts\python.exe main.py --port 8766 --no-browser
```

`--serial` 指定设备，`--config` 加载公共配置覆盖项，完整参数见 `main.py --help`。默认活动规则在 `configs/double11.json`，不保存个人设备信息。

## 模块职责

| 路径 | 职责 |
| --- | --- |
| `main.py` | 网页 / CLI 入口与运行时初始化 |
| `modules/campaign.py` | 任务选择、浏览、搜索、返回、核验和有限重试 |
| `modules/task_model.py`、`screen_reader.py` | 任务解析及统一 UI / 本地 OCR 观察 |
| `modules/device_adapter.py`、`adb_transport.py` | 驱动、设备发现、原生输入与连接兼容 |
| `modules/app_instances.py` | 包名和 Android 用户空间的实例身份 |
| `modules/daily_state.py` | 当日增量统计、不可用事实与诊断导出 |
| `modules/control_panel.py` | 本地 HTTP、状态快照及单设备工作线程 |
| `modules/browse_gestures.py` | 范围内变化的滚动参数 |
| `modules/windows_tray.py`、`branding.py` | Windows 托盘与统一图标资源 |
| `web/` | HTML、CSS 和 JavaScript 控制台 |
| `scripts/`、`tests/` | 构建维护工具与回归用例 |

## 执行约束

流程为「观察 → 解析 → 执行 → 返回 → 核验 → 重读」。任务标题、进度和按钮配对后才操作；UI 树不可靠时使用本地 OCR 复核前台。搜索优先原生 `set_text`，重新定位右侧提交按钮，必要时回车；确认结果页后才浏览，不安装或切换输入法。

任务完成依据为进度、完成标签或对应奖励状态；无法确认时不计成功。新替换任务拥有独立身份。任务尝试、返回层数、等待、列表滚动和整轮执行均有上限。恢复优先逐层 Back，每次重读并检查认证和实例；到达返回上限后 Home，确认桌面才使用共享的一次冷重启额度。初次启动与异常恢复分别计数；认证等人工处理状态独立停止。

实例由包名与 Android 用户空间共同确定。启动、停止和恢复限定用户，操作前核对焦点窗口。启动转场未确认前台时，允许再次唤起同一实例一次，不重复强停；仍无法确认或操作途中身份不符时停止。队列串行执行，记录按实例隔离，不读取账号标识。

HTTP 仅绑定本机，写操作校验 Host、Origin 与会话令牌。一个工作线程控制设备，预览通过 I/O 锁读取；新截图按序替换，短时缓存遇到操作或前台变化失效，失败现场使用新帧。无网页访问时停止额外预览，Windows 托盘负责重新打开和退出。

## 数据与接口

源码数据默认位于 `runtime/`，便携版位于 `%LOCALAPPDATA%\MiaoTask`；`MIAO_DATA_DIR` 可覆盖位置。主应用使用 `daily/YYYY-MM-DD/<device_hash>/`，其他实例在其下的 `instances/<instance_hash>/` 独立记录。

| 数据 | 含义 |
| --- | --- |
| `state.json` | 当日累计、计数水位与不可用任务 |
| `events.jsonl` | 阶段变化与日志 |
| `failures/` | 失败说明和可取得的原始截图 |
| API `stats` / `daily.stats` | 本轮 / 当前实例今日累计 |
| API `image_sequence` | 新截图序号 |
| GET `/api/diagnostics` | 当前设备、所选实例当天的本地诊断 ZIP |

接口和配置以当前代码为准。结构调整应独立提出迁移方案，避免让活动逻辑依赖网页布局或具体驱动细节。参与修改见[贡献规范](CONTRIBUTING.md)，验证、构建和发布见[测试与打包](BUILDING.md)。
