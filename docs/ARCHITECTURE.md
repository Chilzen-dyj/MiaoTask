# 架构与扩展

当前重构基线为 0.0.9 的修复提交 `1846fdf`。0.1.0 保留既有任务行为，尚未发布；没有新增已适配的平台。无线接入、不同屏幕与多设备能力在本地开发分支验证。

## 目录与边界

```text
MiaoTask/
├── main.py                       # 稳定启动入口
├── backend/
│   ├── main.py                   # CLI 与装配
│   ├── bootstrap.py              # 开发集成入口
│   ├── core/
│   │   ├── config/               # 默认配置、分层加载与校验
│   │   ├── device/               # 驱动、实例、截图、OCR、坐标与接入契约
│   │   ├── execution/            # 会话、循环、返回预算、重试、守卫
│   │   ├── storage/              # 日累计、命名空间、旧记录接续
│   │   ├── service/              # HTTP、来源校验、静态路由、预览与托盘
│   │   ├── models.py             # 文本、坐标和任务数据契约
│   │   └── registry.py           # 应用与活动发现
│   └── app/
│       ├── common/               # 注入规则的任务行配对与跳转可用性
│       └── taobao/
│           ├── manifest.py       # 应用包名、用户空间与旧记录策略
│           ├── configs/base.json
│           ├── utils/            # 搜索与任务分类规则
│           └── activities/double11/
│               ├── manifest.py   # 注册元数据
│               ├── config.json   # 活动配置
│               ├── activity.py   # 策略组合
│               ├── entry.py      # 入口与赚能量菜单
│               ├── tasks.py      # 解析规则装配
│               ├── actions.py    # 执行策略
│               └── verify.py     # 核验策略
├── frontend/                     # 原生 HTML/CSS/JS，无 npm 构建
├── shared/                       # 公共资源约定
├── scripts/                      # 构建、审计与验证入口
├── tests/                        # 原有回归、架构契约与合成对照数据
├── docs/                         # 项目文档
├── build/                        # 本机构建环境、工具与临时输出，默认忽略
├── .venv/                        # 本地开发环境，默认忽略
└── dist/                         # 本地便携包，默认忽略
```

`core` 不导入具体平台包，也不包含平台包名或活动名。注册表读取本地 manifest，再按声明的工厂装配活动。文本几何放在 core，避免读屏层反向依赖业务层。平台之间通过 `app/common` 共享业务算法。

任务行配对、状态机和恢复流程按职责拆分，保留原有分支与默认值。活动入口和核验存在较多当前页面特征，继续留在活动包；没有强行把这些判断推广成所有平台的默认规则。

## 注册一个活动

平台目录包含 `manifest.py` 和 `configs/base.json`，活动目录包含 manifest、config 及活动实现。以现有 `taobao/activities/double11` 为实际参考。

```python
from backend.core.registry import ActivityMeta

META = ActivityMeta(
    app='sample', id='daily-tasks', label='每日任务',
    factory='backend.app.sample.activities.daily_tasks.activity:DailyTasksActivity',
    config='config.json', device_types=('uiautomator2',),
)
```

公开活动 ID 可以带连字符，Python 包目录使用 `daily_tasks` 等合法标识符；两者由 `factory` 显式关联。无需依赖 ID 推导 import 路径。

活动继承 `core.execution.activity.Activity`。会话对象持有设备、配置、控制句柄、记录和读屏器；实现 `default_config`、`parse_tasks`、`is_task_list`、`execute`、`verify`，并提供入口和恢复策略。原有 `ensure_list(auto_open)`、`recover()`、`scan()`、`run()` 方法保留。可以复用 `Navigator`，也可覆盖入口与恢复方法；不同页面不应直接复制淘宝坐标。

`run()` 调用 setup、通用循环及 finally 中的 teardown。通用循环负责候选选择、重试、不可用事实、进度核验与统计；认证和身份核对失败始终中断。当前默认导航器还需要活动提供主页、活动页、菜单、列表及官方入口的判定钩子，接口见现有 `EntryPolicy`；没有这些页面结构的活动应提供自己的有限恢复策略。

`TaskRules` 注入按钮、进度、描述和累计奖励词表及分类函数，共用行配对算法；特殊平台可直接替换解析函数。新增活动后重启服务即可被注册表发现，前端「应用与活动」读取同一目录。未安装活动包时，HTTP 和离线自检仍可运行，执行入口禁用。

测试中会临时注册第二个合成活动，验证框架无需改代码即可运行另一平台。这只证明扩展契约可用，不代表该示例已适配真实 App。

## 配置与数据

配置顺序为 `core/config/defaults.json → 平台 base.json → 活动 config.json → 用户覆盖`，JSON 与 YAML 都支持。`load_resolved` 返回只读快照及字段来源；运行接口保留字典配置，原有 JSON 覆盖文件和网页字段仍可使用。

记录路径为：

```text
runtime/apps/<app>/activities/<activity>/daily/<date>/<device_hash>/instances/<instance_hash>/
```

便携版的数据根仍为 `%LOCALAPPDATA%/MiaoTask`，`MIAO_DATA_DIR` 仍可覆盖。设备、应用、活动、实例、日期分别隔离。只有明确声明 `legacy_storage=True` 的原活动会接续旧 `daily/` 记录：检查身份后复制状态、事件和失败现场，保留旧文件，首次完成后不再导入，避免重复累计。单独调用 `DailyState` 且不传命名空间时仍可读取旧布局。

