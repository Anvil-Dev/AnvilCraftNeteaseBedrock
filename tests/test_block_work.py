# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""通过落砧事件验证双方块优先级、炼药锅流体与跨存档恢复。"""

import copy
import logging
import unittest

from test_drop_work import Workshop
from test_impact_events import ImpactEvents
from anvilcraft_scripts.common.impact import CRUSH_RESULTS
from anvilcraft_scripts.common.vanilla_catalog import BLOCK_COMPRESS, SQUEEZING

LOG = logging.getLogger("block-work-test")
LOG.addHandler(logging.NullHandler())


class BlockWorkshop(Workshop):

    def __init__(self):
        super(BlockWorkshop, self).__init__()
        self.block_states = {}
        self.block_data = {}
        self.block_results = []
        self.state_results = []
        self.state_aux = {}
        self.unloaded = set()
        self.block_changed = None
        self.state_changed = None

    def CreateBlock(self, level):
        return self

    def LookupBlocksByBlockTag(self, tag):
        return []

    def CheckChunkState(self, dim, pos):
        return self.loaded and (dim, pos) not in self.unloaded

    def GetBlockStates(self, pos, dim):
        if not self.CheckChunkState(dim, pos):
            return None
        return copy.deepcopy(self.block_states.get((dim, pos), {}))

    def GetBlockEntityData(self, dim, pos):
        default = {"PotionId": -1, "CustomColor": -1}
        return copy.deepcopy(self.block_data.get((dim, pos), default))

    def GetBlockAuxValueFromStates(self, name, states):
        value = (name, tuple(sorted(states.items())))
        if value not in self.state_aux:
            self.state_aux[value] = len(self.state_aux) + 1
        return self.state_aux[value]

    def GetBlockStatesFromAuxValue(self, name, aux):
        for (kind, states), value in self.state_aux.items():
            if name == kind and value == aux:
                return dict(states)
        return {}

    def SetBlockNew(self, pos, block, mode, dim, legacy):
        if self.block_results and not self.block_results.pop(0):
            return False
        self.block_states[dim, pos] = self.GetBlockStatesFromAuxValue(block["name"], block["aux"])
        changed = super(BlockWorkshop, self).SetBlockNew(pos, block, mode, dim, legacy)
        if self.block_changed:
            callback = self.block_changed
            self.block_changed = None
            callback()
        return changed

    def SetBlockStates(self, pos, states, dim):
        if self.state_results and not self.state_results.pop(0):
            return False
        self.block_states[dim, pos] = copy.deepcopy(states)
        if self.state_changed:
            callback = self.state_changed
            self.state_changed = None
            callback()
        return True


