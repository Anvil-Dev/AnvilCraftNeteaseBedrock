# 来源与许可

本仓库沿用 AnvilCraft 的代码许可和非代码资源许可，并保留两份许可证的原始内容。

| 项目 | 来源与适用方式 |
| --- | --- |
| 上游项目 | [Anvil-Dev/AnvilCraft](https://github.com/Anvil-Dev/AnvilCraft) |
| 本次调研提交 | `ef65f8a876c4d4d695a2f263f3f62d9280e10dad` |
| 代码许可 | [LICENSE](LICENSE)，保留 `Copyright (c) 2024 Gugle`、LGPL 第 3 版和所附 GPL 第 3 版全文；文件头包含后续版本许可选项 |
| 非代码资源许可 | [ASSETS_LICENSE](ASSETS_LICENSE)，原文为 `All rights reserved unless explicitly stated.` |

上游 README 将代码和非代码资产分别指向这两份文件。复制纹理、模型、音效、语言文件等资源时，需要逐项记录来源、作者和适用授权；迁移时制作的新资源也按本仓库资源许可处理，另有说明的文件按其说明处理。

调研文档记录玩法、源码位置和迁移方案。每次实际移植代码或引入资源时，需要记录上游路径、提交与修改内容，以便保留归属信息并跟踪更新。

阶段 0 的方块粉碎沿用上述提交中 `src/generated/resources/data/anvilcraft/recipe/block_crush/gravel.json` 与 `sand.json` 的输入和产物，落地结算按网易事件在 Python 2.7 中重新实现。实验方块引用游戏自带的纹理图集，实验界面的 JSON 与中文名称由本项目编写。

阶段 1 的原料与产物来自同一提交的 `recipe/block_crush/`、`recipe/item_compress/bone_block.json` 与 `recipe/unpack/`。加工位置按 `ItemCompressRecipe.java`、`UnpackRecipe.java` 和 AnvilLib 的世界配方范围换算。手册沿用 `anvilcraft:guide_book` 与上游根进度的首次入服奖励，正文和网易书本配置由本项目编写，图标引用游戏内置书本纹理。[上游配方目录](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/generated/resources/data/anvilcraft/recipe)

物品压缩和解包表同时包含上游在启动时生成的配方。转换规则依照同一提交的 `VanillaRecipesWrap.java` 和 `tags/item/compress_item.json`，原料、数量和产物取自 Minecraft Java 1.21.1 与 NeoForge 21.1.238 的默认数据包，并按 Mojang 的基岩 1.21.130.3 物品表转换标识符。生成工具与网易结算代码均在本仓库中用 Python 2.7 编写。[上游转换规则](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/recipe/anvil/wrap/VanillaRecipesWrap.java) · [基岩物品表](https://github.com/Mojang/bedrock-samples/blob/v1.21.130.3/metadata/vanilladata_modules/mojang-items.json)

双方块压合与原版方块压榨采用同一提交的 `recipe/block_compress/`、`recipe/squeezing/`，以及 `tags/block/mushroom_block.json` 和 Java 原版 `minecraft:leaves` 标签。上下方块的位置、结果位置和原版锅的流体显示层数按 `BlockCompressRecipe.java`、`SqueezingRecipe.java`、`HasCauldron.java` 换算，网易事务恢复与手册正文由本项目编写。[上游配方实现](https://github.com/Anvil-Dev/AnvilCraft/tree/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/recipe/anvil/wrap)

脚手架筛分采用同一上游提交的 `recipe/mesh/` 原版配方，树叶配方按 `MeshRecipeGeneratingCache.java` 的树种 ID 关联规则生成，原料和产物由 Java 1.21.1 的默认标签与基岩注册表核对。每份原料的独立概率由 Python 标准库重新实现，补发保存已抽出的物品数量。新增手册正文由本项目编写。[上游筛分实现](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/recipe/anvil/wrap/MeshRecipe.java) · [上游树叶生成规则](https://github.com/Anvil-Dev/AnvilCraft/blob/ef65f8a876c4d4d695a2f263f3f62d9280e10dad/src/main/java/dev/dubhe/anvilcraft/recipe/generate/MeshRecipeGeneratingCache.java)

开发依赖 `mc-netease-sdk` 是网易发布的接口补全包，其版权与许可归属该依赖自身；游戏发布包通过网易运行环境调用 ModSDK。