不把应用安装状态跨实例共享。Android 用户空间的安装情况可能不同；当天不可用事实继续随各活动、实例保存，次日重新判断。

## 设备、屏幕与模拟器

`core/device/wifi.py` 负责 mDNS 广播读取、TLS 配对与指定地址连接。配对码走子进程标准输入，不进入命令行、快照或配置；连接后继续使用原驱动、包名与用户空间限制。

`emulators.py` 只调用已安装 MuMu 的只读实例查询，读取运行中实例的实际 ADB 地址，不猜端口、不启动或修改模拟器。`inventory.py` 对已授权连接读取设备身份，去重 USB、TCP 与 mDNS 别名。Android 优先使用真实序列号，无序列属性的模拟器使用 Android ID；无法核定身份时拒绝多设备租约，避免重复控制。

截图、读屏和输入都使用设备坐标。`ScreenReader` 随观察刷新宽高，过滤其他应用的背景窗口，横屏大图采用重叠区域 OCR，并把结果移回原图；竖屏保留既有宽度处理。自定义 `ImageProcessor` 的裁剪、缩放结果必须通过 `CoordinateTransform` 回映，缓存键也需反映策略。

`displays.py` 从 Android 焦点取得逻辑显示屏，通过系统的主显示设备 uniqueId 解析采集 ID；MuMu 的逻辑 ID、HWC 端口、ADB 截图序号不能互换。输入使用相同逻辑显示屏。映射失败不回退主屏，热插拔或显示变化会刷新映射。默认主屏仍使用原截图与点击路径。

`DisplayGeometry` 描述系统报告的尺寸、安全边距及挖孔区域，约束点击与滚动；元数据缺失时保留全屏坐标。画面完全不可读取时停止输入，不据隐藏控件继续点击。登录、授权和支付仍由本人处理。未知机型的窗口布局、自由窗口和折叠屏姿态需要相应实测，不能仅以分辨率比例推断支持。

## 多设备与服务

一个 `DeviceHub` 管理最多 8 个 `Controller`，一个本地 HTTP 服务和一套静态页面。每个控制器拥有独立工作线程、停止/暂停句柄、预览缓存、活动、实例队列及日记录。各设备线程并行运行，同一台设备内的应用分身仍串行。

| 状态 | 所有者 | 隔离方式 |
| --- | --- | --- |
| 连接、执行与操作锁 | 设备控制器 / 适配器 | 每台一套，不共享“当前设备” |
| 物理设备租约 | DeviceHub | 序列号或 Android ID，连接别名不可重复占用 |
| 活动、实例与配置 | 各控制器 | 执行期间禁止切换，批量配置逐台校验 |
| 日累计与失败现场 | DailyState | 设备、应用、活动、实例、日期命名空间 |
| OCR 推理状态 | 设备执行上下文 | 每个工作区独立引擎，缓存数量有上限 |
| 日志 | `core/context.py` 上下文 | 工作线程明确归属，不能写入其他设备的记录 |
| 当前展示 | 浏览器页面 | 只影响查询目标，不改变后台执行目标 |

开始连接时先核定物理身份、取得独占租约，再初始化自动化驱动。重复别名连接失败，原设备继续工作。移除需等待设备操作结束；已移除控制器拒绝迟到的写操作。退出一次停止全部控制器，并在统一时间预算内等待和保存。

批量启动将命令交给各设备线程，不等待上一台执行结束。部分未连接、忙碌或配置不兼容的设备各自返回失败，其余继续；停止、认证和异常默认仅影响本设备。批量复制任务与滚动配置，不复制账号或分身选择。

## HTTP 与前端

既有 `/api/state`、`run`、`scan`、暂停、继续、停止、配置、实例、预览、诊断等路径保留，不带设备参数时服务默认工作区。多设备请求通过 `?device=<workspace_id>` 明确目标，未知 ID 必须拒绝；浏览器切换时丢弃旧请求和旧预览结果，不能将迟到响应显示成新设备状态。

* `GET /api/workspaces`：工作区概要；`POST /api/workspaces`：添加。
* `POST /api/workspaces/remove`：移除空闲工作区；`/api/workspaces/batch`：向显式设备列表提交并行操作。
* `GET /api/inventory`、`/api/emulators`：已连接设备去重与 MuMu 实例发现。
* `POST /api/wifi/pair|connect`：当前工作区无线配对与连接；`/api/open_app` 仅唤醒所选实例。
* `/api/session/status|start|pause|resume|stop`、`/api/preview` 为既有别名，`/api/stats` 和 `/api/tasks` 返回指定工作区快照。
* `/api/shutdown` 退出整个服务；所有写操作仍校验 Host、Origin 与令牌。工作区 ID 不构成授权凭据。

前端 `device-manager.js` 管理设备标签和批量选择，`api.js` 统一附加设备 ID；任务判断和坐标留在后端。只为当前展示设备提供额外预览；后台任务按自己的观察周期取图。标签切换不新开端口或浏览器页面。旧静态路径保留，所有资源由固定白名单提供。

验证、构建与覆盖边界集中在 [BUILDING](BUILDING.md)，贡献前先读本架构，再读 [CONTRIBUTING](CONTRIBUTING.md)。
