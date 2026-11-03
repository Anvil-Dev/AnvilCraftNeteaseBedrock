# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""验证模型继承、逐面转换与客户端朝向更新。"""

from copy import deepcopy
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "behavior_pack"))
from java_models import JavaModels, face_uv, geometry
from item_icons import render_icon
from cStringIO import StringIO
from PIL import Image
from anvilcraft_scripts.client.visual_events import VisualEvents
from anvilcraft_scripts.common.logistics import CHUTE
from anvilcraft_scripts.common.magnets import MAGNETS, REQUEST_EVENT, STATE_EVENT


class ModelTests(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.base = os.path.join(self.directory, "src/main/resources/assets/anvilcraft/models/block")
        os.makedirs(self.base)
        self.jar = os.path.join(self.directory, "vanilla.jar")
        with zipfile.ZipFile(self.jar, "w") as pack:
            pack.writestr("assets/minecraft/models/block/block.json", "{}")
        self.models = JavaModels(self.directory, self.jar)

    def write(self, name, data):
        with open(os.path.join(self.base, name + ".json"), "wb") as handle:
            json.dump(data, handle)

    def test_inheritance_overrides_texture_aliases_without_changing_other_children(self):
        self.write("parent", {"parent": "minecraft:block/block", "elements": [],
                              "display": {"gui": {"rotation": [30, 225, 0]}},
                              "textures": {"side": "anvilcraft:block/metal", "particle": "#side"}})
        self.write("first", {"parent": "anvilcraft:block/parent", "textures": {"side": "anvilcraft:block/first"},
                             "display": {"fixed": {"rotation": [0, 90, 0]}}})
        self.write("second", {"parent": "anvilcraft:block/parent", "textures": {"side": "anvilcraft:block/second"}})
        first = self.models.read("anvilcraft:block/first")
        second = self.models.read("anvilcraft:block/second")
        first["textures"]["side"] = "anvilcraft:block/edited"
        self.assertEqual([30, 225, 0], first["display"]["gui"]["rotation"])
        self.assertEqual("anvilcraft:block/second", self.models.texture(second, "#particle"))
        self.assertEqual("anvilcraft:block/first", self.models.texture(self.models.read("anvilcraft:block/first"), "#particle"))
        self.write("cycle", {"parent": "anvilcraft:block/cycle"})
        self.assertRaises(ValueError, self.models.read, "anvilcraft:block/cycle")

    def test_partition_preserves_mirrored_uvs_and_rotated_element_coordinates(self):
        model = {"textures": {"top": "anvilcraft:block/top", "side": "anvilcraft:block/side"},
                 "elements": [{"from": [2, 9, 1.5], "to": [5, 15, 7.5],
                               "rotation": {"angle": 22.5, "axis": "x", "origin": [8, 12, 4.5]},
                               "faces": {"north": {"uv": [12, 0, 4, 16], "texture": "#side"},
                                         "up": {"uv": [0, 5, 12, 6], "texture": "#top", "rotation": 270}}}]}
        before = deepcopy(model)
        top = geometry(self.models, model, "anvilcraft:block/top", "geometry.top", (16, 16))
        side = geometry(self.models, model, "anvilcraft:block/side", "geometry.side", (16, 16))
        cube = top["bones"][0]["cubes"][0]
        self.assertEqual([-5, 9, 1.5], cube["origin"])
        self.assertEqual([3, 6, 6], cube["size"])
        self.assertEqual([-8, 12, 4.5], cube["pivot"])
        self.assertEqual([-22.5, 0, 0], cube["rotation"])
        self.assertEqual({"up": {"uv": [12, 6], "uv_size": [-12, -1], "uv_rotation": 270}}, cube["uv"])
        self.assertEqual({"north": {"uv": [12, 0], "uv_size": [-8, 16]}}, side["bones"][0]["cubes"][0]["uv"])
        self.assertEqual(before, model)

    def test_uv_scales_with_actual_texture_size_and_rejects_rescale(self):
        face = {"uv": [1, 2, 4, 8], "texture": "anvilcraft:block/test"}
        self.assertEqual({"uv": [2, 8], "uv_size": [6, 24]}, face_uv(face, "east", 32, 64))
        model = {"elements": [{"from": [0, 0, 0], "to": [1, 1, 1], "faces": {"up": face},
                               "rotation": {"axis": "x", "angle": 22.5, "origin": [0, 0, 0], "rescale": True}}]}
        self.assertRaises(ValueError, geometry, self.models, model, "anvilcraft:block/test", "geometry.test", (16, 16))

    def test_icon_depth_and_transparent_hole_preserve_the_visible_model(self):
        red = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        for x in range(4, 12):
            for y in range(4, 12):
                red.putpixel((x, y), (0, 0, 0, 0))
        blue = Image.new("RGBA", (16, 16), (0, 0, 255, 255))
        def plane(z, texture):
            return {"from": [0, 0, z], "to": [16, 16, z], "faces": {
                "south": {"uv": [0, 0, 16, 16], "texture": texture}}}
        model = {"display": {"gui": {"rotation": [0, 0, 0]}},
                 "elements": [plane(0, "anvilcraft:block/blue"), plane(1, "anvilcraft:block/red")]}
        image = Image.open(StringIO(render_icon(self.models, model, {
            "anvilcraft:block/blue": blue, "anvilcraft:block/red": red})))
        self.assertEqual((0, 0, 204, 255), image.getpixel((32, 32)))
        self.assertEqual((204, 0, 0, 255), image.getpixel((10, 10)))
        self.assertEqual(0, image.getpixel((0, 0))[3])

    def test_gui_projection_keeps_the_anvil_damage_surface_visible(self):
        faces = {direction: {"uv": [0, 0, 16, 16], "texture": "anvilcraft:block/side"}
                 for direction in ("up", "down", "east", "west", "north", "south")}
        faces["up"]["texture"] = "anvilcraft:block/top"
        model = {"display": {"gui": {"rotation": [30, 225, 0]}},
                 "elements": [{"from": [0, 0, 0], "to": [16, 16, 16], "faces": faces}]}
        textures = {"anvilcraft:block/side": Image.new("RGBA", (16, 16), (0, 0, 255, 255)),
                    "anvilcraft:block/top": Image.new("RGBA", (16, 16), (255, 0, 0, 255))}
        first = render_icon(self.models, model, textures)
        textures["anvilcraft:block/top"] = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
        second = render_icon(self.models, model, textures)
        self.assertNotEqual(first, second)

    def test_icon_face_rotation_is_clockwise_for_asymmetric_textures(self):
        texture = Image.new("RGBA", (16, 16), (0, 0, 255, 255))
        for x in range(4):
            for y in range(4):
                texture.putpixel((x, y), (255, 0, 0, 255))
        face = {"uv": [0, 0, 16, 16], "texture": "anvilcraft:block/test", "rotation": 90}
        model = {"display": {"gui": {"rotation": [0, 0, 0]}}, "elements": [
            {"from": [0, 0, 1], "to": [16, 16, 1], "faces": {"south": face}}]}
        data = {"anvilcraft:block/test": texture}
        clockwise = Image.open(StringIO(render_icon(self.models, model, data)))
        self.assertEqual((204, 0, 0, 255), clockwise.getpixel((54, 10)))
        self.assertEqual((0, 0, 204, 255), clockwise.getpixel((10, 10)))
        face["rotation"] = 270
        counterclockwise = Image.open(StringIO(render_icon(self.models, model, data)))
        self.assertEqual((204, 0, 0, 255), counterclockwise.getpixel((10, 54)))


class Client(object):

    def __init__(self):
        self.callbacks, self.blocks, self.variables = {}, {}, {}
        self.dimension = 0
        self.allow_update = True
        self.requests = []

    def GetEngineCompFactory(self):
        return self

    def GetLevelId(self):
        return "level"

    def GetEngineNamespace(self):
        return "Minecraft"

    def GetEngineSystemName(self):
        return "Engine"

    def GetLocalPlayerId(self):
        return "player"

    def NotifyToServer(self, name, data):
        self.requests.append((name, deepcopy(data)))

    def ListenForEvent(self, namespace, system, name, receiver, callback):
        self.callbacks[name] = callback

    def CreateBlockInfo(self, level):
        return self

    def CreateGame(self, level):
        return self

    def GetCurrentDimension(self):
        return self.dimension

    def GetBlock(self, pos):
        return self.blocks.get(pos)

    def SetBlockEntityMolangValue(self, pos, name, value):
        if self.allow_update:
            self.variables[pos, name] = value
        return self.allow_update


class VisualTests(unittest.TestCase):

    def test_powered_magnet_loaded_late_retries_model_and_survives_dimension_changes(self):
        world = Client()
        events = VisualEvents(world)
        events.listen(world)
        pos = (0, 64, 0)
        for name in MAGNETS:
            world.blocks[pos] = name, 0
            args = dict(blockName=name, dimensionId=0, posX=0, posY=64, posZ=0)
            world.callbacks["ModBlockEntityLoadedClientEvent"](args)
            self.assertEqual(REQUEST_EVENT, world.requests[-1][0])
            world.allow_update = False
            world.callbacks[STATE_EVENT](dict(dimensionId=0, pos=list(pos), lit=True))
            world.allow_update = True
            world.callbacks["ModBlockEntityTickClientEvent"](args)
            self.assertEqual(1, world.variables[pos, "variable.anvilcraft_lit"])
            world.dimension = 1
            world.callbacks[STATE_EVENT](dict(dimensionId=0, pos=list(pos), lit=False))
            self.assertEqual(1, world.variables[pos, "variable.anvilcraft_lit"])
            world.dimension = 0
            world.callbacks["ModBlockEntityTickClientEvent"](args)
            self.assertEqual(0, world.variables[pos, "variable.anvilcraft_lit"])
            world.callbacks["ModBlockEntityRemoveClientEvent"](args)

    def test_initialization_retry_and_far_direction_changes_update_the_same_model(self):
        world = Client()
        events = VisualEvents(world)
        events.listen(world)
        pos = (1, 64, 2)
        args = dict(blockName=CHUTE, dimensionId=0, posX=1, posY=64, posZ=2)
        world.blocks[pos] = CHUTE, 0
        world.allow_update = False
        world.callbacks["ModBlockEntityLoadedClientEvent"](args)
        self.assertEqual({}, world.variables)
        world.allow_update = True
        world.callbacks["ModBlockEntityTickClientEvent"](args)
        self.assertEqual(1, world.variables[pos, "variable.anvilcraft_down"])
        world.blocks[pos] = CHUTE, 5
        for _ in range(15):
            world.callbacks["OnScriptTickClient"]()
        self.assertEqual(0, world.variables[pos, "variable.anvilcraft_down"])
        world.dimension = 1
        world.blocks[pos] = CHUTE, 0
        world.callbacks["ModBlockEntityTickClientEvent"](args)
        self.assertEqual(0, world.variables[pos, "variable.anvilcraft_down"])
        world.callbacks["ModBlockEntityRemoveClientEvent"](args)
        world.dimension = 0
        for _ in range(15):
            world.callbacks["OnScriptTickClient"]()
        self.assertEqual(0, world.variables[pos, "variable.anvilcraft_down"])


if __name__ == "__main__":
    unittest.main()
