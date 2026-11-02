# 调研来源与统计说明

本文档列出特性迁移所依据的上游 AnvilCraft 源码入口、网易 ModSDK 官方文档链接，以及静态配方统计脚本的计算口径。

调研与数据采样日期为 2026-11-02。所有上游源码链接均固定到提交 `ef65f8a876c4d4d695a2f263f3f62d9280e10dad`（分支 `dev/1.21/1.6`），便于后续核对。网易接口行为以官方文档说明为基础，实际客户端表现将在阶段 0 实测确认。

## 上游源码索引

| 编号 | 模块领域 | 源码位置 | 核对内容 |
| --- | --- | --- | --- |
| S1 | 项目配置与许可证 | [README.md](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/README.md)、[gradle.properties](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/gradle.properties)、[LICENSE](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/LICENSE)、[ASSETS_LICENSE](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/ASSETS_LICENSE) | Java 21 / NeoForge 版本基线、代码与美术资源双许可证条款 |
| S2 | 方块与物品注册 | [ModBlocks.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/init/block/ModBlocks.java)、[ModItems.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/init/item/ModItems.java)、[ModFoodItems.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/init/item/ModFoodItems.java) | 金属材料、装饰方块、机器、工具、食物和终局物品的注册清单 |
| S3 | 静态配方文件 | [生成配方目录](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/generated/resources/data/anvilcraft/recipe)、[手写配方目录](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/resources/data/anvilcraft/recipe) | 各配方的具体原料、产物、触发条件与文件数量 |
| S4 | 配方类型与序列化 | [ModRecipeTypes.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/init/recipe/ModRecipeTypes.java)、[recipe 实现目录](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/recipe)、[data/recipe 生成器](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/data/recipe) | 粉碎、压缩、冲压、炼药锅加工、多合锻造、多步加工与天体配方的字段定义 |
| S5 | 铁砧落地结算 | [FallingBlockEntityMixin.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/mixin/FallingBlockEntityMixin.java)、[AnvilEventListener.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/event/anvil/AnvilEventListener.java) | 铁砧落地事件抛时机、世界配方触发顺序、切石机破拆与伤害结算 |
| S6 | 磁铁与铁砧锤交互 | [MagnetBlock.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/MagnetBlock.java)、[ModAnvilBehaviors.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/init/ModAnvilBehaviors.java)、[AnvilHammerItem.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/item/AnvilHammerItem.java) | 磁铁吸起与红石释放逻辑、特殊方块被砸响应、铁砧锤旋转与拆卸 |
| S7 | 电网与批量机器 | [api/power](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/api/power)、[block/entity/batch](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/entity/batch) | 发电、耗电、输电半径、蓄电、电网合并拆分与批量合成/切割机器 |
| S8 | 物流、容器与流体 | [block/entity](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/entity)、[block/entity/storage](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/entity/storage)、[block/entity/fluid](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/entity/fluid) | 溜槽、磁力溜槽、木箱、超维存储、储液罐与流体管道 |
| S9 | 生物、矿物与装备 | [HitCrabTrapBehavior.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/anvil/HitCrabTrapBehavior.java)、[MineralFountainBlockEntity.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/entity/MineralFountainBlockEntity.java)、[ModAmulets.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/init/item/ModAmulets.java)、[item 目录](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/item) | 捕蟹笼、矿物涌泉、护符系统、工具属性与特殊武器 |
| S10 | 激光系统 | [BaseLaserBlockEntity.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/entity/BaseLaserBlockEntity.java)、[api/laser](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/api/laser) | 激光发射方向、最大射程、棱镜折射、照射加工与实体伤害 |
| S11 | 复杂结构与天体终局 | [FallingGiantAnvilEntity.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/entity/FallingGiantAnvilEntity.java)、[api/sliding](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/api/sliding)、[recipe/multiblock](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/recipe/multiblock)、[block/entity/celestial](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/block/entity/celestial)、[worldgen](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/worldgen)、[ModMegastructures.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/init/ModMegastructures.java) | 巨型铁砧、滑动导轨结构、多方块配方、天体机器、月球世界生成与巨构 |
| S12 | 手册引导与外部模组联动 | [GuideEventListener.java](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/event/GuideEventListener.java)、[integration](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/integration)、[advancements](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/advancements)、[api/energy](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/api/energy) | 手册发放与查阅、JEI/EMI 配方展示、Curios 饰品栏与 FE 能源对接 |

