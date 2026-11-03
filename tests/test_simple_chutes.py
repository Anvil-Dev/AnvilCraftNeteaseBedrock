# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""回放简易溜槽的连接转换、独立转发、含水和存档恢复。"""

import copy
import unittest

from test_drop_work import GroundItem, LOG
from test_magnet_logistics import Factory
from anvilcraft_scripts.common.drop_recipes import STAMP
from anvilcraft_scripts.common.logistics import (
    CHUTE, CHUTE_DOWN, COOLDOWN_KEY, MAGNETIC_CHUTE, SIMPLE_CHUTE,
    SIMPLE_DOWN, SIMPLE_TALL, SIMPLE_TALL_DOWN,
)
from anvilcraft_scripts.server.impact_events import ImpactEvents


class SimpleChuteTests(unittest.TestCase):

    def setUp(self):
        self.world = Factory()
        self.pos, self.above = (0, 63, 0), (0, 64, 0)
        self.bind()

    def bind(self):
        self.events = ImpactEvents(self.world, LOG)
        self.events.listen(self.world)
        self.work = self.events._logistics
        self.inventory = self.events._stations.inventory

    def cell(self, pos, name, facing=0):
        self.world.cells[0, pos] = name
        self.world.aux[0, pos] = facing
        self.world.cell_states.pop((0, pos), None)

    def items(self, pos=None):
        return self.inventory.get(0, pos or self.pos)["items"]

    def item(self, name="diamond", count=3):
        return dict(newItemName="minecraft:" + name, newAuxValue=0, count=count, extraId="kept")

    def record(self, items, pos=None, **settings):
        self.inventory.write(
            0, pos or self.pos, dict(settings, items=copy.deepcopy(items), logistics=True))

    def frame(self, positions=None, count=1):
        for _ in range(count):
            self.events._tick += 2
            self.events._stations.tick = self.events._tick
            for pos in positions or [self.pos]:
                self.work.block_tick(dict(blockName=self.world.cells[0, pos], dimension=0,
                                          posX=pos[0], posY=pos[1], posZ=pos[2]))

    def chest(self, pos, contents=None):
        self.cell(pos, "minecraft:chest")
        self.world.containers[0, pos] = copy.deepcopy(contents or [None] * 9)

    def test_connection_converts_both_ways_without_refunding_inventory(self):
        self.cell(self.pos, CHUTE)
        self.cell(self.above, CHUTE)
        self.cell((0, 62, 0), "minecraft:stone")
        self.record([self.item()], filter=["minecraft:diamond", 0])
        self.world.GetBlockEntityData(0, self.pos)[COOLDOWN_KEY] = 5
        self.frame()
        self.assertEqual(SIMPLE_TALL_DOWN, self.world.cells[0, self.pos])
        self.assertEqual([self.item()], self.items())
        self.assertNotIn("filter", self.inventory.get(0, self.pos))
        self.assertFalse(self.world.drops)
        self.cell(self.above, "minecraft:air")
        self.frame()
        self.assertEqual(CHUTE_DOWN, self.world.cells[0, self.pos])
        self.assertEqual([self.item()], self.items())
        self.assertFalse(self.world.drops)

    def test_magnetic_input_uses_low_head_and_ordinary_above_uses_tall_head(self):
        self.cell(self.pos, CHUTE, 5)
        self.cell((-1, 63, 0), MAGNETIC_CHUTE, 5)
        self.frame()
        self.assertEqual(SIMPLE_CHUTE, self.world.cells[0, self.pos])
        self.cell(self.above, MAGNETIC_CHUTE, 0)
        self.frame()
        self.assertEqual(SIMPLE_CHUTE, self.world.cells[0, self.pos])
        self.cell(self.above, CHUTE, 0)
        self.frame()
        self.assertEqual(SIMPLE_TALL, self.world.cells[0, self.pos])

    def test_placement_selects_simple_shape_before_world_changes(self):
        self.cell(self.above, CHUTE)
        event = dict(fullName=CHUTE, face=1, auxData=2, entityId="player", dimensionId=0,
                     x=0, y=63, z=0)
        self.work.place(event)
        self.assertEqual((SIMPLE_TALL_DOWN, 0), (event["fullName"], event["auxData"]))

    def test_simple_input_does_not_merge_and_legacy_slots_are_preserved(self):
        self.cell(self.pos, SIMPLE_CHUTE, 5)
        source = (-1, 63, 0)
        self.cell(source, CHUTE, 5)
        self.record([self.item("iron_ingot", 4)], source)
        self.record([self.item("iron_ingot", 2)])
        self.assertEqual(0, self.work._move(0, source, self.pos))
        self.assertEqual(2, self.items()[0]["count"])
        self.record([self.item("diamond", 7)], simple_first=False)
        self.assertEqual(4, self.work._move(0, source, self.pos))
        self.assertEqual([self.item("iron_ingot", 4), self.item("diamond", 7)], self.items())

    def test_simple_does_not_suck_input_container_or_accept_manual_inventory_use(self):
        self.cell(self.pos, SIMPLE_CHUTE, 5)
        self.cell((-1, 63, 0), CHUTE, 5)
        self.chest(self.above, [self.item("gold_ingot", 9)])
        self.world.carried = self.item("stone", 2)
        self.work.use(dict(blockName=SIMPLE_CHUTE, playerId="player", dimensionId=0,
                           x=0, y=63, z=0, face=1))
        self.frame(count=16)
        self.assertFalse(self.items())
        self.assertEqual(2, self.world.carried["count"])
        self.assertEqual(9, self.world.containers[0, self.above][0]["count"])

    def test_simple_collision_collects_and_forwards_despite_redstone(self):
        self.cell(self.pos, SIMPLE_CHUTE, 5)
        self.cell((-1, 63, 0), CHUTE, 5)
        target = (1, 63, 0)
        self.chest(target)
        self.world.power.add((0, self.pos))
        self.world.drops["input"] = GroundItem("minecraft:diamond", 3, (0.5, 63.4, 0.5), 0)
        event = dict(blockName=SIMPLE_CHUTE, blockX=0, blockY=63, blockZ=0, entityId="input")
        self.work.inside(event)
        self.assertNotIn("input", self.world.drops)
        self.frame(count=7)
        self.assertIsNone(self.world.containers[0, target][0])
        self.frame()
        self.assertEqual(3, self.world.containers[0, target][0]["count"])
        self.assertFalse(self.items())

    def test_pipeline_delay_is_independent_of_block_tick_order(self):
        for source_first in (True, False):
            self.world = Factory()
            self.bind()
            source, target = (-1, 63, 0), (1, 63, 0)
            self.cell(source, CHUTE, 5)
            self.cell(self.pos, SIMPLE_CHUTE, 5)
            self.chest(target)
            self.record([self.item()], source)
            order = [source, self.pos] if source_first else [self.pos, source]
            self.frame(order, 6)
            self.assertIsNone(self.world.containers[0, target][0])
            self.frame(order)
            self.assertEqual([self.item()], [self.world.containers[0, target][0]])

    def test_failed_conversion_recovers_after_reload_without_items_dropping(self):
        self.cell(self.pos, CHUTE)
        self.cell(self.above, CHUTE)
        self.record([self.item()])
        self.world.refuse_cells.add((0, self.pos))
        self.frame()
        self.assertEqual(CHUTE, self.world.cells[0, self.pos])
        self.assertEqual([self.item()], self.items())
        self.world.refuse_cells.clear()
        self.bind()
        self.frame()
        self.assertEqual(SIMPLE_TALL_DOWN, self.world.cells[0, self.pos])
        self.assertEqual([self.item()], self.items())
        self.assertFalse(self.world.drops)

    def test_water_and_cooldown_survive_height_change_and_reload(self):
        self.cell(self.pos, SIMPLE_DOWN)
        self.cell((-1, 63, 0), CHUTE, 5)
        self.record([self.item()])
        water = {"name": "minecraft:water", "aux": 0}
        self.world.liquids[0, self.pos] = water
        self.world.GetBlockEntityData(0, self.pos)[COOLDOWN_KEY] = 5
        self.cell(self.above, CHUTE)
        self.frame()
        self.assertEqual(SIMPLE_TALL_DOWN, self.world.cells[0, self.pos])
        self.assertEqual(water, self.world.liquids[0, self.pos])
        self.bind()
        self.frame()
        self.assertEqual([self.item()], self.items())
        self.assertEqual(3, self.world.GetBlockEntityData(0, self.pos)[COOLDOWN_KEY])

    def test_unloaded_neighbour_does_not_restore_a_disconnected_shape(self):
        self.cell(self.pos, SIMPLE_TALL_DOWN)
        self.record([self.item()])
        self.world.unloaded.add((0, self.above))
        self.frame()
        self.assertEqual(SIMPLE_TALL_DOWN, self.world.cells[0, self.pos])
        self.assertEqual([self.item()], self.items())

    def test_middle_pick_normalizes_helper_item_without_overwriting_a_changed_slot(self):
        item = dict(newItemName=SIMPLE_TALL_DOWN, newAuxValue=5, count=2, extraId="picked")
        event = dict(playerId="player", slot=2, newItemDict=item)
        self.world.callbacks["InventoryItemChangedServerEvent"](event)
        self.work.advance(1)
        self.assertNotIn(2, self.world.player_inventory)
        self.world.player_inventory[2] = item
        self.world.callbacks["InventoryItemChangedServerEvent"](event)
        self.work.advance(2)
        self.assertEqual(
            dict(item, newItemName=CHUTE, newAuxValue=0), self.world.player_inventory[2])
        self.world.callbacks["InventoryItemChangedServerEvent"](event)
        self.world.player_inventory[2] = self.item("stone")
        self.work.advance(3)
        self.assertEqual(self.item("stone"), self.world.player_inventory[2])

    def test_neighbour_change_event_restores_regular_chute_without_a_block_tick(self):
        self.cell(self.pos, SIMPLE_TALL_DOWN)
        self.record([self.item()])
        self.world.callbacks["BlockNeighborChangedServerEvent"](dict(
            blockName=SIMPLE_TALL_DOWN, dimensionId=0, posX=0, posY=63, posZ=0))
        self.work.advance(1)
        self.assertEqual(CHUTE_DOWN, self.world.cells[0, self.pos])
        self.assertEqual([self.item()], self.items())

    def test_rotation_into_an_incoming_outlet_breaks_once_and_returns_regular_item(self):
        self.cell(self.pos, SIMPLE_CHUTE, 5)
        self.cell((-1, 63, 0), CHUTE, 5)
        self.record([self.item()])
        self.world.sneaking = True
        self.work.use(dict(blockName=SIMPLE_CHUTE, playerId="player", dimensionId=0,
                           x=0, y=63, z=0, face=4))
        self.assertEqual("minecraft:air", self.world.cells[0, self.pos])
        output = [row.item for row in self.world.drops.values()]
        self.assertIn(self.item(), output)
        self.assertEqual(1, sum(row["count"] for row in output if row["newItemName"] == CHUTE))
        self.assertFalse(self.items())

    def test_collision_at_side_gap_is_not_collected(self):
        self.cell(self.pos, SIMPLE_CHUTE, 5)
        self.cell((-1, 63, 0), CHUTE, 5)
        self.world.drops["gap"] = GroundItem("minecraft:diamond", 3, (0.05, 63.1, 0.05), 0)
        self.work.inside(dict(blockName=SIMPLE_CHUTE, blockX=0, blockY=63, blockZ=0,
                              entityId="gap"))
        self.assertIn("gap", self.world.drops)
        self.assertFalse(self.items())

    def test_conversion_preserves_world_changes_during_inventory_save(self):
        self.cell(self.pos, CHUTE)
        self.cell(self.above, CHUTE)
        self.record([self.item()])
        original = self.world.SetExtraData
        fired = [False]
        def save(key, value, sync):
            result = original(key, value, sync)
            if key == "anvilcraft:machine_inventories_v1" and not fired[0]:
                fired[0] = True
                self.cell(self.pos, "minecraft:stone")
            return result
        self.world.SetExtraData = save
        self.frame()
        self.assertEqual("minecraft:stone", self.world.cells[0, self.pos])
        self.work.advance(30)
        self.assertEqual([self.item()], [row.item for row in self.world.drops.values()])

    def test_conversion_preserves_rotation_during_inventory_save(self):
        self.cell(self.pos, CHUTE)
        self.cell(self.above, CHUTE)
        self.record([self.item()])
        original = self.world.SetExtraData
        fired = [False]
        def save(key, value, sync):
            result = original(key, value, sync)
            if key == "anvilcraft:machine_inventories_v1" and not fired[0]:
                fired[0] = True
                self.cell(self.pos, CHUTE, 2)
            return result
        self.world.SetExtraData = save
        self.frame()
        self.assertEqual([self.item()], self.items())
        self.frame()
        self.assertEqual(SIMPLE_TALL, self.world.cells[0, self.pos])
        self.assertEqual(2, self.world.aux[0, self.pos])
        self.assertEqual([self.item()], self.items())

    def test_restoring_regular_keeps_one_group_and_spills_other_slots(self):
        self.cell(self.pos, SIMPLE_DOWN)
        first, second = self.item("iron_ingot", 60), self.item("iron_ingot", 10)
        other, tagged = self.item("diamond", 3), dict(self.item("iron_ingot", 4), extraId="other")
        self.record([first, second, other, tagged])
        self.work._forms.update(0, self.pos)
        self.assertEqual(CHUTE_DOWN, self.world.cells[0, self.pos])
        self.assertEqual([dict(first, count=64)], self.items())
        dropped = [row.item for row in self.world.drops.values()]
        self.assertEqual(3, len(dropped))
        for item in (dict(second, count=6), other, tagged):
            self.assertIn(item, dropped)
        self.bind()
        self.work.advance(1)
        self.assertEqual(3, len(self.world.drops))
        self.assertNotIn("form_token", self.inventory.get(0, self.pos))

    def test_spill_save_failure_retries_confirmation_without_spawning_again(self):
        self.cell(self.pos, SIMPLE_DOWN)
        self.record([self.item("diamond"), self.item("gold_ingot", 7)])
        original = self.world.SetExtraData
        failed = [False]
        def save(key, value, sync):
            if key == "anvilcraft:chute_forms_v1" and not failed[0] and any(
                    row.get("phase") == "spilled" for row in value.values()):
                failed[0] = True
                return False
            return original(key, value, sync)
        self.world.SetExtraData = save
        self.assertIsNone(self.work._forms.update(0, self.pos))
        self.assertEqual(1, len(self.world.drops))
        self.work._forms.update(0, self.pos)
        self.assertEqual(1, len(self.world.drops))
        self.assertEqual([self.item("diamond")], self.items())
        self.assertNotIn("form_token", self.inventory.get(0, self.pos))

    def test_unknown_spill_after_reload_preserves_receipt_and_never_duplicates(self):
        self.cell(self.pos, SIMPLE_DOWN)
        self.record([self.item("diamond"), self.item("gold_ingot", 7)])
        original = self.world.SetExtraData
        def save(key, value, sync):
            if key == "anvilcraft:chute_forms_v1" and any(
                    row.get("phase") == "spilled" for row in value.values()):
                return False
            return original(key, value, sync)
        self.world.SetExtraData = save
        self.work._forms.update(0, self.pos)
        self.assertEqual(1, len(self.world.drops))
        self.world.SetExtraData = original
        self.bind()
        self.frame(count=3)
        self.assertEqual(1, len(self.world.drops))
        self.assertEqual([self.item("diamond")], self.items())
        self.assertIn("form_token", self.inventory.get(0, self.pos))

    def test_new_water_during_receipt_save_is_preserved(self):
        self.cell(self.pos, SIMPLE_DOWN)
        self.cell(self.above, CHUTE)
        water = {"name": "minecraft:water", "aux": 0}
        original = self.world.SetExtraData
        changed = [False]
        def save(key, value, sync):
            result = original(key, value, sync)
            if key == "anvilcraft:chute_forms_v1" and not changed[0]:
                changed[0] = True
                self.world.liquids[0, self.pos] = water
            return result
        self.world.SetExtraData = save
        self.frame()
        self.assertEqual(SIMPLE_TALL_DOWN, self.world.cells[0, self.pos])
        self.assertEqual(water, self.world.liquids[0, self.pos])

    def test_replacing_failed_conversion_with_a_table_preserves_reserved_spill(self):
        self.cell(self.pos, SIMPLE_DOWN)
        self.record([self.item("diamond"), self.item("gold_ingot", 7)])
        self.world.refuse_cells.add((0, self.pos))
        self.work._forms.update(0, self.pos)
        self.assertIn("form_token", self.inventory.get(0, self.pos))
        self.world.refuse_cells.clear()
        self.world.SetBlockNew(self.pos, {"name": STAMP, "aux": 0}, 0, 0)
        self.world.SetBlockNew(self.pos, {"name": "minecraft:air", "aux": 0}, 0, 0)
        self.work.advance(30)
        dropped = [row.item for row in self.world.drops.values()]
        self.assertEqual(2, len(dropped))
        self.assertIn(self.item("diamond"), dropped)
        self.assertIn(self.item("gold_ingot", 7), dropped)
        self.assertNotIn("form_token", self.inventory.get(0, self.pos))

    def test_table_cannot_consume_or_replace_a_reserved_chute_record(self):
        self.cell(self.pos, SIMPLE_DOWN)
        self.record([self.item("diamond"), self.item("gold_ingot", 7)])
        self.world.refuse_cells.add((0, self.pos))
        self.work._forms.update(0, self.pos)
        self.world.refuse_cells.clear()
        self.world.SetBlockNew(self.pos, {"name": STAMP, "aux": 0}, 0, 0)
        self.world.carried = self.item("sugar_cane", 5)
        self.events._stations.use(dict(
            blockName=STAMP, playerId="player", dimensionId=0, x=0, y=63, z=0, face=1))
        self.assertEqual(5, self.world.carried["count"])
        self.assertFalse(self.items())
        self.work.advance(30)
        self.assertNotIn("form_token", self.inventory.get(0, self.pos))

    def test_neighbour_updates_do_not_refund_a_processing_tables_inventory(self):
        table = (1, 63, 0)
        self.cell(self.pos, CHUTE)
        self.cell(table, STAMP)
        self.inventory.write(0, table, {"items": [self.item("sugar_cane", 5)]})
        self.work.changed(dict(blockName=CHUTE, dimensionId=0, posX=0, posY=63, posZ=0))
        self.work.advance(30)
        self.assertEqual([self.item("sugar_cane", 5)], self.items(table))
        self.assertFalse(self.world.drops)

    def test_collision_at_outlet_edge_uses_the_complete_item_box(self):
        self.cell(self.pos, SIMPLE_CHUTE, 4)
        self.cell((1, 63, 0), CHUTE, 4)
        self.world.drops["edge"] = GroundItem("minecraft:diamond", 3, (-0.1, 63.4, 0.5), 0)
        self.work.inside(dict(blockName=SIMPLE_CHUTE, blockX=0, blockY=63, blockZ=0,
                              entityId="edge"))
        self.assertNotIn("edge", self.world.drops)
        self.assertEqual(3, self.items()[0]["count"])


if __name__ == "__main__":
    unittest.main()
