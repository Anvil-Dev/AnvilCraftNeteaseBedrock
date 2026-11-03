# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""复制原仓库贴图，并将已移植模型转换为网易方块实体资源。"""

import argparse
import json
import os
import struct
import sys
import zipfile
from cStringIO import StringIO

from PIL import Image
from build_machine_assets import ROOT
from java_models import JavaModels, geometry, resource_config
from item_icons import render_icon

MODELS = (
    ("stamping_platform", "anvilcraft:block/processing_table"),
    ("crushing_table", "anvilcraft:block/processing_table_crushing"),
    ("sifting_table", "anvilcraft:block/processing_table_sifting"),
    ("unpacking_table", "anvilcraft:block/processing_table_unpacking"),
    ("magnet_block", "anvilcraft:block/magnet_block"),
    ("hollow_magnet_block", "anvilcraft:block/hollow_magnet_block"),
    ("chute", "anvilcraft:block/chute_side"),
    ("magnetic_chute", "anvilcraft:block/magnetic_chute"),
    ("held_anvil", "minecraft:block/anvil"),
    ("held_chipped_anvil", "minecraft:block/chipped_anvil"),
    ("held_damaged_anvil", "minecraft:block/damaged_anvil"),
)
VANILLA = {"minecraft:block/anvil": "textures/blocks/anvil_base",
           "minecraft:block/anvil_top": "textures/blocks/anvil_top_damaged_0",
           "minecraft:block/chipped_anvil_top": "textures/blocks/anvil_top_damaged_1",
           "minecraft:block/damaged_anvil_top": "textures/blocks/anvil_top_damaged_2"}


def texture_key(name):
    return "anvilcraft_" + name.split(":", 1)[1].replace("/", "_")


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=4, sort_keys=True, separators=(",", ": "))
            + u"\n").encode("utf-8")


