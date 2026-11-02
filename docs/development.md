# Python 2.7 开发规范

网易基岩版 ModSDK 运行在 Python 2.7 环境中。本仓库的业务脚本与检查工具统一使用 Python 2.7 编写，开发环境使用的 SDK 补全包版本与目标客户端实测版本分开记录。

## 本地环境配置

| 项目 | 配置值 | 检查命令 |
| --- | --- | --- |
| Python 解释器 | `2.7.18`（[`.python-version`](../.python-version)） | `python --version` |
| ModSDK 补全包 | `mc-netease-sdk==3.9.0.79920`（[`requirements-dev.txt`](../requirements-dev.txt)） | `python -m pip show mc-netease-sdk` |
| 文本与缩进格式 | UTF-8、LF、4 空格缩进（[`.editorconfig`](../.editorconfig)） | `git diff --check` |
| 静态语法检查 | 标准库脚本 [`tools/check.py`](../tools/check.py) | `python tools/check.py` |

在 IDE 中将项目解释器指定为 Python 2.7.18。`.python-version` 供版本管理工具读取，终端内直接执行的 `python` 仍由系统 `PATH` 决定。安装代码补全依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

`mc-netease-sdk` 仅提供 `RegisterSystem`、`GetEngineCompFactory` 等函数的类型与签名声明，不包含游戏引擎运行时逻辑。PyPI 上已有更新的 `3.10.0.81573` 版本（见 [PyPI 发布页](https://pypi.org/project/mc-netease-sdk/3.9.0.79920/)），当前固定 `3.9.0.79920` 用于锁定初始开发环境，阶段 0 确定目标客户端版本后再同步升级。

## 目录结构

当前仓库包含文档与检查工具：

```text
AnvilCraftNeteaseBedrock/
├── .editorconfig
├── .gitattributes
├── .gitignore
├── .python-version
├── ASSETS_LICENSE
├── LICENSE
├── NOTICE.md
├── README.en_US.md
├── README.md
├── requirements-dev.txt
├── docs/
│   ├── README.md
│   ├── development.md
│   ├── development-plan.md
│   ├── migration-research.md
│   ├── source-inventory.json
│   └── sources.md
└── tools/
    └── check.py
```

进入阶段 0 并在 MC Studio 中创建可加载工程时，按以下结构建立行为包、资源包与测试目录：

| 目录或文件 | 用途 |
| --- | --- |
| `behavior_pack/manifest.json` | 行为包清单、包 UUID 与最低引擎版本声明 |
| `behavior_pack/anvilcraft_scripts/modMain.py` | ModSDK 入口与双端系统注册（文件名由引擎固定要求） |
| `behavior_pack/anvilcraft_scripts/server/` | 服务端事件监听、配方结算、电网流体计算与数据存档 |
| `behavior_pack/anvilcraft_scripts/client/` | 客户端 UI、模型动画与粒子特效 |
| `behavior_pack/anvilcraft_scripts/common/` | 无引擎依赖的纯数据结构、配方表与网络事件字段定义 |
| `behavior_pack/netease_blocks/`、`netease_items_beh/` | 自定义方块与物品行为定义 |
| `behavior_pack/recipes/` | 基岩版原版静态合成与熔炼配方 JSON |
| `resource_pack/` | 资源包清单、模型、纹理、UI、语言文件与音效 |
| `tests/` | 基于 `unittest` 的纯逻辑单元测试 |

## 编码与架构要求

- 所有 `.py` 文件头部必须声明 `# -*- coding: utf-8 -*-`。中文文本字面量使用 `unicode`（`u"..."`），在文件读写、JSON 解析和 SDK 调用处显式转换编码。
- 严格使用 Python 2.7 语法与标准库，禁止使用 f-string、类型注解、`async`/`await`、`dataclasses` 及 Python 3 专有模块。
- 模块名与函数名使用 `snake_case`，类名使用 `CapWords`。引擎要求固定的入口文件名（如 `modMain.py`）、事件名称和回调函数签名保持 SDK 原样。
- 涉及除法运算时显式导入 `from __future__ import division` 或区分整除 `//` 与浮点除法，保持物品数量、电量、流体量和计时的数值类型一致。超出方块实体存储上限的大整数必须转为字符串保存。
- 物品数量增减、配方结算、伤害计算、能量扣减和存档写入全部在服务端执行。客户端只上报玩家操作意图，服务端必须校验玩家距离、所在维度、目标方块坐标和容器槽位合法性。
- `server/` 仅调用服务端 API，`client/` 仅调用客户端 API，`common/` 禁止导入任何 `mod.*` 引擎模块，以便在本地直接运行单元测试。
- `mc-netease-sdk` 仅作为本地开发依赖安装，打包发布时只包含项目脚本与已获授权的资源文件。

## 本地检查与游戏内测试

提交代码前在根目录运行：

```powershell
python tools/check.py
git diff --check
```

`tools/check.py` 会遍历 `behavior_pack/`、`resource_pack/`、`docs/`、`tools/` 和 `tests/`，验证所有 `.py` 与 `.json` 文件的 UTF-8 编码，调用 Python 2.7 `compile()` 检查脚本语法（不生成 `.pyc`），并用 `json.loads()` 校验 JSON 文件。全部通过返回 `0`，文件校验失败返回 `1`，Python 版本不是 2.7 返回 `2`。

纯算法与状态机使用标准库 `unittest` 编写单元测试。引擎事件触发顺序、方块实体持久化、容器读写、多人联机同步和存档重载需在 MC Studio 测试存档中实测。打包产物输出到 `dist/`，本地测试存档放在 `worlds/` 或 `run/`（均已配置 `.gitignore` 忽略）。包 UUID 以及已发布的物品、方块标识符一旦对外发布不得更改；修改存档数据结构时必须提供旧版本兼容迁移逻辑。