调研期间详细阅读了铁砧落地处理、磁铁吸放状态、方块粉碎、物品压缩、冲压、压榨、解包与电网组件的实现源码；其余模块通过注册表入口、配方 JSON 与对应包结构确认功能边界。

## 网易 ModSDK 官方文档参考

| 编号 | 官方文档页面 | 关注要点 |
| --- | --- | --- |
| N1 | [网易 3.10 更新说明](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/更新信息/3.10.html?catalog=1)、[mc-netease-sdk PyPI 页面](https://pypi.org/project/mc-netease-sdk/3.10.0.81573/) | 目标基岩引擎 `1.21.130`、Python 2 补全包 `3.10.0.81573` |
| N2 | [自定义重力方块](https://mc.163.com/dev/mcmanual/mc-dev/mcguide/20-玩法开发/15-自定义游戏内容/2-自定义方块/3-特殊方块/6-自定义重力方块.html) | `custom_heavy_block` 基础类型、`netease:fall` 组件、Python 事件开关与落地伤害参数 |
| N3 | [方块事件文档](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/事件/方块.html) | 开始下落、落地还原、破坏为掉落物、红石信号强度变化与方块实体 Tick 事件参数 |
| N4 | [自定义方块实体指南](https://mc.163.com/dev/mcmanual/mc-dev/mcguide/20-玩法开发/15-自定义游戏内容/2-自定义方块/4-自定义方块实体.html) | `netease:block_entity` 配置、每秒 20 次 Tick 触发范围与扩展数据用法 |
| N5 | [方块实体接口文档](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/方块/方块实体.html) | `CreateBlockEntityData` 与 `CreateBlockInfo` 的区别、支持的数据类型、大整数限制与顶层键重新赋值要求 |
| N6 | [世界方块管理接口](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/世界/方块管理.html) | `GetBlockNew`、`SetBlockNew`、区块加载前提、覆盖容器会清空内部物品的注意事项与方块状态读写 |
| N7 | [容器接口文档](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/方块/容器.html) | `GetContainerItem`、`getUserData` 参数默认值、`SpawnItemToContainer` 与支持的容器类型 |
| N8 | [红石接口文档](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/方块/红石.html) | 服务端 `GetStrength` 函数签名与 0–15 信号强度返回值 |
| N9 | [配方接口文档](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/世界/配方.html) | `AddRecipe` 动态注册配方的用法及在联机大厅模式下的限制 |
| N10 | [方块组合（调色板）接口](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/世界/方块组合.html) | `GetBlockPaletteBetweenPos`、`SetBlockByBlockPalette`、旋转、床/门处理与冲突中断行为 |
| N11 | [地图与维度接口](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/世界/地图.html) | `CreateDimension`、`CheckChunkState` 与自定义维度注册要求 |

初次调研使用 `3.9.0.79920` 补全包。阶段 0 按目标版本 `3.10.0.81573` 核对了方块替换、标签查询、容器物品读写与方块实体数据接口。

## 静态配方统计方法

[`source-inventory.json`](source-inventory.json) 由 Python 2.7 脚本解析上游以下两个目录中的全部 `.json` 文件，按顶层 `type` 字段分类汇总生成：

- `src/main/resources/data/anvilcraft/recipe/`：21 个文件
- `src/generated/resources/data/anvilcraft/recipe/`：1,607 个文件

两个目录合计 1,628 个 JSON 文件，涵盖 53 种配方 `type`（其中 `anvilcraft:*` 命名空间下有 44 种 `type`、共 1,049 个文件），两个目录间不存在同名相对路径冲突。统计范围包含带加载条件的联动配方，不包含进度（Advancement）JSON、内置可选数据包以及在 Java 代码中动态构造的配方。

[`source-inventory.json`](source-inventory.json) 中的 `license_sha256` 字段记录了上游 `LICENSE` 与 `ASSETS_LICENSE` 原始文件的 SHA-256 哈希值，用于校验本仓库根目录下的同名许可证文件与上游完全一致。
