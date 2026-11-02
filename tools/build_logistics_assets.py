# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""生成磁铁物流方块与自制模型，并转换相应的上游合成配方。"""

import argparse
import json
import os

from build_machine_assets import ROOT, cube, write

BLOCKS = (
    ("magnet_block", u"磁铁块"), ("hollow_magnet_block", u"空心磁铁块"),
    ("held_anvil", u"铁砧"), ("held_chipped_anvil", u"开裂的铁砧"),
    ("held_damaged_anvil", u"损坏的铁砧"), ("chute", u"溜槽"), ("magnetic_chute", u"磁力溜槽"),
)
RECIPES = (
    "chute", "magnetic_chute", "magnet_block", "hollow_magnet_block",
    "magnet_block_from_hollow_magnet_block", "hollow_magnet_block_from_magnet_block",
    "magnet_ingot_from_block", "magnet_ingot_from_hollow_block",
)


def main(upstream):
    with open(os.path.join(ROOT, "resource_pack", "blocks.json"), "rb") as handle:
        resources = json.load(handle)
    names = [u"item.anvilcraft:magnet_ingot.name=磁铁锭"]
    for name, title in BLOCKS:
        held, chute = name.startswith("held_"), name.endswith("chute")
        identifier = "anvilcraft:" + name
        description = {"identifier": identifier, "category": "construction"}
        if held:
            description["register_to_create_menu"] = False
        components = {
            "minecraft:destroy_time": 5.0 if held else 2.0,
            "minecraft:explosion_resistance": 6.0,
            "minecraft:loot": "loot_tables/blocks/" + name + ".json",
            "netease:listen_block_remove": {"value": True},
            "netease:block_entity": {"tick": not held, "movable": False},
        }
        if chute or not held:
            components["netease:redstone"] = {"type": "consumer"}
        if chute:
            components["netease:face_directional"] = {"type": "facing_direction"}
            resources[identifier] = {"sound": "metal", "textures": {
                "up": "hopper_top", "down": "hopper_outside", "north": "dropper_front_horizontal",
                "south": "iron_block", "east": "iron_block", "west": "iron_block"}}
        else:
            components["minecraft:block_light_absorption"] = 0
            cubes = []
            if held:
                components["netease:face_directional"] = {"type": "direction"}
                components["netease:aabb"] = {
                    "collision": {"min": [0.125, 0, 0], "max": [0.875, 1, 1]},
                    "clip": {"min": [0.125, 0, 0], "max": [0.875, 1, 1]}}
                cubes = [cube([-6, 0, -8], [12, 4, 16]), cube([-4, 4, -5], [8, 6, 10]),
                         cube([-5, 10, -8], [10, 6, 16], 1)]
                stage = ("held_anvil", "held_chipped_anvil", "held_damaged_anvil").index(name)
                cubes[-1]["texture"] = 0
                cubes[-1]["uv"]["up"]["texture"] = 1
                textures = ["anvil_base", ("flattened_anvil_top", "chipped_anvil_top", "damaged_anvil_top")[stage]]
            elif name == "hollow_magnet_block":
                cubes = [cube([-8, 0, -8], [5, 16, 16]), cube([3, 0, -8], [5, 16, 16]),
                         cube([-3, 0, -8], [6, 16, 5], 1), cube([-3, 0, 3], [6, 16, 5], 1)]
                boxes = [{"min": [0, 0, 0], "max": [0.3125, 1, 1]},
                         {"min": [0.6875, 0, 0], "max": [1, 1, 1]},
                         {"min": [0.3125, 0, 0], "max": [0.6875, 1, 0.3125]},
                         {"min": [0.3125, 0, 0.6875], "max": [0.6875, 1, 1]}]
                components["netease:aabb"] = {"collision": boxes, "clip": boxes}
                textures = ["iron_block", "redstone_block"]
            else:
                cubes = [cube([-8, 0, -8], [16, 16, 16]), cube([-8, 6, -8.01], [16, 4, 0.01], 1),
                         cube([-8, 6, 8], [16, 4, 0.01], 1)]
                textures = ["iron_block", "redstone_block"]
            write("resource_pack/models/netease_block/" + name + ".json", {
                "format_version": "1.13.0", "netease:block_geometry": {
                    "description": {"identifier": identifier, "textures": textures, "use_ao": True},
                    "bones": [{"name": "body", "pivot": [0, 0, 0], "cubes": cubes}]}})
            resources[identifier] = {"sound": "anvil" if held else "metal", "textures": textures[0],
                                     "netease_model": identifier}
        write("behavior_pack/netease_blocks/" + name + ".json", {
            "format_version": "1.10.0", "minecraft:block": {
                "description": description, "components": components}})
        write("behavior_pack/loot_tables/blocks/" + name + ".json", {"pools": [] if held else [
            {"rolls": 1, "entries": [{"type": "item", "name": identifier, "weight": 1}]}]})
        names.append(u"tile." + identifier + u".name=" + title)
    write("resource_pack/blocks.json", resources)
    write("behavior_pack/netease_items_beh/magnet_ingot.json", {
        "format_version": "1.10", "minecraft:item": {
            "description": {"identifier": "anvilcraft:magnet_ingot", "category": "items"},
            "components": {"minecraft:max_stack_size": 64}}})
    write("resource_pack/netease_items_res/magnet_ingot.json", {
        "format_version": "1.10", "minecraft:item": {
            "description": {"identifier": "anvilcraft:magnet_ingot"},
            "components": {"minecraft:icon": "iron_ingot"}}})
    for name in RECIPES:
        path = os.path.join(upstream, "src", "generated", "resources", "data", "anvilcraft", "recipe", name + ".json")
        with open(path, "rb") as handle:
            original = json.load(handle)
        shaped = original["type"] == "minecraft:crafting_shaped"
        recipe = {"description": {"identifier": "anvilcraft:" + name}, "tags": ["crafting_table"]}
        if shaped:
            recipe.update(pattern=original["pattern"], key=original["key"])
        else:
            recipe["ingredients"] = original["ingredients"]
        recipe["result"] = {"item": original["result"]["id"], "count": original["result"].get("count", 1)}
        write("behavior_pack/recipes/" + name + ".json", {
            "format_version": "1.12.0",
            "minecraft:recipe_shaped" if shaped else "minecraft:recipe_shapeless": recipe})
    path = os.path.join(ROOT, "resource_pack", "texts", "zh_CN.lang")
    with open(path, "rb") as handle:
        lines = handle.read().decode("utf-8").splitlines()
    prefixes = tuple(line.split("=", 1)[0] + "=" for line in names)
    lines = [line for line in lines if not line.startswith(prefixes)]
    with open(path, "wb") as handle:
        handle.write((u"\n".join(lines + names) + u"\n").encode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anvilcraft", default=os.path.join(ROOT, "..", "AnvilCraft"))
    main(parser.parse_args().anvilcraft)
