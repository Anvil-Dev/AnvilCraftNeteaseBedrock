# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""通过落砧回调验证平台、掉落物兑换及引擎拒绝写入时的数量守恒。"""

import copy
import logging
import random
import unittest

from test_impact_events import Engine, ImpactEvents

LOG = logging.getLogger("workshop-test")
LOG.addHandler(logging.NullHandler())


class GroundItem(object):

    def __init__(self, name, count, pos, dim, **data):
        self.item = dict(data, newItemName=name, newAuxValue=0, count=count)
        self.pos = pos
        self.dim = dim

    def GetEngineTypeStr(self):
        return "minecraft:item"

    def GetEntityDimensionId(self):
        return self.dim

    def GetFootPos(self):
        return self.pos


class Workshop(Engine):

    def __init__(self):
        super(Workshop, self).__init__()
        self.drops = {}
        self.save = {}
        self.states = {}
        self.refuse = set()
        self.loaded = True
        self.allow_save = True
        self.allow_retract = True
        self.save_results = []
        self.new_ids = 0
        self.picked_up = None

    def CreateEngineType(self, entity):
        return self.drops.get(entity)

    def CreateBlock(self, level):
        return self

    def CreateBlockUseEventWhiteList(self, level):
        return self

    def AddBlockItemListenForUseEvent(self, name):
        return True

    def LookupBlocksByBlockTag(self, tag):
        return []

    def CreateDimension(self, entity):
        return self.drops.get(entity)

    def CreatePos(self, entity):
        return self.drops[entity] if entity in self.drops else self.actor

    def CreateGame(self, level):
        return self

    def CreateItem(self, level):
        return self

    def CreateBlockState(self, level):
        return self

    def CreateExtraData(self, level):
        return self

    def CreateChunkSource(self, level):
        return self

    def CheckChunkState(self, dim, pos):
        return self.loaded

    def GetExtraData(self, key):
        return copy.deepcopy(self.save.get(key))

    def SetExtraData(self, key, value, save):
        accepted = self.save_results.pop(0) if self.save_results else self.allow_save
        if accepted:
            self.save[key] = copy.deepcopy(value)
        return accepted

    def GetBlockStates(self, pos, dim):
        return self.states

    def GetEntitiesInSquareArea(self, entity, start, end, dim):
        return list(self.drops.keys())

    def GetDroppedItem(self, entity, get_user_data):
        if entity in self.drops:
            return copy.deepcopy(self.drops[entity].item)

    def DestroyEntity(self, entity):
        if entity not in self.drops or (entity.startswith("new") and not self.allow_retract):
            return False
        del self.drops[entity]
        if self.picked_up:
            self.drops.pop(self.picked_up, None)
            self.picked_up = None
        return True

    def CreateEngineItemEntity(self, item, dim, pos):
        if item["newItemName"] in self.refuse:
            return None
        self.new_ids += 1
        entity = "new" + str(self.new_ids)
        drop = GroundItem(item["newItemName"], item["count"], pos, dim)
        drop.item = copy.deepcopy(item)
        self.drops[entity] = drop
        return entity


