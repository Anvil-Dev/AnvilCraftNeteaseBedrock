# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""回放磁铁循环、跨容器物流与中断恢复，核对数量和附加数据。"""

import copy
import unittest

from test_stations import Machines
from test_drop_work import GroundItem, LOG
from anvilcraft_scripts.common.drop_recipes import CRUSH, STAMP
from anvilcraft_scripts.common.logistics import (
    CHUTE, CHUTE_DOWN, DIRECTIONS, LOGISTICS, MAGNETIC_CHUTE, offset,
)
from anvilcraft_scripts.common.magnets import HELD, MAGNETS, REQUEST_EVENT, STATE_EVENT
from anvilcraft_scripts.server.impact_events import ImpactEvents


class Motion(object):
    def __init__(self, world, entity):
        self.world, self.entity = world, entity

    def SetMotion(self, motion):
        if self.world.refuse_motion:
            return False
        self.world.motions[self.entity] = motion
        return True


class EntityData(dict):

    def __missing__(self, key):
        return None


class Factory(Machines):

    class ItemPosType(Machines.ItemPosType):
        INVENTORY = 0

    def __init__(self):
        super(Factory, self).__init__()
        self.aux = {}
        self.cell_states = {}
        self.power = set()
        self.containers = {}
        self.refuse_container = False
        self.after_native_write = None
        self.refuse_cells = set()
        self.unloaded = set()
        self.motions = {}
        self.sneaking = False
        self.refuse_motion = False
        self.messages = []
        self.look = (0, 0, 1)
        self.game_type = 0
        self.may_place = True
        self.block_listeners = set()
        self.block_data = {}
        self.player_inventory = {}

    def CreateBlockEntityData(self, level):
        return self

    def GetBlockEntityData(self, dim, pos):
        return self.block_data.setdefault((dim, pos), EntityData())

    def GetPlayerItem(self, kind, slot, user_data):
        if kind == self.ItemPosType.INVENTORY:
            return copy.deepcopy(self.player_inventory.get(slot))
        return super(Factory, self).GetPlayerItem(kind, slot, user_data)

    def SpawnItemToPlayerInv(self, item, player, slot=-1):
        if self.refuse_hand:
            return False
        self.player_inventory[slot] = copy.deepcopy(item)
        return True

    def BroadcastToAllClient(self, name, data):
        self.messages.append((None, name, copy.deepcopy(data)))

    def NotifyToClient(self, player, name, data):
        self.messages.append((player, name, copy.deepcopy(data)))

    def CreateRedStone(self, level):
        return self

    def CreatePlayer(self, player):
        return self

    def CreateRot(self, entity):
        return self

    def GetRot(self):
        return 0, 0

    def GetDirFromRot(self, rotation):
        return self.look

    def GetPlayerGameType(self, player):
        return self.game_type

    def MayPlaceOn(self, name, aux, pos, facing):
        return self.may_place

    def AddBlockItemListenForUseEvent(self, name):
        self.block_listeners.add(name)
        return True

    def isSneaking(self):
        return self.sneaking

    def CreateActorMotion(self, entity):
        return Motion(self, entity)

    def GetStrength(self, pos, dim):
        return 15 if (dim, pos) in self.power else 0

    def GetBlockPoweredState(self, pos, dim):
        return (dim, pos) in self.power

    def CheckChunkState(self, dim, pos):
        return self.loaded and (dim, tuple(pos)) not in self.unloaded

    def GetBlockNew(self, pos, dim):
        return {"name": self.cells.get((dim, tuple(pos)), "minecraft:air"),
                "aux": self.aux.get((dim, tuple(pos)), 0)}

    def SetBlockNew(self, pos, block, mode, dimension, legacy=True, updateNeighbors=True):
        if (dimension, pos) in self.refuse_cells:
            return False
        result = super(Factory, self).SetBlockNew(pos, block, mode, dimension, legacy, updateNeighbors)
        if result:
            self.aux[dimension, pos] = block.get("aux", 0)
            self.cell_states.pop((dimension, pos), None)
            self.block_data.pop((dimension, pos), None)
            self.liquids.pop((dimension, pos), None)
        return result

    def GetBlockStates(self, pos, dim):
        default = ({"facing_direction": self.aux.get((dim, pos), 0)}
                   if self.cells.get((dim, pos)) in LOGISTICS else {})
        return copy.deepcopy(self.cell_states.get((dim, pos), default))

    def SetBlockStates(self, pos, states, dim):
        self.cell_states[dim, pos] = copy.deepcopy(states)
        if "facing_direction" in states:
            self.aux[dim, pos] = states["facing_direction"]
        return True

    def GetContainerSize(self, pos, dim):
        return len(self.containers[dim, pos]) if (dim, pos) in self.containers else -1

    def GetContainerItem(self, pos, slot, dim, user_data):
        return copy.deepcopy(self.containers[dim, pos][slot])

    def SpawnItemToContainer(self, item, slot, pos, dim):
        if self.refuse_container:
            return False
        self.containers[dim, pos][slot] = copy.deepcopy(item) if item and item.get("count", 0) else None
        if self.after_native_write:
            self.after_native_write()
        return True


