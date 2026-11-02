# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""按 3.10 的事件签名回放同一铁砧从实体还原为方块的过程。"""

import logging
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "behavior_pack"))
from anvilcraft_scripts.server.impact_events import ImpactEvents


class Actor(object):

    def __init__(self, material):
        self.nbt = {"FallingBlock": {"name": material}}
        self.feet = (-0.5, 67, 1.5)

    def GetFootPos(self):
        return self.feet

    def GetEntityNBTTags(self):
        return self.nbt


class Engine(object):
    """只提供回放用到的引擎读数，事件顺序与射线命中由用例指定。"""

    class RayFilterType(object):
        OnlyBlocks = 2

    def __init__(self):
        self.callbacks = {}
        self.actor = Actor("minecraft:anvil")
        self.cells = {(1, (-1, 63, 1)): "minecraft:cobblestone"}
        self.hit = {"identifier": "minecraft:cobblestone", "pos": (-1, 63, 1)}
        self.writes = []
        self.liquids = {}

    def ListenForEvent(self, namespace, system, name, listener, callback):
        self.callbacks[name] = callback

    def GetEngineCompFactory(self):
        return self

    def GetLevelId(self):
        return "level"

    def GetEngineNamespace(self):
        return "Minecraft"

    def GetEngineSystemName(self):
        return "Engine"

    def GetMinecraftEnum(self):
        return self

    def CreateBlockInfo(self, level):
        return self

    def CreateEntityDefinitions(self, entity):
        return self.actor

    def CreatePos(self, entity):
        return self.actor

    def GetIntPos(self, pos):
        return tuple(int(math.floor(value)) for value in pos)

    def getEntitiesOrBlockFromRay(self, dimension, pos, direction, distance, through, kind):
        return [self.hit] if self.hit is not None else None

    def GetBlockNew(self, pos, dimension):
        return {"name": self.cells.get((dimension, pos), "minecraft:air")}

    def SetBlockNew(self, pos, block, mode, dimension, legacy=True, updateNeighbors=True):
        self.writes.append((dimension, pos, block["name"]))
        self.cells[dimension, pos] = block["name"]
        return True

    def GetLiquidBlock(self, pos, dimension):
        value = self.liquids.get((dimension, pos))
        return dict(value) if value else None

    def SetLiquidBlock(self, pos, block, dimension):
        self.liquids[dimension, pos] = dict(block)
        return True


class ImpactEventTests(unittest.TestCase):

    def setUp(self):
        self.world = Engine()
        self.events = ImpactEvents(self.world, logging.getLogger("impact-test"))
        self.events.listen(self.world)
        self.fire = self.world.callbacks
        self.tick = self.fire["OnScriptTickServer"]
        self.placed = (1, (-1, 64, 1))
        self.floor = (1, (-1, 63, 1))
        self.land = dict(fallingBlockId=42, heavyBlockName="minecraft:anvil",
                         blockX=-1, blockY=64, blockZ=1, dimensionId=1)

    def spawn(self, entity="42"):
        self.fire["AddEntityServerEvent"](dict(id=entity, engineTypeStr="minecraft:falling_block",
                                               posX=-0.5, posY=70.5, posZ=1.5, dimensionId=1))

    def remove(self, entity="42"):
        self.fire["EntityRemoveEvent"]({"id": entity})

    def test_vanilla_without_heavy_events_and_no_argument_tick(self):
        self.spawn()
        self.tick()
        self.remove()
        self.tick()
        self.assertFalse(self.world.writes)
        self.world.cells[self.placed] = "minecraft:chipped_anvil"
        self.tick()
        self.fire["FallingBlockReturnHeavyBlockServerEvent"](self.land)
        self.remove()
        self.tick()
        self.assertEqual([(1, (-1, 63, 1), "minecraft:gravel")], self.world.writes)

    def test_gravity_event_first_and_tagged_nbt(self):
        self.world.actor.nbt = {"FallingBlock": {"__type__": 10, "__value__": {
            "name": {"__type__": 8, "__value__": "minecraft:anvil"}}}}
        self.spawn()
        self.world.cells[self.placed] = "minecraft:anvil"
        self.fire["FallingBlockReturnHeavyBlockServerEvent"](self.land)
        self.remove()
        self.tick()
        self.assertEqual(1, len(self.world.writes))

    def test_existing_anvil_or_different_falling_material(self):
        self.world.cells[self.placed] = "minecraft:anvil"
        self.world.hit = {"identifier": "minecraft:anvil", "pos": self.placed[1]}
        self.spawn()
        self.remove()
        self.tick()
        self.tick()
        self.world.actor.nbt = {"FallingBlock": {"name": "minecraft:sand"}}
        self.world.hit = {"identifier": "minecraft:cobblestone", "pos": self.floor[1]}
        self.spawn()
        self.remove()
        self.tick()
        self.assertFalse(self.world.writes)

    def test_broken_or_unloaded_fall_cannot_settle_later(self):
        self.spawn()
        self.remove()
        for _ in range(3):
            self.tick()
        self.world.cells[self.placed] = "minecraft:anvil"
        self.tick()
        self.assertFalse(self.world.writes)
        self.spawn()
        self.fire["ChunkAcquireDiscardedServerEvent"](dict(dimension=1, chunkPosX=-1,
                                                          chunkPosZ=0, entities=["42"]))
        self.remove()
        self.tick()
        self.assertFalse(self.world.writes)

    def test_anvil_placed_under_another_mid_fall_is_not_its_landing(self):
        self.spawn()
        self.world.cells[self.placed] = "minecraft:anvil"
        self.world.hit = {"identifier": "minecraft:anvil", "pos": self.placed[1]}
        self.tick()
        self.remove()
        self.tick()
        self.assertFalse(self.world.writes)

    def test_removing_an_actor_in_the_air_does_not_process_a_new_anvil_below(self):
        self.spawn()
        self.world.actor.feet = (-0.5, 69.9, 1.5)
        self.tick()
        self.world.cells[self.placed] = "minecraft:anvil"
        self.remove()
        self.tick()
        self.assertFalse(self.world.writes)

    def test_two_removed_entities_cannot_claim_one_block_twice(self):
        self.spawn("41")
        self.spawn("42")
        self.world.actor.feet = (-0.5, 64.15, 1.5)
        self.tick()
        self.remove("41")
        self.remove("42")
        self.world.cells[self.placed] = "minecraft:damaged_anvil"
        self.tick()
        self.assertEqual([(1, (-1, 63, 1), "minecraft:gravel")], self.world.writes)

    def test_regular_stone_has_no_crushing_recipe(self):
        self.world.cells[self.floor] = "minecraft:stone"
        self.world.hit = {"identifier": "minecraft:stone", "pos": self.floor[1]}
        self.spawn()
        self.world.actor.feet = (-0.5, 64.125, 1.5)
        self.fire["OnGroundServerEvent"]({"id": "42"})
        self.world.cells[self.placed] = "minecraft:anvil"
        self.remove()
        self.tick()
        self.assertFalse(self.world.writes)
