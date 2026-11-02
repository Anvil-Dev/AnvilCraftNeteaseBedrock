# Python 2.7 开发规范

网易基岩版 ModSDK 运行在 Python 2.7 环境中。本仓库的业务脚本与检查工具统一使用 Python 2.7 编写，开发环境使用的 SDK 补全包版本与目标客户端实测版本分开记录。

## 本地环境配置

| 项目 | 配置值 | 检查命令 |
| --- | --- | --- |
| Python 解释器 | `2.7.18`（[`.python-version`](../.python-version)） | `python --version` |
| ModSDK 补全包 | `mc-netease-sdk==3.10.0.81573`（[`requirements-dev.txt`](../requirements-dev.txt)） | `python -m pip show mc-netease-sdk` |
| 文本与缩进格式 | UTF-8、LF、4 空格缩进（[`.editorconfig`](../.editorconfig)） | `git diff --check` |
| 静态语法检查 | 标准库脚本 [`tools/check.py`](../tools/check.py) | `python tools/check.py` |

在 IDE 中将项目解释器指定为 Python 2.7.18。`.python-version` 供版本管理工具读取，终端内直接执行的 `python` 仍由系统 `PATH` 决定。安装代码补全依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

项目以网易 ModSDK 3.10 和基岩引擎 1.21.130 为目标。`mc-netease-sdk` 提供 `RegisterSystem`、`GetEngineCompFactory` 等接口声明，游戏内实测使用网易客户端。[网易 3.10 更新说明](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/更新信息/3.10.html?catalog=1) · [补全包发布页](https://pypi.org/project/mc-netease-sdk/3.10.0.81573/)

## 目录结构

当前仓库包含行为包、资源包、实验包与开发工具。

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
├── behavior_pack/
├── resource_pack/
├── tests/
│   └── addon/
├── docs/
│   ├── README.md
│   ├── development.md
│   ├── development-plan.md
│   ├── migration-research.md
│   ├── source-inventory.json
│   └── sources.md
└── tools/
    ├── check.py
    └── package_addon.py
```

阶段 0 已建立基础包，后续玩法沿用以下目录分工。

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
python -B -m unittest discover -s tests -v
git diff --check
```

`tools/check.py` 会遍历 `behavior_pack/`、`resource_pack/`、`docs/`、`tools/` 和 `tests/`，验证所有 `.py` 与 `.json` 文件的 UTF-8 编码，调用 Python 2.7 `compile()` 检查脚本语法（不生成 `.pyc`），并用 `json.loads()` 校验 JSON 文件。全部通过返回 `0`，文件校验失败返回 `1`，Python 版本不是 2.7 返回 `2`。

纯算法与状态机使用标准库 `unittest` 编写单元测试。引擎事件触发顺序、方块实体持久化、容器读写、多人联机同步和存档重载需在 MC Studio 测试存档中实测。打包产物输出到 `dist/`，本地测试存档放在 `worlds/` 或 `run/`（均已配置 `.gitignore` 忽略）。包 UUID 以及已发布的物品、方块标识符一旦对外发布不得更改；修改存档数据结构时必须提供旧版本兼容迁移逻辑。

## 在 MC Studio 导入附加包

1. 在仓库根目录运行 `python -B tools/package_addon.py`。
2. 打开工作台的「本地导入」，选择基岩版附加包，勾选「复制文件到默认文件夹」，选择 `dist/AnvilCraft-Studio.zip`。使用文件夹导入时，先将此 ZIP 单独解压，选择直接包含两个包目录的那一级。
3. 从作品库选择导入的组件，启动「开发测试」。进入世界后，在 Mod 日志中查看 `[AnvilCraft] server ready` 和 `[AnvilCraft] client ready`。如需测试重力铁砧和检测台，再单独导入 `dist/AnvilCraft-Lab-Studio.zip`，在同一测试世界启用主包和实验包。

工作台通过行为包的 `entities/` 和资源包的 `textures/` 识别包类型，每个目录都与各自的 `manifest.json` 同级。仓库沿用网易模板中的空文件 `.dummy`，使 Git 检出、打包和工作台复制都保留这两个目录。出现「缺少 Manifest 配置文件」时，先核对所选 ZIP 解压后的这两组路径。[网易附加包结构与导入说明](https://mc.163.com/dev/mcmanual/mc-dev/mconline/10-addon教程/第18章：打包导出你的作品/课程01.包体的结构和导入.html?catalog=1)

### 复测原版铁砧粉碎

2026-11-02，主包 `0.1.1` 在网易 3.10 PC 客户端通过手动复测。测试时将圆石（`minecraft:cobblestone`）放在地上，让原版铁砧从圆石正上方三格自由落下。第一次落下后，圆石变成沙砾（`minecraft:gravel`）。再次落下后，沙砾变成沙子（`minecraft:sand`）。

在启用命令的测试世界中，站在平地上保持不动，依次运行以下两条命令即可复现第一次下落。普通石头（`minecraft:stone`）可用于单独的对照测试，预期保持原样。

```text
/setblock ~2 ~ ~ minecraft:cobblestone
/setblock ~2 ~4 ~ minecraft:anvil
```

2026-11-02 的 PC 测试日志确认基岩引擎 `1.21.130.0` 已加载主包两端。旧版服务端每次收到无参数的 `OnScriptTickServer` 都抛出 `TypeError: _advance() takes exactly 2 arguments (1 given)`。修复版客户端启动行包含 `addon=0.1.1`。服务端识别原版下落实体后记录 `falling anvil`，加工成功记录 `crush` 和产物 ID，输入未匹配或替换失败则记录 `no crush` 和脚下方块 ID。

主包行为包 `0.3.0` 搭配资源包 `0.2.0`，客户端启动行包含 `addon=0.3.0`。首次进入该世界的玩家会收到手册。加工日志中的 `item process` 记录配方 ID、份数和每种产物的总量。旧版欠发记录中的西瓜片随补发迁移到 `minecraft:melon_slice`。[配方与复测方法](recipes.md)

如果引擎拒绝生成产物或返还余料，服务端会把欠发物品保存到世界扩展数据 `anvilcraft:pending_drops_v1`，在目标区块加载后重试。如果补发已生成实体、存档写入和实体撤销又同时失败，`spawned item could not be retracted` 日志会列出实体 ID 和原始记录。此时先恢复存档写入并核对该物品，再重启世界。引擎的存档写入和掉落物生成分属两次调用，硬崩溃窗口需在存档回归时单独验证。

## 复核原版落砧配方

`tools/sync_vanilla_recipes.py` 读取 Minecraft Java 1.21.1 客户端中的默认配方、NeoForge 21.1.238 的配方覆盖与标签、AnvilCraft `ef65f8a` 的默认数据包，以及基岩 1.21.130 的物品表。运行时直接使用生成的 Python 配方表。更新清单时先准备这些输入，在仓库根目录执行以下命令。[基岩 1.21.130.3 物品表](https://raw.githubusercontent.com/Mojang/bedrock-samples/v1.21.130.3/metadata/vanilladata_modules/mojang-items.json)

```powershell
$cache = Join-Path $env:USERPROFILE '.gradle/caches'
$mc = Join-Path $cache 'neoformruntime/artifacts/minecraft_1.21.1_client.jar'
$neo = (Get-Item "$cache/modules-2/files-2.1/net.neoforged/neoforge/21.1.238/*/*-universal.jar").FullName
$items = '.sdk/bedrock-1.21.130.3/mojang-items.json'
python -B tools/sync_vanilla_recipes.py --minecraft $mc --neoforge $neo --anvilcraft ../AnvilCraft --bedrock-items $items --check
```

`--check` 将重新计算的原料、产物和匹配顺序与仓库中的配方表逐项比对。去掉该参数即可重建配方表。基线输出为 `crush=12 compress=33 unpack=54`。