class MechanismTests(unittest.TestCase):

    def setUp(self):
        self.world = Factory()
        self.pos = (0, 63, 0)
        self.magnet = (0, 68, 0)
        self.bind()

    def bind(self):
        self.events = ImpactEvents(self.world, LOG)
        self.events.listen(self.world)
        self.stations = self.events._stations
        self.logistics = self.events._logistics
        self.magnets = self.events._magnets

    def cell(self, pos, name, dim=0, aux=0):
        self.world.cells[dim, pos] = name
        self.world.aux[dim, pos] = aux

    def record(self, pos, *items):
        record = dict(items=list(items))
        if self.world.cells[0, pos] in LOGISTICS:
            record["logistics"] = True
        self.stations.inventory.write(0, pos, record)

    def item(self, name, count, **tags):
        return dict(tags, newItemName="minecraft:" + name, newAuxValue=0, count=count)

    def tick(self, pos, times=1):
        for _ in range(times):
            self.events._tick += 2
            self.stations.tick = self.events._tick
            self.world.callbacks["ServerBlockEntityTickEvent"](dict(
                blockName=self.world.cells[0, pos], dimension=0, posX=pos[0], posY=pos[1], posZ=pos[2]))

    def contents(self, pos):
        return self.stations.inventory.get(0, pos)["items"]

    def box(self, pos, items=None, name="chest"):
        self.cell(pos, "minecraft:" + name)
        self.world.containers[0, pos] = copy.deepcopy(items or [None] * 3)

    def dropped(self, name):
        return [row for row in self.world.drops.values() if row.item["newItemName"] == "minecraft:" + name]

    def placing(self, name, face):
        event = dict(fullName=name, auxData=1, face=face, entityId="player", dimensionId=0,
                     x=self.pos[0], y=self.pos[1], z=self.pos[2], cancel=False)
        self.world.callbacks["ServerEntityTryPlaceBlockEvent"](event)
        return event

    def test_chute_placement_matches_clicked_face_and_sneaking_including_downward(self):
        for sneaking in (False, True):
            self.world.sneaking = sneaking
            for face in range(6):
                event = self.placing(CHUTE, face)
                expected = face if sneaking else face ^ 1
                self.assertEqual(0 if expected < 2 else expected, event["auxData"])
                self.assertFalse(event["cancel"])

    def test_magnetic_placement_supports_six_look_directions_and_extends_existing_output(self):
        vectors = ((0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1), (-1, 0, 0), (1, 0, 0))
        for sneaking in (False, True):
            self.world.sneaking = sneaking
            for direction, vector in enumerate(vectors):
                self.world.look = vector
                self.assertEqual(direction ^ int(sneaking), self.placing(MAGNETIC_CHUTE, 1)["auxData"])
        self.cell((-1, 63, 0), MAGNETIC_CHUTE)
        self.world.cell_states[0, (-1, 63, 0)] = {"facing_direction": 5}
        self.world.look, self.world.sneaking = (0, 0, -1), False
        self.assertEqual(5, self.placing(MAGNETIC_CHUTE, 5)["auxData"])

    def test_incoming_chute_reverses_new_output_and_opposing_sandwich_cancels_placement(self):
        self.cell((-1, 63, 0), CHUTE)
        self.world.cell_states[0, (-1, 63, 0)] = {"facing_direction": 5}
        self.assertEqual(5, self.placing(CHUTE, 5)["auxData"])
        self.cell((1, 63, 0), MAGNETIC_CHUTE)
        self.world.cell_states[0, (1, 63, 0)] = {"facing_direction": 4}
        self.assertTrue(self.placing(CHUTE, 5)["cancel"])
        self.world.look = (-1, 0, 0)
        self.assertTrue(self.placing(MAGNETIC_CHUTE, 5)["cancel"])

    def test_items_inside_both_chute_bodies_are_collected_and_old_upward_chute_is_corrected(self):
        for name in (CHUTE, MAGNETIC_CHUTE):
            self.cell(self.pos, name)
            self.world.cell_states[0, self.pos] = {"facing_direction": 1}
            self.world.drops.clear()
            self.stations.inventory.write(0, self.pos, None)
            drop = GroundItem("minecraft:diamond", 7, (0.5, 63.625, 0.5), 0, extraId="ground")
            entity = "input_" + name
            self.world.drops[entity] = drop
            self.tick(self.pos, 8)
            self.assertNotIn(entity, self.world.drops)
            self.assertEqual("ground", self.contents(self.pos)[0]["extraId"])
            if name == CHUTE:
                self.assertEqual(0, self.world.GetBlockStates(self.pos, 0)["facing_direction"])

    def test_chute_item_use_allows_chain_placement_without_consuming_it_as_inventory(self):
        self.cell(self.pos, CHUTE)
        self.world.carried = dict(newItemName=CHUTE, newAuxValue=0, count=4)
        for sneaking in (False, True):
            self.world.sneaking = sneaking
            self.stations.tick += 10
            event = dict(blockName=CHUTE, playerId="player", dimensionId=0, x=0, y=63, z=0, face=5)
            self.world.callbacks["ServerBlockUseEvent"](event)
            self.assertFalse(event.get("cancel", False))
            self.assertEqual([], self.contents(self.pos))
            self.assertEqual(4, self.world.carried["count"])

    def test_chute_does_not_pull_from_a_neighbour_whose_output_points_away(self):
        self.cell(self.pos, CHUTE)
        above = (0, 64, 0)
        self.cell(above, CHUTE)
        self.world.cell_states[0, above] = {"facing_direction": 5}
        self.record(above, self.item("diamond", 7))
        self.tick(self.pos)
        self.assertEqual([], self.contents(self.pos))
        self.assertEqual(7, self.contents(above)[0]["count"])

    def test_normal_top_placement_collects_ground_item_and_outputs_downward(self):
        event = self.placing(CHUTE, 1)
        self.cell(self.pos, CHUTE)
        self.world.SetBlockStates(self.pos, {"facing_direction": event["auxData"]}, 0)
        below = (0, 62, 0)
        self.box(below)
        self.world.drops["input"] = GroundItem("minecraft:diamond", 7, (0.5, 64, 0.5), 0)
        self.tick(self.pos)
        self.assertNotIn("input", self.world.drops)
        self.tick(self.pos, 8)
        self.assertEqual([], self.contents(self.pos))
        self.assertEqual(7, self.world.containers[0, below][0]["count"])

    def test_magnetic_six_faces_collect_opposite_ground_items_and_deliver_to_container(self):
        for facing, direction in enumerate(DIRECTIONS):
            self.world.cells.clear()
            self.world.containers.clear()
            self.world.drops.clear()
            self.world.look = direction
            event = self.placing(MAGNETIC_CHUTE, 1)
            self.cell(self.pos, MAGNETIC_CHUTE)
            self.world.SetBlockStates(self.pos, {"facing_direction": event["auxData"]}, 0)
            self.box(offset(self.pos, direction))
            source = offset(self.pos, DIRECTIONS[facing ^ 1])
            entity = "input_%d" % facing
            self.world.drops[entity] = GroundItem("minecraft:iron_sword", 1,
                tuple(value + 0.5 for value in source), 0, extraId=entity, userData={"Damage": 91})
            self.tick(self.pos, 8)
            self.assertNotIn(entity, self.world.drops)
            self.tick(self.pos, 8)
            received = self.world.containers[0, offset(self.pos, direction)][0]
            self.assertEqual((entity, {"Damage": 91}), (received["extraId"], received["userData"]))
            self.assertEqual([], self.contents(self.pos))

    def test_body_collection_preserves_full_remainder_and_refunds_on_failed_save(self):
        self.cell(self.pos, CHUTE)
        self.world.power.add((0, self.pos))
        self.world.drops["input"] = GroundItem("minecraft:diamond", 7, (0.5, 63.625, 0.5), 0)
        self.tick(self.pos)
        self.assertIn("input", self.world.drops)
        self.world.power.clear()
        self.world.allow_save = False
        self.tick(self.pos, 8)
        self.assertEqual([], self.contents(self.pos))
        self.assertEqual(7, sum(row.item["count"] for row in self.dropped("diamond")))
        self.world.allow_save = True
        self.record(self.pos, *([self.item("diamond", 64)] * 8 + [self.item("diamond", 63)]))
        self.box((0, 62, 0), [self.item("stone", 64)])
        self.tick(self.pos, 8)
        self.assertEqual(64 * 9, sum(row["count"] for row in self.contents(self.pos)))
        self.assertEqual(6, sum(row.item["count"] for row in self.dropped("diamond")))

    def test_body_collision_collects_between_idle_ticks_and_does_not_reset_cooldown_twice(self):
        self.cell(self.pos, CHUTE)
        self.tick(self.pos)
        self.world.drops["input"] = GroundItem("minecraft:diamond", 7, (0.5, 63.625, 0.5), 0)
        event = dict(blockName=self.world.cells[0, self.pos], blockX=0, blockY=63, blockZ=0,
                     entityId="input")
        self.world.callbacks["OnEntityInsideBlockServerEvent"](event)
        self.world.callbacks["OnEntityInsideBlockServerEvent"](event)
        self.assertEqual(7, self.contents(self.pos)[0]["count"])
        self.assertNotIn("input", self.world.drops)
        self.assertEqual([], self.dropped("diamond"))

    def test_container_use_places_chute_toward_chest_and_preserves_container_inventory(self):
        self.world.callbacks["LoadServerAddonScriptsAfter"]({})
        self.assertIn("minecraft:chest", self.world.block_listeners)
        self.assertIn("minecraft:purple_shulker_box", self.world.block_listeners)
        self.box(self.pos, [self.item("diamond", 51)])
        self.world.carried = dict(newItemName=CHUTE, newAuxValue=0, count=3)
        event = dict(blockName="minecraft:chest", playerId="player", dimensionId=0, x=0, y=63, z=0, face=5)
        self.world.callbacks["ServerBlockUseEvent"](event)
        self.assertTrue(event["cancel"])
        self.assertEqual(CHUTE, self.world.cells[0, (1, 63, 0)])
        self.assertEqual(4, self.world.aux[0, (1, 63, 0)])
        self.assertEqual(2, self.world.carried["count"])
        self.assertEqual(51, self.world.containers[0, self.pos][0]["count"])
        self.world.callbacks["ServerBlockUseEvent"](dict(event, cancel=False))
        self.assertEqual(2, self.world.carried["count"])

    def test_container_attachment_respects_collision_game_mode_and_failed_write_refunds(self):
        self.box(self.pos)
        event = dict(blockName="minecraft:chest", playerId="player", dimensionId=0, x=0, y=63, z=0, face=5)
        item = dict(newItemName=CHUTE, newAuxValue=0, count=3, extraId="refund")
        self.world.carried = copy.deepcopy(item)
        self.world.may_place = False
        self.world.callbacks["ServerBlockUseEvent"](event)
        self.assertNotIn((0, (1, 63, 0)), self.world.cells)
        self.assertEqual(item, self.world.carried)
        self.stations.tick += 10
        self.world.may_place = True
        self.world.refuse_cells.add((0, (1, 63, 0)))
        self.world.callbacks["ServerBlockUseEvent"](dict(event, cancel=False))
        refund = [row.item for row in self.world.drops.values() if row.item["newItemName"] == CHUTE]
        self.assertEqual([dict(item, count=1)], refund)
        self.assertEqual(2, self.world.carried["count"])
        self.stations.tick += 10
        self.world.refuse_cells.clear()
        self.world.game_type = 1
        self.world.callbacks["ServerBlockUseEvent"](dict(event, cancel=False))
        self.assertEqual(2, self.world.carried["count"])
        self.assertEqual(CHUTE, self.world.cells[0, (1, 63, 0)])

    def test_container_attachment_preserves_external_changes_during_hand_update(self):
        self.box(self.pos)
        target = (1, 63, 0)
        original = self.world.SpawnItemToPlayerCarried
        for replacement in ("minecraft:stone", CHUTE):
            self.cell(target, "minecraft:air")
            self.world.drops.clear()
            self.world.carried = dict(newItemName=CHUTE, newAuxValue=0, count=3, extraId="refund")
            def change_target(item, player):
                result = original(item, player)
                self.cell(target, replacement)
                return result
            self.world.SpawnItemToPlayerCarried = change_target
            self.stations.tick += 10
            self.world.callbacks["ServerBlockUseEvent"](dict(
                blockName="minecraft:chest", playerId="player", dimensionId=0, x=0, y=63, z=0, face=5))
            self.assertEqual(replacement, self.world.cells[0, target])
            refund = [row.item for row in self.world.drops.values() if row.item["newItemName"] == CHUTE]
            self.assertEqual([dict(newItemName=CHUTE, newAuxValue=0, count=1, extraId="refund")], refund)
            self.assertEqual(2, self.world.carried["count"])

    def test_both_magnets_sync_power_and_late_join_without_client_control_of_state(self):
        for name in MAGNETS:
            self.cell(self.magnet, name)
            self.world.power.add((0, self.magnet))
            self.tick(self.magnet)
            self.assertTrue(self.world.messages[-1][2]["lit"])
            event = dict(playerId="player", dimensionId=0, pos=list(self.magnet), lit=False)
            self.world.callbacks[REQUEST_EVENT](event)
            self.assertEqual(("player", STATE_EVENT), self.world.messages[-1][:2])
            self.assertTrue(self.world.messages[-1][2]["lit"])
            count = len(self.world.messages)
            self.world.player.dim = 1
            self.world.callbacks[REQUEST_EVENT](event)
            self.world.callbacks[REQUEST_EVENT](dict(event, dimensionId=None))
            self.assertEqual(count, len(self.world.messages))
            self.world.player.dim = 0
            self.world.power.clear()
            self.tick(self.magnet)
            self.assertTrue(self.world.messages[-1][2]["lit"])
            self.tick(self.magnet, 3)
            self.assertFalse(self.world.messages[-1][2]["lit"])

    def test_power_return_cancels_magnet_off_delay_and_keeps_anvil_released(self):
        self.cell(self.magnet, MAGNETS[0])
        self.world.power.add((0, self.magnet))
        self.tick(self.magnet)
        self.world.power.clear()
        self.cell((0, 64, 0), "minecraft:anvil")
        self.tick(self.magnet, 2)
        self.assertEqual("minecraft:anvil", self.world.cells[0, (0, 64, 0)])
        self.world.power.add((0, self.magnet))
        self.tick(self.magnet, 5)
        self.assertEqual("minecraft:anvil", self.world.cells[0, (0, 64, 0)])
        self.world.power.clear()
        self.tick(self.magnet, 4)
        self.assertEqual(HELD["minecraft:anvil"], self.world.cells[0, (0, 67, 0)])

    def test_failed_held_placement_does_not_block_powered_appearance(self):
        self.cell(self.magnet, MAGNETS[0])
        self.cell((0, 64, 0), "minecraft:anvil")
        self.world.refuse_cells.add((0, (0, 67, 0)))
        self.tick(self.magnet)
        self.assertEqual("placing", self.magnets._data.get(0, self.magnet)["phase"])
        self.world.power.add((0, self.magnet))
        self.world.callbacks["BlockStrengthChangedServerEvent"](dict(
            blockName=MAGNETS[0], dimensionId=0, posX=0, posY=68, posZ=0, newStrength=15))
        self.assertTrue(self.world.messages[-1][2]["lit"])
        self.world.power.clear()
        self.tick(self.magnet, 4)
        self.assertFalse(self.world.messages[-1][2]["lit"])

    def test_magnet_lifts_holds_and_releases_original_damage_and_orientation(self):
        self.cell(self.magnet, MAGNETS[0])
        self.cell((0, 64, 0), "minecraft:chipped_anvil", aux=2)
        self.tick(self.magnet)
        held = (0, 67, 0)
        self.assertEqual("minecraft:air", self.world.cells[0, (0, 64, 0)])
        self.assertEqual(HELD["minecraft:chipped_anvil"], self.world.cells[0, held])
        self.bind()
        self.tick(self.magnet)
        self.assertEqual(HELD["minecraft:chipped_anvil"], self.world.cells[0, held])
        self.world.power.add((0, self.magnet))
        self.tick(self.magnet)
        self.assertEqual({"name": "minecraft:chipped_anvil", "aux": 2}, self.world.GetBlockNew(held, 0))
        self.assertNotIn("phase", self.magnets._data.get(0, self.magnet))

    def test_power_obstructions_unloaded_cells_and_failed_save_do_not_consume_anvils(self):
        self.cell(self.magnet, MAGNETS[0])
        source = (0, 64, 0)
        self.cell(source, "minecraft:anvil")
        self.cell((0, 66, 0), "minecraft:stone")
        self.tick(self.magnet)
        self.assertEqual("minecraft:anvil", self.world.cells[0, source])
        self.cell((0, 66, 0), "minecraft:air")
        self.world.power.add((0, self.magnet))
        self.tick(self.magnet)
        self.assertEqual("minecraft:anvil", self.world.cells[0, source])
        self.world.power.clear()
        self.world.unloaded.add((0, source))
        self.tick(self.magnet)
        self.assertEqual("minecraft:anvil", self.world.cells[0, source])
        self.world.unloaded.clear()
        self.world.allow_save = False
        self.tick(self.magnet)
        self.assertEqual("minecraft:anvil", self.world.cells[0, source])

    def test_interrupted_magnet_placement_recovers_and_breaking_magnet_releases(self):
        self.cell(self.magnet, MAGNETS[1])
        source, held = (0, 64, 0), (0, 67, 0)
        self.cell(source, "minecraft:damaged_anvil", aux=3)
        self.world.refuse_cells.add((0, held))
        self.tick(self.magnet)
        self.assertEqual("placing", self.magnets._data.get(0, self.magnet)["phase"])
        self.assertEqual("minecraft:air", self.world.cells[0, source])
        self.bind()
        self.world.refuse_cells.clear()
        self.tick(self.magnet)
        self.cell(self.magnet, "minecraft:air")
        self.magnets.advance(30)
        self.assertEqual("minecraft:damaged_anvil", self.world.cells[0, held])
        self.assertEqual(3, self.world.aux[0, held])

    def test_nested_magnet_events_cannot_claim_one_anvil_twice(self):
        self.cell(self.magnet, MAGNETS[0])
        other = (0, 66, 0)
        self.cell(other, MAGNETS[0])
        self.cell((0, 63, 0), "minecraft:anvil")
        original = self.world.SetExtraData
        fired = [False]
        def save(key, records, sync):
            if key == "anvilcraft:magnet_holds_v1" and not fired[0]:
                fired[0] = True
                self.magnets.step(0, other)
            return original(key, records, sync)
        self.world.SetExtraData = save
        self.magnets.step(0, other)
        self.magnets.step(0, self.magnet)
        self.assertEqual(1, sum(name in HELD.values() for name in self.world.cells.values()))

    def test_mined_source_during_prepare_does_not_create_a_second_anvil(self):
        self.cell(self.magnet, MAGNETS[0])
        source = (0, 64, 0)
        self.cell(source, "minecraft:anvil")
        original = self.world.SetExtraData
        fired = [False]
        def save(key, records, sync):
            if key == "anvilcraft:magnet_holds_v1" and not fired[0]:
                fired[0] = True
                self.cell(source, "minecraft:air")
                self.world.CreateEngineItemEntity(self.item("anvil", 1), 0, (0.5, 64, 0.5))
            return original(key, records, sync)
        self.world.SetExtraData = save
        self.tick(self.magnet)
        self.assertEqual(1, self.dropped("anvil")[0].item["count"])
        self.assertEqual(0, sum(name in HELD.values() for name in self.world.cells.values()))

    def test_replacement_at_consumed_source_is_preserved_and_new_obstruction_stops_recovery(self):
        self.cell(self.magnet, MAGNETS[0])
        source, target = (0, 64, 0), (0, 67, 0)
        self.cell(source, "minecraft:anvil")
        self.world.refuse_cells.add((0, target))
        self.tick(self.magnet)
        self.assertEqual("placing", self.magnets._data.get(0, self.magnet)["phase"])
        self.cell(source, "minecraft:anvil")
        self.cell((0, 66, 0), "minecraft:stone")
        self.world.refuse_cells.clear()
        self.bind()
        self.tick(self.magnet)
        self.assertEqual("minecraft:air", self.world.cells.get((0, target), "minecraft:air"))
        self.cell((0, 66, 0), "minecraft:air")
        self.tick(self.magnet)
        self.assertEqual("minecraft:anvil", self.world.cells[0, source])
        self.assertEqual(HELD["minecraft:anvil"], self.world.cells[0, target])

    def test_held_anvil_removed_during_release_prepare_is_refunded_once(self):
        self.cell(self.magnet, MAGNETS[0])
        self.cell((0, 64, 0), "minecraft:anvil")
        self.tick(self.magnet)
        original = self.world.SetExtraData
        fired = [False]
        def save(key, records, sync):
            if key == "anvilcraft:magnet_holds_v1" and not fired[0] and any(
                    row.get("phase") == "releasing" for row in records.values()):
                fired[0] = True
                self.cell((0, 67, 0), "minecraft:air")
                self.magnets.remove(dict(fullName=HELD["minecraft:anvil"], dimension=0, x=0, y=67, z=0))
            return original(key, records, sync)
        self.world.SetExtraData = save
        self.world.power.add((0, self.magnet))
        self.tick(self.magnet)
        self.tick(self.magnet)
        self.assertEqual(1, sum(drop.item["count"] for drop in self.dropped("anvil")))
        self.assertNotIn("phase", self.magnets._data.get(0, self.magnet))

    def test_lightning_rod_converts_only_nearby_iron_blocks_once(self):
        self.cell((0, 64, 0), "minecraft:lightning_rod")
        self.cell((0, 63, 0), "minecraft:iron_block")
        self.cell((2, 63, 0), "minecraft:iron_block")
        event = dict(id="lightning", engineTypeStr="minecraft:lightning_bolt", dimensionId=0,
                     posX=0.5, posY=65, posZ=0.5)
        self.world.callbacks["AddEntityServerEvent"](event)
        self.world.callbacks["AddEntityServerEvent"](event)
        self.assertEqual(MAGNETS[1], self.world.cells[0, (0, 63, 0)])
        self.assertEqual("minecraft:iron_block", self.world.cells[0, (2, 63, 0)])

    def test_chute_collects_items_then_inserts_into_chest_with_all_metadata(self):
        self.cell(self.pos, CHUTE)
        below = (0, 62, 0)
        self.box(below)
        data = self.item("iron_sword", 1, userData={"Damage": 75}, enchantData=[(9, 3)], extraId="kept")
        drop = GroundItem("minecraft:iron_sword", 1, (0.5, 64.2, 0.5), 0)
        drop.item = data
        self.world.drops["input"] = drop
        self.tick(self.pos)
        self.assertEqual(data, self.contents(self.pos)[0])
        self.tick(self.pos, 8)
        self.assertEqual([], self.contents(self.pos))
        self.assertEqual(data, self.world.containers[0, below][0])

    def test_full_output_and_redstone_pause_keep_input_then_resume(self):
        self.cell(self.pos, CHUTE)
        below, above = (0, 62, 0), (0, 64, 0)
        self.box(below, [self.item("iron_ingot", 64)])
        self.box(above, [self.item("iron_ingot", 8)])
        self.record(self.pos, self.item("iron_ingot", 12))
        self.world.power.add((0, self.pos))
        self.tick(self.pos)
        self.assertEqual(12, self.contents(self.pos)[0]["count"])
        self.world.power.clear()
        self.tick(self.pos, 8)
        self.assertEqual(20, self.contents(self.pos)[0]["count"])
        self.assertEqual(64, self.world.containers[0, below][0]["count"])
        self.world.containers[0, below][0] = None
        self.tick(self.pos, 8)
        self.assertEqual(20, self.world.containers[0, below][0]["count"])
        self.assertEqual([], self.contents(self.pos))

    def test_inventory_to_inventory_transfer_is_atomic_and_feeds_processing_table(self):
        self.cell(self.pos, MAGNETIC_CHUTE)
        target = (1, 63, 0)
        self.cell(target, STAMP)
        self.world.cell_states[0, self.pos] = {"facing_direction": 5}
        self.record(self.pos, self.item("sugar_cane", 5, extraId="transport"))
        self.world.allow_save = False
        self.tick(self.pos)
        self.assertEqual(5, self.contents(self.pos)[0]["count"])
        self.assertEqual([], self.contents(target))
        self.world.allow_save = True
        self.tick(self.pos, 8)
        self.assertEqual([], self.contents(self.pos))
        self.assertEqual("transport", self.contents(target)[0]["extraId"])
        self.stations.process(STAMP, 0, target)
        self.assertEqual(5, self.dropped("paper")[0].item["count"])

    def test_native_push_saved_receipt_completes_once_after_reload(self):
        self.cell(self.pos, CHUTE_DOWN)
        below = (0, 62, 0)
        self.box(below)
        self.record(self.pos, self.item("diamond", 7))
        self.world.save_results = [True, True, False]
        self.tick(self.pos)
        self.assertEqual(7, self.world.containers[0, below][0]["count"])
        self.assertIn("transfer", self.stations.inventory.get(0, self.pos))
        self.world.after_native_write = None
        self.world.allow_save = True
        self.bind()
        self.tick(self.pos)
        self.assertEqual(7, self.world.containers[0, below][0]["count"])
        self.assertNotIn("transfer", self.stations.inventory.get(0, self.pos))

    def test_native_pull_saved_receipt_completes_once_and_failed_write_keeps_source(self):
        self.cell(self.pos, CHUTE)
        above = (0, 64, 0)
        self.box(above, [self.item("gold_ingot", 11)])
        self.world.refuse_container = True
        self.tick(self.pos)
        self.assertEqual(11, self.world.containers[0, above][0]["count"])
        self.assertEqual([], self.contents(self.pos))
        self.world.refuse_container = False
        self.world.save_results = [True, True, False]
        self.tick(self.pos, 8)
        self.assertIsNone(self.world.containers[0, above][0])
        self.world.allow_save = True
        self.world.after_native_write = None
        self.bind()
        self.logistics._recover(0, self.pos)
        self.assertEqual(11, self.contents(self.pos)[0]["count"])
        self.logistics._recover(0, self.pos)
        self.assertEqual(11, self.contents(self.pos)[0]["count"])

    def test_unknown_transfer_never_refunds_after_player_takes_identical_snapshot(self):
        self.cell(self.pos, CHUTE)
        below = (0, 62, 0)
        self.box(below)
        self.record(self.pos, self.item("diamond", 7))
        self.world.after_native_write = lambda: setattr(self.world, "allow_save", False)
        self.tick(self.pos)
        self.assertEqual(7, self.world.containers[0, below][0]["count"])
        self.world.containers[0, below][0] = None
        self.world.after_native_write = None
        self.world.allow_save = True
        self.tick(self.pos, 8)
        self.assertIsNone(self.world.containers[0, below][0])
        self.assertEqual([], self.contents(self.pos))
        self.record(self.pos, self.item("diamond", 7))
        self.world.after_native_write = lambda: setattr(self.world, "allow_save", False)
        self.tick(self.pos, 8)
        self.world.containers[0, below][0] = None
        self.world.after_native_write = None
        self.world.allow_save = True
        self.bind()
        self.tick(self.pos)
        self.assertIsNone(self.world.containers[0, below][0])
        self.assertEqual([], self.contents(self.pos))
        self.assertIn("transfer", self.stations.inventory.get(0, self.pos))

    def test_refused_native_write_with_foreign_changes_keeps_an_unresolved_reservation(self):
        self.cell(self.pos, CHUTE)
        below = (0, 62, 0)
        self.box(below)
        self.record(self.pos, self.item("diamond", 7))
        def refuse(item, slot, pos, dim):
            self.world.containers[dim, pos][slot] = self.item("diamond", 7)
            return False
        self.world.SpawnItemToContainer = refuse
        self.tick(self.pos)
        record = self.stations.inventory.get(0, self.pos)
        self.assertEqual([self.item("diamond", 7)], record["transfer"]["reserved"])
        self.assertNotIn("outcome", record["transfer"])
        self.assertEqual(7, self.world.containers[0, below][0]["count"])
        self.stations.inventory.write(0, self.pos, dict(items=[self.item("diamond", 7)], logistics=True))
        self.world.containers[0, below] = [self.item("iron_ingot", 64)] * 27 + [None] * 27
        def shrink(item, slot, pos, dim):
            self.world.containers[dim, pos] = self.world.containers[dim, pos][:27]
            return False
        self.world.SpawnItemToContainer = shrink
        self.tick(self.pos, 8)
        self.assertIn("transfer", self.stations.inventory.get(0, self.pos))

    def test_unrelated_chutes_cannot_overwrite_inventory_during_nested_save(self):
        other = (5, 63, 0)
        self.cell(self.pos, CHUTE)
        self.cell(other, CHUTE)
        self.record(self.pos, self.item("diamond", 7))
        self.record(other, self.item("gold_ingot", 9))
        original = self.world.SetExtraData
        fired = [False]
        def save(key, records, sync):
            if key == "anvilcraft:machine_inventories_v1" and not fired[0]:
                fired[0] = True
                self.tick(other)
            return original(key, records, sync)
        self.world.SetExtraData = save
        self.tick(self.pos)
        self.assertEqual(7, self.dropped("diamond")[0].item["count"])
        self.assertEqual([], self.dropped("gold_ingot"))
        self.assertEqual(9, self.contents(other)[0]["count"])
        self.tick(other, 8)
        self.assertEqual(9, self.dropped("gold_ingot")[0].item["count"])
        self.assertEqual([], self.contents(other))

    def test_break_refund_is_locked_and_unknown_transfer_keeps_only_its_reservation(self):
        self.cell(self.pos, CHUTE)
        self.record(self.pos, self.item("diamond", 7))
        original = self.world.SetExtraData
        fired = [False]
        event = dict(fullName=CHUTE, dimension=0, x=0, y=63, z=0)
        def save(key, records, sync):
            if key == "anvilcraft:machine_inventories_v1" and not fired[0]:
                fired[0] = True
                self.logistics.remove(event)
            return original(key, records, sync)
        self.world.SetExtraData = save
        self.logistics.remove(event)
        self.assertEqual(7, sum(drop.item["count"] for drop in self.dropped("diamond")))
        below = (0, 62, 0)
        self.box(below)
        self.record(self.pos, self.item("diamond", 7), self.item("gold_ingot", 3))
        self.world.after_native_write = lambda: setattr(self.world, "allow_save", False)
        self.tick(self.pos)
        self.world.after_native_write = None
        self.world.allow_save = True
        self.cell(self.pos, "minecraft:air")
        self.cell(below, "minecraft:air")
        self.bind()
        self.logistics.advance(30)
        self.assertEqual(3, self.dropped("gold_ingot")[0].item["count"])
        record = self.stations.inventory.get(0, self.pos)
        self.assertEqual([], record["items"])
        self.assertEqual([self.item("diamond", 7)], record["transfer"]["original"])

    def test_refused_motion_retracts_entity_and_retries_original_delivery_once(self):
        self.cell(self.pos, MAGNETIC_CHUTE)
        self.world.cell_states[0, self.pos] = {"facing_direction": 1}
        self.record(self.pos, self.item("diamond", 7))
        self.world.refuse_motion = True
        self.tick(self.pos)
        self.assertEqual([], self.dropped("diamond"))
        self.assertEqual(1, len(self.events._drop_work._delivery.pending))
        self.world.refuse_motion = False
        self.events._drop_work.tick(30)
        self.assertEqual(7, self.dropped("diamond")[0].item["count"])
        self.assertEqual([], self.events._drop_work._delivery.pending)

    def test_filter_direction_configuration_does_not_consume_items_and_ignores_remote_player(self):
        self.cell(self.pos, MAGNETIC_CHUTE)
        self.world.sneaking = True
        self.world.carried = self.item("iron_ingot", 3)
        event = dict(blockName=MAGNETIC_CHUTE, playerId="player", dimensionId=0, x=0, y=63, z=0, face=1)
        self.world.callbacks["ServerBlockUseEvent"](event)
        self.assertEqual(3, self.world.carried["count"])
        self.assertEqual(["minecraft:iron_ingot", 0], self.stations.inventory.get(0, self.pos)["filter"])
        self.world.carried = None
        self.stations.tick += 10
        self.logistics.use(event)
        self.assertEqual(1, self.world.GetBlockStates(self.pos, 0)["facing_direction"])
        self.stations.tick += 10
        self.world.player.dim = 1
        event["face"] = 5
        self.logistics.use(event)
        self.assertEqual(1, self.world.GetBlockStates(self.pos, 0)["facing_direction"])
        self.world.player.dim = 0
        self.world.drops["filtered"] = GroundItem("minecraft:gold_ingot", 3, (0.5, 62.2, 0.5), 0)
        self.tick(self.pos)
        self.assertIn("filtered", self.world.drops)
        self.assertEqual([], self.contents(self.pos))

    def test_magnetic_upward_ejection_preserves_motion_when_delivery_is_deferred(self):
        self.cell(self.pos, MAGNETIC_CHUTE)
        self.world.cell_states[0, self.pos] = {"facing_direction": 1}
        self.record(self.pos, self.item("iron_ingot", 4))
        self.world.refuse.add("minecraft:iron_ingot")
        self.tick(self.pos)
        self.assertEqual([], self.contents(self.pos))
        self.bind()
        self.world.refuse.clear()
        self.events._drop_work.load()
        self.events._drop_work.tick(30)
        drop = self.dropped("iron_ingot")[0]
        self.assertEqual(4, drop.item["count"])
        self.assertIn((0, 0.25, 0), self.world.motions.values())

    def test_break_refund_retries_and_unloaded_output_never_moves_items(self):
        self.cell(self.pos, CHUTE)
        below = (0, 62, 0)
        self.box(below)
        self.record(self.pos, self.item("diamond", 9, extraId="restore"))
        self.world.unloaded.add((0, below))
        self.tick(self.pos)
        self.assertEqual(9, self.contents(self.pos)[0]["count"])
        self.cell(self.pos, "minecraft:air")
        self.world.allow_save = False
        self.logistics.remove(dict(fullName=CHUTE, dimension=0, x=0, y=63, z=0))
        self.world.allow_save = True
        self.bind()
        self.logistics.advance(30)
        self.assertEqual([], self.contents(self.pos))
        self.assertEqual("restore", self.dropped("diamond")[0].item["extraId"])

    def test_magnet_release_two_processing_cycles_and_chute_collection(self):
        self.cell(self.pos, CRUSH)
        self.cell(self.magnet, MAGNETS[0])
        source = (0, 64, 0)
        chute, box = (0, 61, 0), (0, 60, 0)
        self.cell(chute, CHUTE)
        self.box(box)
        for index in range(2):
            self.cell(source, "minecraft:anvil")
            self.world.power.clear()
            self.tick(self.magnet, 4)
            self.world.power.add((0, self.magnet))
            self.tick(self.magnet)
            self.record(self.pos, self.item("bone", 1))
            self.world.callbacks["HeavyBlockStartFallingServerEvent"](dict(
                dimensionId=0, fallingBlockId=str(index), blockName="minecraft:anvil", blockX=0, blockY=67, blockZ=0))
            self.world.callbacks["FallingBlockReturnHeavyBlockServerEvent"](dict(
                dimensionId=0, fallingBlockId=str(index), heavyBlockName="minecraft:anvil", blockX=0, blockY=64, blockZ=0))
            for drop in self.dropped("bone_meal"):
                drop.pos = (0.5, 62.2, 0.5)
            self.cell((0, 67, 0), "minecraft:air")
            self.tick(chute, 16)
        self.assertEqual(12, self.world.containers[0, box][0]["count"])

    def test_unpowered_magnet_waits_for_native_landing_processing_before_lifting(self):
        self.cell(self.pos, CRUSH)
        self.cell(self.magnet, MAGNETS[0])
        self.record(self.pos, self.item("bone", 1))
        self.world.hit = {"identifier": CRUSH, "pos": self.pos}
        self.world.callbacks["AddEntityServerEvent"](dict(
            id="fall", engineTypeStr="minecraft:falling_block", dimensionId=0,
            posX=0.5, posY=67, posZ=0.5))
        self.world.actor.feet = (0.5, 64, 0.5)
        self.world.callbacks["OnGroundServerEvent"](dict(id="fall"))
        self.world.callbacks["EntityRemoveEvent"](dict(id="fall"))
        self.cell((0, 64, 0), "minecraft:anvil")
        self.tick(self.magnet)
        self.assertEqual("minecraft:anvil", self.world.cells[0, (0, 64, 0)])
        self.world.callbacks["OnScriptTickServer"]()
        self.assertEqual(6, self.dropped("bone_meal")[0].item["count"])
        self.tick(self.magnet)
        self.assertEqual(HELD["minecraft:anvil"], self.world.cells[0, (0, 67, 0)])


if __name__ == "__main__":
    unittest.main()
