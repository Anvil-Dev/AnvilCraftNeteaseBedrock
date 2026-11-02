# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""按加工平台、物品数量和掉落位置匹配上游的压缩与解包配方。"""

from collections import Counter, namedtuple
from random import random

from anvilcraft_scripts.common.vanilla_catalog import COMPRESS, MESH, UNPACK

CAULDRON = "minecraft:cauldron"
TRAPDOOR = "minecraft:iron_trapdoor"
SCAFFOLDING = "minecraft:scaffolding"
Drop = namedtuple("Drop", "entity pos item")
Recipe = namedtuple("Recipe", "source inputs outputs")
Batch = namedtuple("Batch", "recipe times debits")


RECIPES = {
    CAULDRON: tuple(Recipe(*row) for row in COMPRESS),
    TRAPDOOR: tuple(Recipe(*row) for row in UNPACK),
    SCAFFOLDING: tuple(Recipe(*row) for row in MESH),
}
STACK_LIMITS = {"minecraft:minecart": 1, "minecraft:honey_bottle": 16, "minecraft:snowball": 16}


def usable_platform(name, states):
    if name == CAULDRON:
        return states.get("fill_level") == 0
    if name == TRAPDOOR:
        return states.get("upside_down_bit") == 1 and states.get("open_bit") == 0
    if name == SCAFFOLDING:
        return True
    return False


def in_recipe_area(platform, pos, feet):
    """以铁砧底面中心为原点，和上游一样用掉落物的小包围盒判断相交。"""
    x, y, z = pos
    if platform == CAULDRON:
        center_y, half_width, half_height = y + 0.625, 0.375, 0.375
    elif platform == SCAFFOLDING:
        center_y, half_width, half_height = y + 1, 0.5, 0.5
    else:
        center_y, half_width, half_height = y + 1, 0.5, 0.125
    half_item = 0.0625
    return (abs(feet[0] - x - 0.5) < half_width + half_item and
            abs(feet[1] + 0.125 - center_y) < half_height + half_item and
            abs(feet[2] - z - 0.5) < half_width + half_item)


def item_name(item):
    return item.get("newItemName") or item.get("itemName")


def _tag_value(tag):
    return tag.get("__value__", tag) if isinstance(tag, dict) else tag


def _empty_cart_data(tag):
    fields = _tag_value(tag)
    if not fields:
        return True
    if not isinstance(fields, dict):
        return False
    for key, value in fields.iteritems():
        if key in ("display", "RepairCost"):
            continue
        if key in ("Items", "ChestItems") and not _tag_value(value):
            continue
        if key in ("EntityTag", "BlockEntityTag") and _empty_cart_data(value):
            continue
        return False
    return True


def match_drops(platform, drops):
    """一次落砧只选一种配方，最多处理上游默认的 64 份。"""
    # 只拆能确认未载货的矿车，保留带战利品表或未知库存格式的掉落物。
    drops = [drop for drop in drops if item_name(drop.item) not in
             ("minecraft:chest_minecart", "minecraft:hopper_minecart")
             or _empty_cart_data(drop.item.get("userData"))]
    if not drops:
        return None
    totals = Counter()
    for drop in drops:
        totals[item_name(drop.item)] += drop.item["count"]
    for recipe in RECIPES[platform]:
        times = min([64] + [sum(totals[name] for name in options) // count
                            for options, count in recipe.inputs])
        if not times:
            continue
        debits = []
        for options, count in recipe.inputs:
            remaining = count * times
            for drop in drops:
                if item_name(drop.item) not in options:
                    continue
                take = min(drop.item["count"], remaining)
                debits.append((drop, take))
                remaining -= take
                if not remaining:
                    break
        return Batch(recipe, times, debits)
    return None


def products(batch, roll=random):
    """逐份独立抽取概率产物，再按基岩版堆叠上限拆分。"""
    for name, quantity in batch.recipe.outputs:
        maximum = STACK_LIMITS.get(name, 64)
        if isinstance(quantity, dict):
            remaining = sum(1 for _ in range(batch.times * quantity["n"]) if roll() < quantity["p"])
        else:
            remaining = batch.times * quantity
        while remaining:
            count = min(maximum, remaining)
            yield {"newItemName": name, "newAuxValue": 0, "count": count}
            remaining -= count
