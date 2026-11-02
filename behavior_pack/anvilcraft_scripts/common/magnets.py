# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""磁铁与悬持铁砧的方块对应关系。"""

MAGNETS = ("anvilcraft:magnet_block", "anvilcraft:hollow_magnet_block")
HELD = {
    "minecraft:anvil": "anvilcraft:held_anvil",
    "minecraft:chipped_anvil": "anvilcraft:held_chipped_anvil",
    "minecraft:damaged_anvil": "anvilcraft:held_damaged_anvil",
}
PASSABLE = ("minecraft:air", "minecraft:water", "minecraft:flowing_water",
            "minecraft:lava", "minecraft:flowing_lava")
