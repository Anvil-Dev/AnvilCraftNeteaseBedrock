# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""回放加工台的五面改装、库存保存、落砧结算与失败退款。"""

import copy
import unittest

from test_drop_work import GroundItem, LOG, Workshop
from anvilcraft_scripts.common.drop_recipes import (
    ATTACHMENTS, CRUSH, SIFT, STAMP, UNPACKING, Drop, match_drops, products,
)
from anvilcraft_scripts.server.impact_events import ImpactEvents


class Player(object):
    feet = (0.5, 63, 0.5)
    dim = 0

    def GetFootPos(self):
        return self.feet

    def GetEntityDimensionId(self):
        return self.dim


class Machines(Workshop):

    class ItemPosType(object):
        CARRIED = 2

    def __init__(self):
        super(Machines, self).__init__()
        self.player = Player()
        self.carried = None
        self.refuse_hand = False
        self.refuse_block = False

    def CreatePos(self, entity):
        return self.player if entity == "player" else super(Machines, self).CreatePos(entity)

    def CreateDimension(self, entity):
        return self.player if entity == "player" else super(Machines, self).CreateDimension(entity)

    def GetPlayerItem(self, kind, slot, user_data):
        return copy.deepcopy(self.carried)

    def SpawnItemToPlayerCarried(self, item, player):
        if self.refuse_hand:
            return False
        self.carried = copy.deepcopy(item) if item["count"] else None
        return True

    def GetItemBasicInfo(self, name, aux=0):
        return {"maxStackSize": 1 if any(word in name for word in (
            "helmet", "chestplate", "leggings", "boots", "sword", "shulker_box")) else 64}

    def SetBlockNew(self, pos, block, mode, dimension, legacy=True, updateNeighbors=True):
        if self.refuse_block:
            return False
        old = self.cells.get((dimension, pos))
        if old and old.startswith("anvilcraft:"):
            self.callbacks["BlockRemoveServerEvent"](dict(
                fullName=old, dimension=dimension, x=pos[0], y=pos[1], z=pos[2]))
        return super(Machines, self).SetBlockNew(pos, block, mode, dimension, legacy, updateNeighbors)


