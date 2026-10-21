# 架构与扩展

当前重构基线为 0.0.9 的修复提交 `1846fdf`。0.1.0 保留既有任务行为，尚未发布；没有新增已适配的平台。无线调试实验位于独立分支，不改变活动执行策略。

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

## 屏幕与模拟器接口

Android 无线接入由 `core/device/wifi.py` 负责，提供 mDNS 广播读取、TLS 配对和指定地址连接。配对码通过子进程标准输入发送，不进入命令行、状态快照或持久化配置。配对与连接共享服务的单设备工作线程，运行任务时不能切换连接；连接后仍使用原 `DeviceAdapter`、真实设备标识、用户空间锁和日累计机制。前端向导位于 `frontend/js/components/wifi-connect.js`，不包含活动业务。

| 接口 | 当前行为 | 后续接入位置 |
| --- | --- | --- |
| `DeviceBackend`、`DriverFactory` | 描述现有驱动能力，现有适配器继续工作 | 新设备后端与工厂注册 |
| `EndpointProvider`、`DeviceEndpoint` | 明确区分设备地址与接入方式 | 厂商实例列表、远程设备发现 |
| `ConfiguredEmulatorProvider` | 接受实际配置的 ADB TCP 地址，不猜端口、不启动模拟器 | MuMu 等厂商配置读取器 |
| `DisplayGeometry` | 描述尺寸、方向、安全边距和挖孔区域 | 异形屏元数据适配 |
| `ImageProcessor`、`CoordinateTransform` | 默认原图与恒等映射；保留 0.0.9 的 OCR 内部宽度上限 | 裁剪、缩放后的识别框回映 |

模拟器当前可沿用网页地址输入和既有 ADB TCP 通道；本轮未接入或操作本机 MuMu，也未新增自动发现按钮。旋转、安全区域及挖孔元数据尚不改变默认点击或滑动。自定义预处理器必须把识别框映射回设备坐标，缓存键也要反映处理策略；预览和失败现场仍保留完整原图。

## HTTP 与前端

旧 `/api/state`、`run`、`scan`、暂停、继续、停止、配置、实例、预览、诊断及退出接口保留。新增 `/api/apps` 和 `/api/select_activity`；运行中禁止切换活动或实例。

`/api/session/status`、`/api/session/start|pause|resume|stop` 和 `/api/preview` 为既有接口的别名。`/api/stats`、`/api/tasks` 返回当前选择的快照，尚不提供任意日期的历史查询或跨设备聚合。`POST /api/export` 导出当前诊断，仍需令牌与来源校验。

前端保留原有操作布局、默认收起的分身与设置；活动选择作为收起的管理控件。静态资源使用固定白名单，旧 `/app.js`、`/style.css` 路径继续可用。暂不引入前端框架或修改并发设备限制。

本轮本地验证方法和覆盖限制集中在 [BUILDING.md](BUILDING.md)。
