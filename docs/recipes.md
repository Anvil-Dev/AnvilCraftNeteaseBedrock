# 生存加工配方

主包 `0.2.0` 接入 12 条方块粉碎、1 条物品压缩和 11 条普通物品解包配方。首次进入安装了主包的世界会获得《铁砧工艺手册》（`anvilcraft:guide_book`），使用手册即可按平台查阅配方。

## 方块粉碎

把原料方块放稳，让原版铁砧从正上方三格落下。表中每条配方均用一个原料方块原地换成一个产物方块。

| 原料 | 产物 | 上游 `block_crush/` 配方名 |
| --- | --- | --- |
| 圆石 | 沙砾 | `gravel` |
| 沙砾 | 沙子 | `sand` |
| 磨制安山岩 | 安山岩 | `andesite` |
| 磨制闪长岩 | 闪长岩 | `diorite` |
| 磨制花岗岩 | 花岗岩 | `granite` |
| 花岗岩 | 红沙 | `red_sand` |
| 灵魂土 | 灵魂沙 | `soul_sand` |
| 石砖 | 裂纹石砖 | `cracked_stone_bricks` |
| 下界砖块 | 裂纹下界砖块 | `cracked_nether_bricks` |
| 磨制黑石砖 | 裂纹磨制黑石砖 | `cracked_polished_blackstone_bricks` |
| 深板岩砖 | 裂纹深板岩砖 | `cracked_deepslate_bricks` |
| 深板岩瓦 | 裂纹深板岩瓦 | `cracked_deepslate_tiles` |

## 空炼药锅压缩

将骨头丢进空炼药锅，让铁砧从锅口正上方落下。每 3 个骨头得到 1 个骨块，可合并计算锅内分开的几堆骨头。7 个骨头可加工成 2 个骨块，余下 1 个骨头留在锅内。加水的锅、普通地面和少于 3 个骨头都不会触发这条配方。上游配方名为 `item_compress/bone_block`。

## 铁活板门解包

把铁活板门装在方块上半格，关上门并在下方留出收集空间。将原料丢在门面中央，让铁砧落在门上，产物从门下取出。每次落砧选择一种配方，可按原料数量处理最多 64 份。

| 原料 | 产物 | 上游 `unpack/` 配方名 |
| --- | --- | --- |
| 1 个紫水晶块 | 4 个紫水晶碎片 | `amethyst_shard` |
| 1 个黏土块 | 4 个黏土球 | `clay_ball` |
| 1 个荧石 | 4 个荧石粉 | `glowstone_dust` |
| 1 个蜂蜜块、4 个玻璃瓶 | 4 个蜂蜜瓶 | `honey_bottle` |
| 1 个蜜脾块 | 4 个蜜脾 | `honeycomb` |
| 1 个西瓜 | 9 个西瓜片 | `melon_slice` |
| 1 个滴水石块 | 4 个滴水石锥 | `pointed_dripstone` |
| 1 个海晶石 | 4 个海晶碎片 | `prismarine_shard_from_prismarine` |
| 1 个海晶石砖 | 9 个海晶碎片 | `prismarine_shard_from_prismarine_bricks` |
| 1 个石英块 | 4 个下界石英 | `quartz` |
| 1 个雪块 | 4 个雪球 | `snowball` |

网易 3.10 采用基岩版 ID。下界砖块从 Java 版的 `minecraft:nether_bricks` 映射为 `minecraft:nether_brick`，雪块从 `minecraft:snow_block` 映射为 `minecraft:snow`，西瓜方块从 `minecraft:melon` 映射为 `minecraft:melon_block`，西瓜片从 `minecraft:melon_slice` 映射为 `minecraft:melon`。

## 验收记录

圆石→沙砾→沙子已在网易 3.10 PC 客户端通过手动复测。以上 24 条配方的原料、用量和产物已与上游 JSON 核对。Python 2.7 事件回放覆盖分堆扣料、余料附加数据、平台状态、拾取冲突、重复落地回调和生成失败后的补发。手册的打开与新增配方的实际表现待客户端确认。[圆石粉碎复测记录](development.md#复测原版铁砧粉碎)