class StationTests(unittest.TestCase):

    def setUp(self):
        self.world = Machines()
        self.pos = (0, 63, 0)
        self.world.cells[0, self.pos] = STAMP
        self.bind()

    def bind(self):
        self.events = ImpactEvents(self.world, LOG)
        self.events.listen(self.world)
        self.stations = self.events._stations

    def use(self, face=1, name=None):
        self.stations.tick += 10
        args = dict(blockName=name or self.world.cells[0, self.pos], playerId="player", dimensionId=0,
                    x=0, y=63, z=0, face=face, itemDict={"newItemName": "minecraft:grindstone"})
        self.world.callbacks["ServerBlockUseEvent"](args)
        self.assertTrue(args["cancel"])

    def held(self, name, count=1, **data):
        self.world.carried = dict(data, newItemName="minecraft:" + name, newAuxValue=0, count=count)

    def record(self):
        return self.stations.inventory.get(0, self.pos)["items"]

    def tick(self):
        name = self.world.cells[0, self.pos]
        self.world.callbacks["ServerBlockEntityTickEvent"](dict(
            blockName=name, dimension=0, posX=0, posY=63, posZ=0))

    def outputs(self, name):
        return [drop.item for drop in self.world.drops.values() if drop.item["newItemName"] == name]

    def test_all_five_faces_switch_consume_one_and_preserve_contents(self):
        self.held("iron_ingot", 8, extraId="inventory")
        self.use()
        for face in (0, 2, 3, 4, 5):
            for target, material in ATTACHMENTS.items():
                old = self.world.cells[0, self.pos]
                self.held(material.split(":")[1], 3)
                self.use(face)
                self.assertEqual(target, self.world.cells[0, self.pos])
                self.assertEqual(3 if old == target else 2, self.world.carried["count"])
                self.assertEqual("inventory", self.record()[0]["extraId"])
        self.bind()
        self.assertEqual(8, self.record()[0]["count"])

    def test_top_inserts_material_instead_of_switching_and_rejects_remote_use(self):
        self.held("grindstone", 2)
        self.use(1)
        self.assertEqual(STAMP, self.world.cells[0, self.pos])
        self.assertEqual(2, self.record()[0]["count"])
        for feet, dim, loaded in (((99, 63, 0), 0, True), ((0.5, 63, 0.5), 1, True),
                                  ((0.5, 63, 0.5), 0, False)):
            self.world.player.feet, self.world.player.dim, self.world.loaded = feet, dim, loaded
            self.held("grindstone", 2)
            self.use(2)
            self.assertEqual(STAMP, self.world.cells[0, self.pos])
            self.assertEqual(2, self.world.carried["count"])

    def test_refused_conversion_and_failed_inventory_save_return_exact_metadata(self):
        self.held("grindstone", 2, extraId="refund", userData={"marker": 7})
        self.world.refuse_block = True
        self.use(2)
        self.assertEqual(STAMP, self.world.cells[0, self.pos])
        self.assertEqual(1, self.world.carried["count"])
        self.assertEqual("refund", self.outputs("minecraft:grindstone")[0]["extraId"])
        self.world.allow_save = False
        self.held("iron_ingot", 4, userData={"marker": 8})
        self.use(1)
        self.assertEqual([], self.record())
        self.assertEqual({"marker": 8}, self.outputs("minecraft:iron_ingot")[0]["userData"])

    def test_table_caps_each_item_type_and_retains_worn_equipment_and_eight_slots(self):
        self.held("iron_ingot", 60)
        self.use()
        self.held("iron_ingot", 20, extraId="other")
        self.use()
        self.assertEqual(16, self.world.carried["count"])
        self.assertEqual(64, sum(row["count"] for row in self.record()))
        for i in range(7):
            self.held("iron_helmet", 1, userData={"Damage": i}, extraId=str(i))
            self.use()
        self.assertEqual(3, len(self.record()))
        self.assertEqual({"Damage": 0}, self.record()[-1]["userData"])
        self.held("copper_ingot", 2)
        self.use()
        self.held("gold_ingot", 2)
        self.use()
        self.held("coal", 2)
        self.use()
        self.held("bone", 2)
        self.use()
        self.held("string", 2)
        self.use()
        self.assertEqual(8, len(self.record()))
        self.held("diamond", 2)
        self.use()
        self.assertEqual(2, self.world.carried["count"])

    def test_native_landing_stamps_once_and_drops_results_below_table(self):
        self.held("sugar_cane", 3)
        self.use()
        self.world.callbacks["HeavyBlockStartFallingServerEvent"](dict(
            dimensionId=0, fallingBlockId="42", blockName="minecraft:anvil", blockX=0, blockY=69, blockZ=0))
        event = dict(dimensionId=0, fallingBlockId="42", heavyBlockName="minecraft:anvil",
                     blockX=0, blockY=64, blockZ=0)
        for _ in range(2):
            self.world.callbacks["FallingBlockReturnHeavyBlockServerEvent"](event)
        self.assertEqual([], self.record())
        self.assertEqual(3, self.outputs("minecraft:paper")[0]["count"])
        self.assertEqual(3, self.outputs("minecraft:sugar")[0]["count"])
        self.assertEqual((0.5, 63, 0.5), self.world.drops.values()[0].pos)

    def test_auto_absorption_break_return_and_reload_keep_full_item_data(self):
        dropped = GroundItem("minecraft:iron_sword", 1, (0.5, 64, 0.5), 0,
                             userData={"Damage": 99}, enchantData=[(9, 2)], extraId="kept")
        self.world.drops["old"] = dropped
        self.tick()
        self.assertNotIn("old", self.world.drops)
        self.assertEqual(dropped.item, self.record()[0])
        self.bind()
        self.world.cells[0, self.pos] = "minecraft:air"
        self.world.callbacks["BlockRemoveServerEvent"](dict(
            fullName=STAMP, dimension=0, x=0, y=63, z=0))
        self.assertEqual([], self.record())
        self.assertEqual(dropped.item, self.outputs("minecraft:iron_sword")[0])

    def test_four_modes_select_their_own_recipe_family(self):
        for platform, raw, result in ((STAMP, "iron_ingot", "heavy_weighted_pressure_plate"),
                                      (CRUSH, "bone", "bone_meal"),
                                      (SIFT, "gravel", "gravel"),
                                      (UNPACKING, "iron_block", "iron_ingot")):
            self.world.cells[0, self.pos] = platform
            self.held(raw, 1)
            self.use()
            self.stations.process(platform, 0, self.pos)
            self.assertEqual([], self.record())
            if platform != SIFT:
                self.assertTrue(self.outputs("minecraft:" + result))

    def test_empty_hand_withdrawal_stays_outside_auto_absorption(self):
        self.held("iron_ingot", 8)
        self.use()
        self.use()
        self.assertEqual([], self.record())
        self.tick()
        self.assertEqual([], self.record())
        self.assertEqual(8, self.outputs("minecraft:iron_ingot")[0]["count"])

    def test_failed_break_save_is_retried_after_reload(self):
        self.held("iron_ingot", 8)
        self.use()
        self.world.allow_save = False
        self.world.cells[0, self.pos] = "minecraft:air"
        self.stations.remove(dict(fullName=STAMP, dimension=0, x=0, y=63, z=0))
        self.world.allow_save = True
        self.bind()
        self.stations.advance(30)
        self.assertEqual([], self.record())
        self.assertEqual(8, self.outputs("minecraft:iron_ingot")[0]["count"])

    def test_break_inside_absorption_returns_existing_and_incoming_items(self):
        self.held("gold_ingot", 3)
        self.use()
        original = self.world.DestroyEntity
        def destroy(entity):
            result = original(entity)
            self.world.cells[0, self.pos] = "minecraft:air"
            self.stations.remove(dict(fullName=STAMP, dimension=0, x=0, y=63, z=0))
            return result
        self.world.DestroyEntity = destroy
        self.world.drops["old"] = GroundItem("minecraft:iron_ingot", 8, (0.5, 64, 0.5), 0)
        self.tick()
        self.assertEqual([], self.record())
        self.assertEqual(3, self.outputs("minecraft:gold_ingot")[0]["count"])
        self.assertEqual(8, self.outputs("minecraft:iron_ingot")[0]["count"])

    def test_conversion_revalidates_after_hand_debit_and_defers_water_recovery(self):
        self.held("grindstone", 2)
        original = self.world.SpawnItemToPlayerCarried
        def replace(item, player):
            result = original(item, player)
            self.world.cells[0, self.pos] = "minecraft:obsidian"
            return result
        self.world.SpawnItemToPlayerCarried = replace
        self.use(2)
        self.assertEqual("minecraft:obsidian", self.world.cells[0, self.pos])
        self.assertEqual(1, self.outputs("minecraft:grindstone")[0]["count"])
        self.world.SpawnItemToPlayerCarried = original
        self.world.cells[0, self.pos] = STAMP
        water = {"name": "minecraft:water", "aux": 0}
        self.world.liquids[0, self.pos] = water
        self.world.SetLiquidBlock = lambda *args: False
        setter = self.world.SetBlockNew
        def clear_water(*args):
            result = setter(*args)
            self.world.liquids.clear()
            return result
        self.world.SetBlockNew = clear_water
        self.held("grindstone", 2)
        self.use(2)
        self.assertEqual(water, self.stations.inventory.get(0, self.pos)["liquid"])
        self.bind()
        def set_water(pos, block, dim):
            self.world.liquids[dim, pos] = block
            return True
        self.world.SetLiquidBlock = set_water
        self.tick()
        self.assertEqual(water, self.world.liquids[0, self.pos])
        self.assertNotIn("liquid", self.stations.inventory.get(0, self.pos))

    def test_conversion_target_replaced_by_another_callback_refunds_and_broken_water_recovers(self):
        self.held("grindstone", 2)
        original = self.world.SpawnItemToPlayerCarried
        def replace(item, player):
            result = original(item, player)
            self.world.cells[0, self.pos] = CRUSH
            return result
        self.world.SpawnItemToPlayerCarried = replace
        self.use(2)
        self.assertEqual(1, self.outputs("minecraft:grindstone")[0]["count"])
        water = {"name": "minecraft:water", "aux": 0}
        self.stations.inventory.write(0, self.pos, {"items": [], "liquid": water})
        self.world.cells[0, self.pos] = "minecraft:air"
        self.world.refuse_block = True
        self.stations.remove(dict(fullName=CRUSH, dimension=0, x=0, y=63, z=0))
        self.assertEqual(water, self.stations.inventory.get(0, self.pos)["liquid"])
        self.world.refuse_block = False
        self.bind()
        self.stations.advance(30)
        self.assertEqual("minecraft:water", self.world.cells[0, self.pos])
        self.assertNotIn("liquid", self.stations.inventory.get(0, self.pos))

    def test_uniform_recycling_and_empty_shulker_safety(self):
        helmet = Drop(0, (), {"newItemName": "minecraft:iron_helmet", "count": 1,
                              "userData": {"Damage": 150}})
        batch = match_drops(CRUSH, [helmet])
        self.assertEqual([], list(products(batch, roll=lambda: 0)))
        self.assertEqual([1], [item["count"] for item in products(batch, roll=lambda: 0.5)])
        self.assertEqual([2], [item["count"] for item in products(batch, roll=lambda: 0.999)])
        for data in ({"Items": [{"Name": "minecraft:diamond", "Count": 1}]}, {"LootTable": "unknown"}):
            box = Drop(0, (), dict(newItemName="minecraft:undyed_shulker_box", count=1, userData=data))
            self.assertIsNone(match_drops(CRUSH, [box]))
        box = Drop(0, (), dict(newItemName="minecraft:undyed_shulker_box", count=1, userData={"Items": []}))
        self.assertEqual([1, 1], [item["count"] for item in products(match_drops(CRUSH, [box]), roll=lambda: 0)])


if __name__ == "__main__":
    unittest.main()
