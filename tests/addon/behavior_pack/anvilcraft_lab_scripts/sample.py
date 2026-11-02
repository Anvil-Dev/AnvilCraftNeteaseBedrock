# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""检查实验物品的耐久、附魔和自定义标记是否一同保存。"""

MARKER = {"__type__": 8, "__value__": "anvilcraft_lab_sample"}


def make_sample():
    return {"newItemName": "minecraft:iron_pickaxe", "newAuxValue": 0, "count": 1,
            "durability": 73, "enchantData": [(15, 1)], "userData": {"anvilcraft_lab": dict(MARKER)}}


def sample_status(item):
    if not item or not item.get("count"):
        return u"空槽"
    if item.get("newItemName") != "minecraft:iron_pickaxe" or item.get("count") != 1:
        return u"已被其他物品占用"
    failures = []
    if item.get("durability") != 73:
        failures.append(u"耐久")
    if (15, 1) not in [tuple(pair) for pair in item.get("enchantData") or ()]:
        failures.append(u"附魔")
    if (item.get("userData") or {}).get("anvilcraft_lab") != MARKER:
        failures.append(u"userData")
    return (u"不匹配：" + u"、".join(failures)) if failures else u"耐久、附魔和标记均相符"


def within_reach(feet, block):
    return feet is not None and sum((a - b - 0.5) ** 2 for a, b in zip(feet, block)) <= 36
