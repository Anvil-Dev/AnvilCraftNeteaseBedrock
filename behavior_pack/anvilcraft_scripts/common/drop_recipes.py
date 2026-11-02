# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""按加工平台、物品数量和掉落位置匹配上游的压缩与解包配方。"""

from collections import Counter, namedtuple

CAULDRON = "minecraft:cauldron"
TRAPDOOR = "minecraft:iron_trapdoor"
Drop = namedtuple("Drop", "entity pos item")
Recipe = namedtuple("Recipe", "inputs output count")
Batch = namedtuple("Batch", "recipe times debits")


def _single(source, result, count):
    return Recipe((("minecraft:" + source, 1),), "minecraft:" + result, count)


RECIPES = {
    CAULDRON: (Recipe((("minecraft:bone", 3),), "minecraft:bone_block", 1),),
    TRAPDOOR: (
        # 蜂蜜瓶配方需要两种原料，按上游优先级先匹配。
        Recipe((("minecraft:honey_block", 1), ("minecraft:glass_bottle", 4)),
               "minecraft:honey_bottle", 4),
        _single("amethyst_block", "amethyst_shard", 4),
        _single("clay", "clay_ball", 4),
        _single("glowstone", "glowstone_dust", 4),
        _single("honeycomb_block", "honeycomb", 4),
        _single("melon_block", "melon", 9),
        _single("dripstone_block", "pointed_dripstone", 4),
        _single("prismarine", "prismarine_shard", 4),
        _single("prismarine_bricks", "prismarine_shard", 9),
        _single("quartz_block", "quartz", 4),
        _single("snow", "snowball", 4),
    ),
}


def usable_platform(name, states):
    if name == CAULDRON:
        return states.get("fill_level") == 0
    if name == TRAPDOOR:
        return states.get("upside_down_bit") == 1 and states.get("open_bit") == 0
    return False


def in_recipe_area(platform, pos, feet):
    """以铁砧底面中心为原点，和上游一样用掉落物的小包围盒判断相交。"""
    x, y, z = pos
    if platform == CAULDRON:
        center_y, half_width, half_height = y + 0.625, 0.375, 0.375
    else:
        center_y, half_width, half_height = y + 1, 0.5, 0.125
    half_item = 0.0625
    return (abs(feet[0] - x - 0.5) < half_width + half_item and
            abs(feet[1] + 0.125 - center_y) < half_height + half_item and
            abs(feet[2] - z - 0.5) < half_width + half_item)


def item_name(item):
    return item.get("newItemName") or item.get("itemName")


def match_drops(platform, drops):
    """一次落砧只选一种配方，最多处理上游默认的 64 份。"""
    totals = Counter()
    for drop in drops:
        totals[item_name(drop.item)] += drop.item["count"]
    for recipe in RECIPES[platform]:
        times = min([64] + [totals[name] // count for name, count in recipe.inputs])
        if not times:
            continue
        needed = dict((name, count * times) for name, count in recipe.inputs)
        debits = []
        for drop in drops:
            name = item_name(drop.item)
            take = min(drop.item["count"], needed.get(name, 0))
            if take:
                debits.append((drop, take))
                needed[name] -= take
        return Batch(recipe, times, debits)
    return None


def products(batch):
    """按基岩版物品堆叠上限拆分产物。"""
    name = batch.recipe.output
    maximum = 16 if name in ("minecraft:snowball", "minecraft:honey_bottle") else 64
    remaining = batch.times * batch.recipe.count
    while remaining:
        count = min(maximum, remaining)
        yield {"newItemName": name, "newAuxValue": 0, "count": count}
        remaining -= count
