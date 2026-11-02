# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""生成本项目自制的加工台模型、方块、战利品与合成配置。"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES = (
    ("stamping_platform", u"冲压平台", "iron_block", None),
    ("crushing_table", u"粉碎台", "stone", "grindstone"),
    ("sifting_table", u"过筛台", "scaffolding_top", "scaffolding"),
    ("unpacking_table", u"解包台", "iron_trapdoor", "iron_trapdoor"),
)


def write(path, obj):
    path = os.path.join(ROOT, path)
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "wb") as handle:
        handle.write((json.dumps(obj, ensure_ascii=False, indent=4, separators=(",", ": "))
                      + u"\n").encode("utf-8"))


def cube(origin, size, texture=0):
    faces = {face: {"uv": [0, 0], "uv_size": [16, 16]} for face in (
        "up", "down", "north", "south", "west", "east")}
    return {"origin": origin, "size": size, "texture": texture, "uv": faces}


def main():
    path = os.path.join(ROOT, "resource_pack", "blocks.json")
    if os.path.isfile(path):
        with open(path, "rb") as handle:
            resources = json.load(handle)
    else:
        resources = {"format_version": [1, 1, 0]}
    names = []
    for name, title, top, attachment in TABLES:
        identifier = "anvilcraft:" + name
        components = {
            "minecraft:destroy_time": 2.0,
            "minecraft:explosion_resistance": 6.0,
            "minecraft:block_light_absorption": 0,
            "minecraft:loot": "loot_tables/blocks/" + name + ".json",
            "netease:block_entity": {"tick": True, "movable": False},
            "netease:listen_block_remove": {"value": True},
            "netease:solid": {"value": False},
            "netease:render_layer": {"value": "alpha"},
            "netease:aabb": {},
        }
        boxes = [{"min": [0, 0.8125, 0], "max": [1, 1, 1]}]
        boxes.extend({"min": [x, 0, z], "max": [x + 0.1875, 0.8125, z + 0.1875]}
                     for x in (0.0625, 0.75) for z in (0.0625, 0.75))
        components["netease:aabb"] = {"collision": boxes, "clip": boxes}
        write("behavior_pack/netease_blocks/" + name + ".json", {
            "format_version": "1.10.0", "minecraft:block": {
                "description": {"identifier": identifier, "category": "construction"},
                "components": components}})
        cubes = [cube([-8, 13, -8], [16, 3, 16], 1)]
        cubes.extend(cube([x, 0, z], [3, 13, 3]) for x in (-7, 4) for z in (-7, 4))
        if name == "crushing_table":
            cubes.extend(cube([x, 10, -6], [3, 3, 12], 1) for x in (-6, 3))
        elif name == "sifting_table":
            cubes.extend(cube([x, 10, -6], [1, 3, 12], 1) for x in (-5, -1, 3))
        elif name == "unpacking_table":
            cubes.append(cube([-6, 10, -6], [12, 2, 12], 1))
        write("resource_pack/models/netease_block/" + name + ".json", {
            "format_version": "1.13.0", "netease:block_geometry": {
                "description": {"identifier": identifier, "textures": ["iron_block", top], "use_ao": True},
                "bones": [{"name": "table", "pivot": [0, 0, 0], "cubes": cubes}]}})
        resources[identifier] = {"textures": "iron_block", "sound": "metal", "netease_model": identifier}
        entries = ["anvilcraft:stamping_platform"]
        if attachment:
            entries.append("minecraft:" + attachment)
        write("behavior_pack/loot_tables/blocks/" + name + ".json", {"pools": [
            {"rolls": 1, "entries": [{"type": "item", "name": entry, "weight": 1}]}
            for entry in entries]})
        names.append(u"tile." + identifier + u".name=" + title)
    write("resource_pack/blocks.json", resources)
    write("behavior_pack/recipes/stamping_platform.json", {
        "format_version": "1.12.0", "minecraft:recipe_shaped": {
            "description": {"identifier": "anvilcraft:stamping_platform"}, "tags": ["crafting_table"],
            "pattern": ["BAB", "B B", "B B"],
            "key": {"A": {"item": "minecraft:heavy_weighted_pressure_plate"},
                    "B": {"item": "minecraft:iron_ingot"}},
            "result": {"item": "anvilcraft:stamping_platform", "count": 1}}})
    path = os.path.join(ROOT, "resource_pack", "texts", "zh_CN.lang")
    with open(path, "rb") as handle:
        lines = handle.read().decode("utf-8").splitlines()
    identifiers = tuple("tile.anvilcraft:" + row[0] + ".name=" for row in TABLES)
    lines = [line for line in lines if not line.startswith(identifiers)]
    with open(path, "wb") as handle:
        handle.write((u"\n".join(lines + names) + u"\n").encode("utf-8"))


if __name__ == "__main__":
    main()