class WorkTests(unittest.TestCase):

    def setUp(self):
        self.world = Workshop()
        self.support = (-1, 63, 1)
        self.platform("cauldron", {"fill_level": 0})
        self.bind()

    def bind(self):
        self.events = ImpactEvents(self.world, LOG)
        self.events.listen(self.world)
        self.fire = self.world.callbacks

    def platform(self, name, states):
        self.world.cells[1, self.support] = "minecraft:" + name
        self.world.states = states
        self.world.hit = {"identifier": "minecraft:" + name, "pos": self.support}

    def drop(self, entity, name, count, pos=(-0.5, 63.3125, 1.5), dim=1, **data):
        self.world.drops[entity] = GroundItem("minecraft:" + name, count, pos, dim, **data)

    def fall(self, entity="42"):
        self.fire["HeavyBlockStartFallingServerEvent"](
            dict(dimensionId=1, fallingBlockId=entity, blockName="minecraft:anvil",
                 blockX=-1, blockY=68, blockZ=1))
        land = dict(dimensionId=1, fallingBlockId=int(entity), heavyBlockName="minecraft:anvil",
                    blockX=-1, blockY=64, blockZ=1)
        self.fire["FallingBlockReturnHeavyBlockServerEvent"](land)
        self.fire["FallingBlockReturnHeavyBlockServerEvent"](land)

    def stacks(self, name):
        return [d for d in self.world.drops.itervalues()
                if d.item["newItemName"] == "minecraft:" + name]

    def test_split_bones_keep_tagged_remainder_and_ignore_neighbours(self):
        self.drop("1", "bone", 2)
        marker = {"label": {"__type__": 8, "__value__": "sample"}}
        self.drop("2", "bone", 5, userData=marker, extraId="kept")
        self.drop("3", "string", 1)
        self.drop("4", "bone", 3, pos=(0.05, 63.4, 1.5))
        self.drop("5", "bone", 3, dim=0)
        self.fall()
        self.assertEqual([2], [d.item["count"] for d in self.stacks("bone_block")])
        self.assertTrue(all(entity in self.world.drops for entity in ("3", "4", "5")))
        remainder = next(d for d in self.stacks("bone") if d.item.get("extraId") == "kept")
        self.assertEqual((1, marker), (remainder.item["count"], remainder.item["userData"]))
        self.assertEqual((-0.5, 63.3125, 1.5), remainder.pos)

    def test_state_or_count_mismatch_preserves_every_input(self):
        self.drop("1", "bone", 2)
        self.fall()
        self.assertEqual(2, self.world.drops["1"].item["count"])
        self.world.drops["1"].item["count"] = 3
        for level in (1, None):
            self.platform("cauldron", {"fill_level": level})
            self.fall()
        self.assertEqual(3, self.world.drops["1"].item["count"])
        self.drop("2", "clay", 1, pos=(-0.5, 64, 1.5))
        for upper, opened in ((False, False), (True, True), (True, None)):
            self.platform("iron_trapdoor", {"upside_down_bit": upper, "open_bit": opened})
            self.fall()
        self.assertIn("2", self.world.drops)
        self.assertFalse(self.stacks("clay_ball"))

    def test_unpack_requires_both_materials_and_selects_one_recipe(self):
        self.platform("iron_trapdoor", {"upside_down_bit": True, "open_bit": False})
        pos = (-0.5, 64, 1.5)
        self.drop("1", "honey_block", 2, pos)
        self.drop("2", "glass_bottle", 3, pos)
        self.fall()
        self.assertEqual({"1", "2"}, set(self.world.drops))
        self.drop("3", "glass_bottle", 6, pos)
        self.drop("4", "clay", 4, pos)
        self.fall()
        self.assertEqual(4, self.world.drops["4"].item["count"])
        self.assertEqual([1], [d.item["count"] for d in self.stacks("glass_bottle")])
        honey = self.stacks("honey_bottle")
        self.assertEqual([(8, (-0.5, 63, 1.5))], [(d.item["count"], d.pos) for d in honey])

    def test_multiple_stacks_respect_recipe_limit_and_output_stack_size(self):
        self.platform("iron_trapdoor", {"upside_down_bit": True, "open_bit": False})
        self.drop("1", "snow", 40, pos=(-0.5, 64, 1.5))
        self.drop("2", "snow", 25, pos=(-0.5, 64, 1.5))
        self.fall()
        self.assertEqual([16] * 16, [d.item["count"] for d in self.stacks("snowball")])
        self.assertEqual([1], [d.item["count"] for d in self.stacks("snow")])

    def test_mesh_pending_outputs_keep_the_original_rolls_after_reload(self):
        self.addCleanup(random.setstate, random.getstate())
        random.seed(0)
        self.platform("scaffolding", {})
        self.drop("1", "sand", 64, pos=(-0.5, 64, 1.5))
        self.world.refuse.update(("minecraft:sand", "minecraft:clay_ball", "minecraft:gold_nugget"))
        self.fall()
        key = "anvilcraft:pending_drops_v1"
        credit = copy.deepcopy(self.world.save[key])
        self.assertTrue(credit)
        self.assertFalse(self.world.drops)
        self.bind()
        self.fire["LoadServerAddonScriptsAfter"]({})
        random.seed(99)
        self.world.refuse.clear()
        self.world.loaded = False
        self.tick_for(30)
        self.assertFalse(self.world.drops)
        self.world.loaded = True
        self.tick_for(120)
        expected = {}
        for _, _, item in credit:
            name = item["newItemName"].split(":")[1]
            expected[name] = expected.get(name, 0) + item["count"]
        for name, count in expected.items():
            self.assertEqual(count, sum(drop.item["count"] for drop in self.stacks(name)))
            self.assertTrue(all(drop.pos == (-0.5, 63, 1.5) for drop in self.stacks(name)))
        self.assertEqual([], self.world.save[key])

    def test_mesh_zero_output_still_consumes_one_recipe_per_native_landing(self):
        self.addCleanup(random.setstate, random.getstate())
        random.seed(0)
        self.platform("scaffolding", {})
        self.drop("1", "gravel", 1, pos=(-0.5, 64, 1.5))
        self.drop("2", "oak_leaves", 1, pos=(-0.5, 64, 1.5))
        for entity in ("41", "42"):
            self.fire["AddEntityServerEvent"](dict(
                id=entity, engineTypeStr="minecraft:falling_block",
                posX=-0.5, posY=68.5, posZ=1.5, dimensionId=1))
        self.world.actor.feet = (-0.5, 64.1, 1.5)
        self.fire["OnScriptTickServer"]()
        self.world.cells[1, (-1, 64, 1)] = "minecraft:anvil"
        for entity in ("41", "42"):
            self.fire["EntityRemoveEvent"]({"id": entity})
        self.tick_for(90)
        self.assertNotIn("1", self.world.drops)
        self.assertEqual(["2"], self.world.drops.keys())
        self.assertEqual(1, self.world.drops["2"].item["count"])
        self.assertFalse(self.world.save.get("anvilcraft:pending_drops_v1"))

    def test_iron_compresses_and_unpacks_one_step_per_fall(self):
        self.drop("1", "iron_ingot", 8)
        self.fall()
        self.assertIn("1", self.world.drops)
        self.drop("2", "iron_ingot", 11)
        self.drop("3", "string", 4)
        self.fall()
        self.assertEqual([2], [d.item["count"] for d in self.stacks("iron_block")])
        self.assertEqual([1], [d.item["count"] for d in self.stacks("iron_ingot")])
        self.assertIn("3", self.world.drops)
        self.fall()
        self.assertEqual([1], [d.item["count"] for d in self.stacks("white_wool")])
        self.platform("iron_trapdoor", {"upside_down_bit": True, "open_bit": False})
        self.stacks("iron_block")[0].pos = (-0.5, 64, 1.5)
        self.fall()
        self.assertItemsEqual([18, 1], [d.item["count"] for d in self.stacks("iron_ingot")])
        self.assertFalse(self.stacks("iron_nugget"))

    def test_tagged_wood_variants_share_a_recipe(self):
        self.platform("iron_trapdoor", {"upside_down_bit": True, "open_bit": False})
        pos = (-0.5, 64, 1.5)
        self.drop("1", "stripped_oak_wood", 2, pos)
        self.drop("2", "oak_log", 1, pos)
        self.drop("3", "spruce_log", 1, pos)
        self.fall()
        self.assertEqual([12], [d.item["count"] for d in self.stacks("oak_planks")])
        self.assertIn("3", self.world.drops)

    def test_minecart_parts_and_failed_second_output(self):
        self.platform("iron_trapdoor", {"upside_down_bit": True, "open_bit": False})
        pos = (-0.5, 64, 1.5)
        contents = {"Items": {"__type__": 9, "__value__": [{"Name": "minecraft:diamond"}]}}
        self.drop("storage", "chest_minecart", 1, pos, userData={"EntityTag": contents})
        self.drop("sealed", "hopper_minecart", 1, pos, userData={"custom:storage": contents})
        self.drop("1", "chest_minecart", 1, pos, userData={"display": {"Name": "named"}})
        self.drop("2", "chest_minecart", 1, pos)
        self.drop("3", "hopper_minecart", 1, pos)
        self.drop("4", "tnt_minecart", 1, pos)
        self.drop("5", "acacia_log", 1, pos)
        self.world.refuse.add("minecraft:chest")
        self.fall()
        self.assertEqual([1, 1], [d.item["count"] for d in self.stacks("minecart")])
        self.assertFalse(self.stacks("chest"))
        self.assertTrue(all(k in self.world.drops for k in ("3", "4", "5", "storage")))
        self.bind()
        self.world.refuse.clear()
        self.fall("43")
        self.tick_for(60)
        self.assertEqual([2], [d.item["count"] for d in self.stacks("chest")])
        self.assertEqual([1], [d.item["count"] for d in self.stacks("hopper")])
        self.fall("44")
        self.assertEqual([1], [d.item["count"] for d in self.stacks("tnt")])
        self.assertEqual([1] * 4, [d.item["count"] for d in self.stacks("minecart")])
        self.assertEqual(contents, self.world.drops["storage"].item["userData"]["EntityTag"])
        self.assertEqual(contents, self.world.drops["sealed"].item["userData"]["custom:storage"])
        self.assertIn("5", self.world.drops)

    def test_legacy_melon_credit_and_new_unpack_use_current_item_id(self):
        key = "anvilcraft:pending_drops_v1"
        self.world.save[key] = [[1, list(self.support), {"newItemName": "minecraft:melon",
                                                          "newAuxValue": 0, "count": 9}]]
        self.platform("iron_trapdoor", {"upside_down_bit": True, "open_bit": False})
        self.drop("1", "melon_block", 1, pos=(-0.5, 64, 1.5))
        self.fall()
        self.tick_for(60)
        self.assertEqual([9, 9], [d.item["count"] for d in self.stacks("melon_slice")])
        self.assertEqual([], self.world.save[key])

    def test_one_vanilla_landing_cannot_unpack_a_second_recipe(self):
        self.platform("iron_trapdoor", {"upside_down_bit": True, "open_bit": False})
        self.drop("1", "clay", 1, pos=(-0.5, 64, 1.5))
        self.drop("2", "snow", 1, pos=(-0.5, 64, 1.5))
        for entity in ("41", "42"):
            self.fire["AddEntityServerEvent"](dict(
                id=entity, engineTypeStr="minecraft:falling_block",
                posX=-0.5, posY=68.5, posZ=1.5, dimensionId=1))
        self.world.actor.feet = (-0.5, 64.1, 1.5)
        self.fire["OnScriptTickServer"]()
        self.world.cells[1, (-1, 64, 1)] = "minecraft:chipped_anvil"
        for entity in ("41", "42"):
            self.fire["EntityRemoveEvent"]({"id": entity})
        self.fire["OnScriptTickServer"]()
        self.assertEqual([4], [d.item["count"] for d in self.stacks("clay_ball")])
        self.assertIn("2", self.world.drops)
        self.assertFalse(self.stacks("snowball"))

    def test_mid_exchange_pickup_refunds_only_items_already_removed(self):
        self.drop("1", "bone", 1, extraId="refund")
        self.drop("2", "bone", 2)
        self.world.picked_up = "2"
        self.fall()
        self.assertFalse(self.stacks("bone_block"))
        self.assertEqual([(1, "refund")],
                         [(d.item["count"], d.item.get("extraId")) for d in self.stacks("bone")])

    def test_failed_output_is_delivered_once_after_reload(self):
        self.drop("1", "bone", 4)
        self.world.refuse.add("minecraft:bone_block")
        self.fall()
        self.assertEqual([1], [d.item["count"] for d in self.stacks("bone")])
        self.assertFalse(self.stacks("bone_block"))
        self.bind()
        self.fall("43")
        self.world.refuse.clear()
        self.world.loaded = False
        self.tick_for(30)
        self.world.loaded, self.world.allow_save = True, False
        self.tick_for(30)
        self.assertFalse(self.stacks("bone_block"))
        self.world.allow_save = True
        self.tick_for(60)
        self.assertEqual([1], [d.item["count"] for d in self.stacks("bone_block")])
        self.assertEqual([1], [d.item["count"] for d in self.stacks("bone")])

    def tick_for(self, ticks):
        for _ in range(ticks):
            self.fire["OnScriptTickServer"]()

    def test_failed_retry_keeps_original_credit_across_sessions(self):
        self.drop("1", "bone", 3)
        self.world.refuse.add("minecraft:bone_block")
        self.fall()
        # 库存服务继续拒绝生成，下一次存档写入也会失败。
        self.world.save_results = [True, False]
        self.tick_for(30)
        self.assertFalse(self.stacks("bone_block"))
        self.bind()
        self.fall("43")
        self.world.refuse.clear()
        self.tick_for(90)
        self.assertEqual([1], [d.item["count"] for d in self.stacks("bone_block")])

    def test_failed_commit_retracts_the_output_before_retry(self):
        self.drop("1", "bone", 3)
        self.world.refuse.add("minecraft:bone_block")
        self.fall()
        self.world.refuse.clear()
        self.world.save_results = [True, False]
        self.tick_for(30)
        self.assertFalse(self.stacks("bone_block"))
        self.bind()
        self.fall("43")
        self.tick_for(60)
        self.assertEqual([1], [d.item["count"] for d in self.stacks("bone_block")])

    def test_world_close_saves_an_issued_drop_when_retraction_was_refused(self):
        self.drop("1", "bone", 3)
        self.world.refuse.add("minecraft:bone_block")
        self.fall()
        self.world.refuse.clear()
        self.world.save_results = [True, False]
        self.world.allow_retract = False
        self.tick_for(30)
        self.assertEqual([1], [d.item["count"] for d in self.stacks("bone_block")])
        self.events.close()
        self.bind()
        self.fall("43")
        self.tick_for(30)
        self.assertEqual([1], [d.item["count"] for d in self.stacks("bone_block")])
