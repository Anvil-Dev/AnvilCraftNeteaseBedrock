# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""匹配上下两格的压合配方，并把压榨液量换算为原版锅的刻度。"""

from anvilcraft_scripts.common.vanilla_catalog import BLOCK_COMPRESS, BLOCK_SMEAR, SQUEEZING


def compression(upper, lower):
    for source, top, bottom, result in BLOCK_COMPRESS:
        if upper in top and lower in bottom:
            return source, result
    return None


def smearing(upper, lower, states):
    for source, top, properties, bottom, result in BLOCK_SMEAR:
        if (upper in top and lower in bottom
                and all(states.get(key) == value for key, value in properties.items())):
            return source, result
    return None


def squeezed_states(states, fluid, amount):
    """沿用上游普通锅的三层显示，水和细雪加一层，熔岩直接装满。"""
    level = states.get("fill_level")
    liquid = fluid.split(":")[1]
    if not isinstance(level, (int, long)) or not 0 <= level <= 6 or amount != 250:
        return None
    if level and states.get("cauldron_liquid") != liquid:
        return None
    if level > 4:
        return None
    result = dict(states)
    result["cauldron_liquid"] = liquid
    # 上游 250 mB 在三层普通锅中四舍五入为一层，基岩的一层占两个刻度。
    result["fill_level"] = 6 if liquid == "lava" else 2 * (level // 2 + 1)
    return result