def compile_assets(upstream, minecraft):
    models = JavaModels(upstream, minecraft)
    generated, terrain, blocks, controllers = {}, {}, {}, {}
    sizes, images = {}, {}

    def texture(name):
        if name in VANILLA:
            sizes[name] = (16, 16)
            path = VANILLA[name]
            namespace, relative = name.split(":", 1)
            with zipfile.ZipFile(minecraft) as pack:
                image = pack.read("assets/%s/textures/%s.png" % (namespace, relative))
            images[name] = Image.open(StringIO(image)).convert("RGBA")
        else:
            namespace, relative = name.split(":", 1)
            if namespace != "anvilcraft":
                raise ValueError("unsupported texture: " + name)
            source = os.path.join(upstream, "src/main/resources/assets/anvilcraft/textures", relative + ".png")
            with open(source, "rb") as handle:
                data = handle.read()
            if not data.startswith("\x89PNG\r\n\x1a\n"):
                raise ValueError("invalid PNG: " + source)
            sizes[name] = struct.unpack(">II", data[16:24])
            path = "textures/anvilcraft/" + relative
            generated["resource_pack/" + path + ".png"] = data
            images[name] = Image.open(StringIO(data)).convert("RGBA")
        terrain[texture_key(name)] = {"textures": path}
        return path

    for model_index, (name, original) in enumerate(MODELS, 1):
        print("model %d/%d: %s" % (model_index, len(MODELS), name))
        sys.stdout.flush()
        model = models.read(original)
        variants = [(model, None)]
        if name == "chute":
            variants.insert(0, (models.read("anvilcraft:block/chute"), [-90, 0, 0]))
        elif name == "magnetic_chute":
            # 六面朝向以北为基准，上游的磁力溜槽基础模型朝上。
            variants[0] = (model, [90, 0, 0])
        elif name in ("magnet_block", "hollow_magnet_block"):
            variants.append((models.read("anvilcraft:block/demagnetized_" + name), None))
        used = sorted(set(models.texture(variant, face["texture"]) for variant, _ in variants
                          for element in variant["elements"] for face in element["faces"].values()))
        textures, geometries, renderers, geometry_rows = {}, {}, [], []
        for index, tex in enumerate(used):
            key = "material_%d" % index
            textures[key] = texture(tex)
            identifiers = []
            for variant_index, (variant, rotation) in enumerate(variants):
                alias = key + "_%d" % variant_index
                identifier = "geometry.anvilcraft.%s.%s" % (name, alias)
                row = geometry(models, variant, tex, identifier, sizes[tex], rotation)
                geometry_rows.append(row)
                geometries[alias] = identifier
                identifiers.append("Geometry." + alias)
            render_id = "controller.render.anvilcraft.%s.%s" % (name, key)
            renderer = {"geometry": identifiers[0], "materials": [{"*": "Material.default"}],
                        "textures": ["Texture." + key]}
            if len(variants) > 1:
                renderer["arrays"] = {"geometries": {"Array.shape": identifiers}}
                selector = "variable.anvilcraft_down ? 0 : 1" if name == "chute" else "variable.anvilcraft_lit"
                renderer["geometry"] = "Array.shape[" + selector + "]"
            controllers[render_id] = renderer
            renderers.append(render_id)
        particle = models.texture(model, model["textures"]["particle"])
        texture(particle)
        description = {"identifier": "anvilcraft:" + name, "materials": {"default": "entity_alphatest"},
                       "textures": textures, "geometry": geometries, "render_controllers": renderers}
        if name == "chute":
            description["scripts"] = {"initialize": ["variable.anvilcraft_down = 1;"]}
        elif name in ("magnet_block", "hollow_magnet_block"):
            description["scripts"] = {"initialize": ["variable.anvilcraft_lit = 0;"]}
        generated["resource_pack/entity/" + name + ".entity.json"] = encode({
            "format_version": "1.10.0", "minecraft:client_entity": {"description": description}})
        generated["resource_pack/models/entity/" + name + ".geo.json"] = encode({
            "format_version": "1.21.0", "minecraft:geometry": geometry_rows})
        blocks["anvilcraft:" + name] = resource_config(name, texture_key(particle))
        icon = "textures/anvilcraft/icons/" + name
        icon_name = "minecraft:item/" + name[5:] if name.startswith("held_") else "anvilcraft:item/" + name
        icon_model = models.read(icon_name)
        for element in icon_model["elements"]:
            for face in element["faces"].values():
                tex = models.texture(icon_model, face["texture"])
                if tex not in images:
                    texture(tex)
        generated["resource_pack/" + icon + ".png"] = render_icon(models, icon_model, images)
        terrain["anvilcraft_icon_" + name] = {"textures": icon}
    item_textures = {}
    for name in ("magnet_ingot", "guide_book"):
        tex = "anvilcraft:item/" + name
        item_textures["anvilcraft_" + name] = {"textures": texture(tex)}
        generated["resource_pack/netease_items_res/" + name + ".json"] = encode({
            "format_version": "1.10", "minecraft:item": {
                "description": {"identifier": "anvilcraft:" + name},
                "components": {"minecraft:icon": "anvilcraft_" + name}}})
    generated["resource_pack/render_controllers/machines.render_controllers.json"] = encode({
        "format_version": "1.8.0", "render_controllers": controllers})
    generated["resource_pack/textures/terrain_texture.json"] = encode({
        "resource_pack_name": "anvilcraft", "texture_name": "atlas.terrain", "texture_data": terrain})
    generated["resource_pack/textures/item_texture.json"] = encode({
        "resource_pack_name": "anvilcraft", "texture_name": "atlas.items", "texture_data": item_textures})
    return generated, blocks


def main(upstream, minecraft, check=False):
    print("Converting upstream machine models and copying textures...")
    sys.stdout.flush()
    generated, blocks = compile_assets(upstream, minecraft)
    path = os.path.join(ROOT, "resource_pack/blocks.json")
    with open(path, "rb") as handle:
        resources = json.load(handle)
    resources.update(blocks)
    generated["resource_pack/blocks.json"] = encode(resources)
    for relative, data in sorted(generated.items()):
        path = os.path.join(ROOT, relative)
        if check:
            with open(path, "rb") as handle:
                current = handle.read()
            if current != data:
                raise ValueError("visual asset differs: " + relative)
        else:
            parent = os.path.dirname(path)
            if not os.path.isdir(parent):
                os.makedirs(parent)
            with open(path, "wb") as handle:
                handle.write(data)
    print("models=%d textures=%d files=%d" % (len(MODELS), sum(p.endswith(".png") for p in generated), len(generated)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anvilcraft", default=os.path.join(ROOT, "..", "AnvilCraft"))
    parser.add_argument("--minecraft", default=os.path.join(
        os.environ["USERPROFILE"], ".gradle/caches/neoformruntime/artifacts/minecraft_1.21.1_client.jar"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    main(args.anvilcraft, args.minecraft, args.check)