class BlockWorkTests(unittest.TestCase):

    def setUp(self):
        self.world = BlockWorkshop()
        self.upper = (-1, 63, 1)
        self.lower = (-1, 62, 1)
        self.bind()

    def bind(self):
        self.events = ImpactEvents(self.world, LOG)
        self.events.listen(self.world)
        self.fire = self.world.callbacks
        self.fire["LoadServerAddonScriptsAfter"]({})

    def put(self, pos, name, **states):
        self.world.cells[1, pos] = "minecraft:" + name
        self.world.block_states[1, pos] = states

    def fall(self, pos=None, entity="42"):
        pos = pos or self.upper
        self.fire["HeavyBlockStartFallingServerEvent"](dict(
            dimensionId=1, fallingBlockId=entity, blockName="minecraft:anvil",
            blockX=pos[0], blockY=pos[1] + 5, blockZ=pos[2]))
        args = dict(dimensionId=1, fallingBlockId=int(entity), heavyBlockName="minecraft:anvil",
                    blockX=pos[0], blockY=pos[1] + 1, blockZ=pos[2])
        self.fire["FallingBlockReturnHeavyBlockServerEvent"](args)
        self.fire["FallingBlockReturnHeavyBlockServerEvent"](args)

    def tick(self, count=30):
        for _ in range(count):
            self.fire["OnScriptTickServer"]()

    def test_every_compression_variant_consumes_two_placed_blocks(self):
        for _, uppers, lowers, result in BLOCK_COMPRESS:
            for upper in uppers:
                self.put(self.upper, upper.split(":")[1], persistent_bit=True)
                self.put(self.lower, lowers[0].split(":")[1])
                self.fall()
                self.assertEqual("minecraft:air", self.world.cells[1, self.upper], upper)
                self.assertEqual(result, self.world.cells[1, self.lower], upper)

    def test_compression_precedes_crushing_and_failed_write_does_not_fall_through(self):
        CRUSH_RESULTS["minecraft:stone"] = "minecraft:cobblestone"
        self.addCleanup(CRUSH_RESULTS.pop, "minecraft:stone")
        self.put(self.upper, "stone")
        self.put(self.lower, "stone")
        self.world.block_results = [True, False, True]
        self.fall()
        self.assertEqual("minecraft:stone", self.world.cells[1, self.upper])
        self.assertEqual("minecraft:stone", self.world.cells[1, self.lower])
        self.fall()
        self.assertEqual("minecraft:air", self.world.cells[1, self.upper])
        self.assertEqual("minecraft:deepslate", self.world.cells[1, self.lower])

    def test_order_wrong_base_and_unloaded_base_preserve_materials(self):
        self.put(self.upper, "dirt")
        self.put(self.lower, "moss_block")
        self.fall()
        self.assertFalse(self.world.writes)
        self.put(self.upper, "ice")
        self.put(self.lower, "packed_ice")
        self.fall()
        self.assertFalse(self.world.writes)
        self.put(self.lower, "ice")
        self.world.unloaded.add((1, self.lower))
        self.fall()
        self.assertFalse(self.world.writes)

    def test_reentrant_landing_at_another_position_is_processed(self):
        other = (1, 63, 1)
        self.put(self.upper, "stone")
        self.put(self.lower, "stone")
        self.put(other, "ice")
        self.put((1, 62, 1), "ice")
        self.world.block_changed = lambda: self.fall(other, "43")
        self.fall()
        self.assertEqual("minecraft:deepslate", self.world.cells[1, self.lower])
        self.assertEqual("minecraft:packed_ice", self.world.cells[1, (1, 62, 1)])
        self.assertEqual("minecraft:air", self.world.cells[1, other])

    def test_each_squeezed_block_keeps_its_solid_and_collects_the_fluid(self):
        for upper, (_, result, fluid, _) in SQUEEZING.items():
            self.put(self.upper, upper.split(":")[1])
            self.put(self.lower, "cauldron", fill_level=0, cauldron_liquid="water")
            self.world.block_data[1, self.lower] = {"marker": {"__type__": 8, "__value__": "kept"}}
            self.fall()
            self.assertEqual(result, self.world.cells[1, self.upper], upper)
            state = self.world.block_states[1, self.lower]
            self.assertEqual(fluid.split(":")[1], state["cauldron_liquid"])
            self.assertEqual(6 if fluid == "minecraft:lava" else 2, state["fill_level"])
            self.assertEqual("kept", self.world.block_data[1, self.lower]["marker"]["__value__"])

    def test_repeated_squeezing_fills_the_cauldron_then_stops(self):
        self.put(self.lower, "cauldron", fill_level=0, cauldron_liquid="water")
        for expected in (2, 4, 6):
            self.put(self.upper, "snow")
            self.fall()
            self.assertEqual("minecraft:ice", self.world.cells[1, self.upper])
            self.assertEqual(expected, self.world.block_states[1, self.lower]["fill_level"])
        self.put(self.upper, "snow")
        self.fall()
        self.assertEqual("minecraft:snow", self.world.cells[1, self.upper])
        self.assertEqual(6, self.world.block_states[1, self.lower]["fill_level"])

    def test_other_liquid_potion_and_dyed_water_are_preserved(self):
        self.put(self.upper, "moss_block")
        self.put(self.lower, "cauldron", fill_level=2, cauldron_liquid="lava")
        self.fall()
        self.assertFalse(self.world.writes)
        self.put(self.lower, "cauldron", fill_level=2, cauldron_liquid="water")
        for field, value in (("PotionId", 5), ("CustomColor", 0xff00ff)):
            self.world.block_data[1, self.lower] = {field: {"__type__": 3, "__value__": value}}
            self.fall()
            self.assertFalse(self.world.writes)
        self.assertEqual(2, self.world.block_states[1, self.lower]["fill_level"])
        self.world.block_data[1, self.lower] = None
        self.fall()
        self.assertFalse(self.world.writes)

    def test_cauldron_state_failure_restores_the_original_block_states(self):
        self.put(self.upper, "wet_sponge", sample=7)
        self.put(self.lower, "cauldron", fill_level=0, cauldron_liquid="water")
        self.world.state_results = [False]
        self.fall()
        self.assertEqual("minecraft:wet_sponge", self.world.cells[1, self.upper])
        self.assertEqual({"sample": 7}, self.world.block_states[1, self.upper])
        self.assertEqual(0, self.world.block_states[1, self.lower]["fill_level"])

    def test_changed_cauldron_contents_abort_and_restore_only_our_written_block(self):
        def changed_fluid():
            self.world.block_states[1, self.lower] = {"fill_level": 6, "cauldron_liquid": "lava"}

        def changed_potion():
            self.world.block_data[1, self.lower] = {"PotionId": {"__type__": 2, "__value__": 5}}

        for callback in (changed_fluid, changed_potion):
            self.put(self.upper, "wet_sponge")
            self.put(self.lower, "cauldron", fill_level=2, cauldron_liquid="water")
            self.world.block_data.clear()
            self.world.block_changed = callback
            self.fall()
            self.assertEqual("minecraft:wet_sponge", self.world.cells[1, self.upper])
            if callback == changed_fluid:
                self.assertEqual(6, self.world.block_states[1, self.lower]["fill_level"])
                self.assertEqual("lava", self.world.block_states[1, self.lower]["cauldron_liquid"])
            else:
                self.assertEqual(2, self.world.block_states[1, self.lower]["fill_level"])
                self.assertEqual(5, self.world.block_data[1, self.lower]["PotionId"]["__value__"])
            self.assertEqual([], self.world.save["anvilcraft:pending_block_changes_v1"])

    def test_failed_rollback_survives_reload_and_blocks_duplicate_processing(self):
        self.put(self.upper, "stone", stone_type="stone")
        self.put(self.lower, "stone", stone_type="stone")
        self.world.block_results = [True, False, False]
        self.fall()
        self.assertEqual("minecraft:deepslate", self.world.cells[1, self.lower])
        self.assertEqual("minecraft:stone", self.world.cells[1, self.upper])
        self.world.loaded = False
        self.bind()
        self.tick()
        self.fall()
        self.assertEqual("minecraft:stone", self.world.cells[1, self.upper])
        self.world.loaded = True
        self.tick()
        self.assertEqual("minecraft:stone", self.world.cells[1, self.lower])
        self.assertEqual({"stone_type": "stone"}, self.world.block_states[1, self.lower])
        self.fall()
        self.assertEqual("minecraft:deepslate", self.world.cells[1, self.lower])
        self.assertEqual("minecraft:air", self.world.cells[1, self.upper])

    def test_nbt_changed_after_state_write_preserves_nbt_and_restores_our_liquid(self):
        self.put(self.upper, "wet_sponge")
        self.put(self.lower, "cauldron", fill_level=2, cauldron_liquid="water")

        def changed_potion():
            self.world.block_data[1, self.lower] = {"PotionId": 5}

        self.world.state_changed = changed_potion
        self.fall()
        self.assertEqual("minecraft:wet_sponge", self.world.cells[1, self.upper])
        self.assertEqual(2, self.world.block_states[1, self.lower]["fill_level"])
        self.assertEqual({"PotionId": 5}, self.world.block_data[1, self.lower])
        self.assertEqual([], self.world.save["anvilcraft:pending_block_changes_v1"])

    def test_native_fall_reaches_the_same_two_block_processing(self):
        self.put(self.upper, "moss_block")
        self.put(self.lower, "dirt")
        self.world.hit = {"identifier": "minecraft:moss_block", "pos": self.upper}
        self.fire["AddEntityServerEvent"](dict(id="51", engineTypeStr="minecraft:falling_block",
                                               posX=-0.5, posY=70.5, posZ=1.5, dimensionId=1))
        self.world.actor.feet = (-0.5, 64.1, 1.5)
        self.tick(1)
        self.world.cells[1, (-1, 64, 1)] = "minecraft:anvil"
        self.fire["EntityRemoveEvent"]({"id": "51"})
        self.tick(1)
        self.assertEqual("minecraft:grass_block", self.world.cells[1, self.lower])
        self.assertEqual("minecraft:air", self.world.cells[1, self.upper])
