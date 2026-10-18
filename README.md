# 喵任务 · 淘宝双11任务助手

基于 [MonsterNone/tmall-miao](https://github.com/MonsterNone/tmall-miao) 的 `next` 分支改造，感谢原作者及贡献者。
本仓库独立维护双11任务执行器、本地网页控制台和便携包；来源基准及权利说明见 [ATTRIBUTION.md](ATTRIBUTION.md)。

当前适配：**淘金币双11狂享20亿 → 赚能量**。支持浏览、搜索、部分跨应用访问、闪购内部跳转与累计奖励领取。

## 下载使用

从 [Releases](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11/releases/latest) 下载 Windows x64 ZIP，
**完整解压**后双击 `MiaoTask.exe`。无需在电脑上安装 Python、ADB 或 OCR 模型，`_internal/` 必须与 exe 放在一起。

1. 手机保持解锁、开启 USB 调试，连接电脑并在手机上允许调试。部分手机需要厂商 USB 驱动。
2. 在手机打开「淘宝 → 领淘金币 → 赚能量」。
3. 网页连接设备，选择「从手机当前页面开始」，点击「识别任务」。
4. 检查任务分类后开始执行；可以暂停、继续或停止。

默认控制台地址为 `http://127.0.0.1:8765`。端口被其他程序占用时自动选择空闲端口。
升级前先在旧网页底部点击「退出助手」，再启动新版，刷新网页并查看页脚版本。
仅关闭浏览器不会停止后台助手。详见 [便携版说明](PORTABLE_README.md)。

当前默认包面向 **Windows x64 + Android**，包含 ADB。HarmonyOS 驱动接口保留，HDC 需另行提供，尚未进行鸿蒙实机验证。

## 相比原版的主要改造

| 方面 | 本版本的实现 |
| --- | --- |
| 活动 | 将原618流程改造为双11淘金币任务识别与执行；清除未接入的旧京东、618模块 |
| 操作 | 默认本地 HTML 控制台，显示任务、进度、手机画面与日志；保留 CLI |
| 识别 | UI 树优先，无法读取时使用本地 RapidOCR；按行位置配对标题、按钮和次数 |
| 浏览 | 读取任务时长，额外停留并持续上下滚动，发现完成提示可提前返回 |
| 搜索 | 原生输入框填字、明确点击搜索、确认结果页后计时，不安装或切换输入法 |
| 跨应用 | 保存原淘宝应用，恢复任务栈并检查是否回到能量列表 |
| 失败与新任务 | 根据实际反馈记录本机跳过原因；有限重试；返回后重新识别替换出的任务 |
| 奖励 | 按对应累计奖励卡的「已领取」状态核验 |
| 分发 | 锁定构建环境，打包离线模型与运行库，提供源码提交号、自检与 SHA256 |

原版已提供 Android / HarmonyOS 适配及打包基础，本版本在此基础上改造。
完整差异与模块设计见 [架构文档](docs/ARCHITECTURE.md)，版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 执行方式与边界

* 15秒浏览默认增加10秒和2秒缓冲，即计划停留约27秒，期间持续上下滚动。缓冲、尝试次数及每轮上限可在网页调整。
* 每次返回核验任务次数、完成状态或页面反馈；控件树保留旧任务时用本地 OCR 复查，避免点击已消失的行。
* 跨应用任务先正常尝试，确认安装页、跳转不可用或任务未核验后，结合该手机安装状态标记跳过。同一设备会话再次开始不重复尝试；重新连接可清除标记。
* 新用户和新启动的助手不继承其他手机的结论。安装已确认缺失的应用后，重新识别会刷新检测。
* 闪购「点击去逛」入口只进行内部浏览与返回。支付宝红包等明确标注「跳转得奖励」的任务只跳转浏览，不参与内部抽奖或游戏。
* 游戏、拉人、邀请、助力与金币考试直接跳过。实际支付、下单、充值、关注、收藏、答题、多商品交互等留待手动处理。
* 同一任务同一进度默认最多尝试2次；页面等待、返回层数、列表滚动和每轮执行次数均有上限。
* 遇到验证、登录或支付页面会停止提示。处理后回到任务列表，再开始一轮。

截图预览为定期截图，非实时视频。截图与 OCR 在本机处理；公共仓库和发布包不包含设备记录或开发者的跳过名单。
日志和导出记录可能包含设备信息，请自行保管。数据位置与提交边界见 [PRIVACY.md](docs/PRIVACY.md)。
活动页面可能随账号、日期及应用版本变化，暂不承诺所有任务均可完成。

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
详细命令与清洁构建步骤见 [RELEASING.md](RELEASING.md)。
