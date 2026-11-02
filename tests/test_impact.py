# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""用实际结算函数验证一次下落只消费一条配方，卸载后不会补算。"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "behavior_pack"))

from anvilcraft_scripts.common.impact import FallingAnvils, crush_at


class BlockColumn(object):

    def __init__(self):
        self.cells = {(1, (15, 63, -1)): "minecraft:cobblestone"}
        self.writes = []

    def GetBlockNew(self, pos, dimension):
        name = self.cells.get((dimension, pos))
        return {"name": name} if name else None

    def SetBlockNew(self, pos, block, mode, dimension, legacy):
        self.writes.append((dimension, pos))
        self.cells[dimension, pos] = block["name"]
        return True


class ImpactTests(unittest.TestCase):

    def setUp(self):
        self.falls = FallingAnvils()
        self.world = BlockColumn()
        self.anvil = "minecraft:anvil"

    def start(self, entity):
        self.falls.start(1, str(entity), self.anvil, (15, 69, -1), 15)

    def land(self, entity, dimension=1, pos=(15, 64, -1)):
        target = self.falls.land(dimension, entity, self.anvil, pos)
        if target is not None:
            return crush_at(self.world, dimension, target)

    def test_two_falls_with_repeated_landing(self):
        self.start(123)
        self.assertIsNone(self.land(123, dimension=0))
        self.assertEqual("minecraft:gravel", self.land(123))
        self.assertIsNone(self.land(123))
        self.start(124)
        self.assertEqual("minecraft:sand", self.land(124))
        self.assertEqual(2, len(self.world.writes))

    def test_polished_granite_needs_two_separate_falls_to_make_red_sand(self):
        self.world.cells[1, (15, 63, -1)] = "minecraft:polished_granite"
        self.start(21)
        self.assertEqual("minecraft:granite", self.land(21))
        self.assertIsNone(self.land(21))
        self.start(22)
        self.assertEqual("minecraft:red_sand", self.land(22))

    def test_unload_break_and_expiry_discard_starts(self):
        self.start(1)
        self.falls.unload(1, 1, 0, ["1"])
        self.assertIsNone(self.land(1))
        self.start(2)
        self.falls.unload(1, 0, -1, [])
        self.assertIsNone(self.land(2))
        self.start(3)
        self.falls.discard(1, 3)
        self.assertIsNone(self.land(3))
        self.start(4)
        self.falls.expire(15)
        self.assertIsNone(self.land(4))
        self.assertFalse(self.world.writes)

    def test_no_height_change_unloaded_target_and_container(self):
        self.start(1)
        self.assertIsNone(self.land(1, pos=(15, 69, -1)))
        self.start(2)
        self.assertIsNone(self.land(2, pos=(16, 64, -1)))
        self.world.cells[1, (15, 63, -1)] = "minecraft:chest"
        self.start(3)
        self.assertIsNone(self.land(3))
        self.assertFalse(self.world.writes)

    def test_unrelated_chunk_and_dimension_do_not_consume_fall(self):
        self.start(9)
        self.falls.unload(0, 0, -1, [9])
        self.falls.unload(1, 1, -1, [])
        self.assertEqual("minecraft:gravel", self.land(9))

    def test_different_landing_material_does_not_settle(self):
        self.start(5)
        self.assertIsNone(self.falls.land(1, 5, "minecraft:sand", (15, 64, -1)))
        self.assertIsNone(self.land(5))
