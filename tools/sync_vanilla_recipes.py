# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""从上游默认数据包和基岩注册表生成原版落砧配方。"""

import argparse
from collections import defaultdict
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "behavior_pack", "anvilcraft_scripts", "common", "vanilla_catalog.py")
RESOURCE = re.compile(r"^data/([^/]+)/(recipe|tags/item|tags/block)/(.+)\.json$")
MC = "minecraft:"
ALIASES = {
    "bricks": "brick_block", "magma_block": "magma", "melon": "melon_block",
    "nether_brick": "netherbrick", "nether_bricks": "nether_brick", "slime_block": "slime",
    "snow_block": "snow", "snow": "snow_layer", "waxed_copper_block": "waxed_copper",
    "flowering_azalea_leaves": "azalea_leaves_flowered",
    "chain": "iron_chain", "shulker_box": "undyed_shulker_box",
}


def resources(path):
    """仅加载默认数据包的配方与物品标签，不加载可选数据包。"""
    if os.path.isdir(path):
        base = os.path.join(path, "data")
        for namespace in sorted(os.listdir(base)):
            for kind in ("recipe", "tags/item", "tags/block"):
                for parent, _, files in os.walk(os.path.join(base, namespace, kind)):
                    for name in files:
                        file_path = os.path.join(parent, name)
                        match = RESOURCE.match(os.path.relpath(file_path, path).replace(os.sep, "/"))
                        if match:
                            with open(file_path, "rb") as handle:
                                yield match.groups(), json.load(handle)
    else:
        with zipfile.ZipFile(path) as pack:
            for name in pack.namelist():
                match = RESOURCE.match(name)
                if match:
                    yield match.groups(), json.loads(pack.read(name))


def load_packs(paths):
    recipes = {}
    tags = defaultdict(list)
    block_tags = defaultdict(list)
    for path in paths:
        for (namespace, kind, name), obj in resources(path):
            key = namespace + ":" + name
            if kind == "recipe":
                recipes[key] = obj
            else:
                target = block_tags if kind == "tags/block" else tags
                if obj.get("replace"):
                    target[key] = []
                target[key].append(obj)
    return recipes, tags, block_tags


def vanilla_items(value, tags):
    if isinstance(value, list):
        return set().union(*(vanilla_items(entry, tags) for entry in value))
    if isinstance(value, dict):
        value = value["id"]
    if value.startswith("#"):
        result = set()
        for layer in tags.get(value[1:], ()):
            result.update(vanilla_items(layer["values"], tags))
            result.difference_update(vanilla_items(layer.get("remove", []), tags))
        return result
    return {value} if value.startswith(MC) else set()


def ingredient(spec, tags):
    if isinstance(spec, list):
        return set().union(*(ingredient(entry, tags) for entry in spec))
    if set(spec) == {"item"}:
        return vanilla_items(spec["item"], tags)
    if set(spec) == {"tag"}:
        return vanilla_items("#" + spec["tag"], tags)
    raise ValueError("unsupported ingredient: %r" % spec)


def wrap(recipe, compressible, storage, tags):
    kind = recipe.get("type")
    if kind not in (MC + "crafting_shapeless", MC + "crafting_shaped"):
        return
    result = recipe["result"]
    name = result["id"]
    if not name.startswith(MC):
        return
    count = result.get("count", 1)
    platform = "compress"
    if kind == MC + "crafting_shapeless":
        slots = recipe["ingredients"]
        if len(slots) == 1 and count > 1:
            platform = "unpack"
        elif len(slots) not in (4, 9) or name not in compressible | storage:
            return
    else:
        if name not in compressible:
            return
        pattern = list(recipe["pattern"])
        while not pattern[0].strip():
            pattern.pop(0)
        while not pattern[-1].strip():
            pattern.pop()
        left = min(len(row) - len(row.lstrip()) for row in pattern)
        right = max(len(row.rstrip()) for row in pattern)
        square = "".join(row[left:right] for row in pattern)
        if len(pattern) <= 1 or right - left != len(pattern) or " " in square:
            return
        slots = [recipe["key"][symbol] for symbol in square]
    common = set.intersection(*(ingredient(slot, tags) for slot in slots))
    if common:
        if result.get("components"):
            raise ValueError("unsupported result components: %r" % result)
        return platform, [(common, len(slots))], [(name, count)]


def explicit(recipe, tags):
    kind = recipe["type"]
    if kind == "anvilcraft:block_crush":
        name = recipe["result"]["block"]
        if name.startswith(MC):
            block = recipe["input"]["blocks"]
            if not isinstance(block, basestring) or block.startswith("#") or (
                    set(recipe["input"]) != {"blocks"} or set(recipe["result"]) != {"block"}):
                raise ValueError("unsupported block predicate: %r" % recipe)
            if block.startswith(MC):
                return "crush", [({block}, 1)], [(name, 1)]
    if kind in ("anvilcraft:item_compress", "anvilcraft:unpack", "anvilcraft:mesh",
                "anvilcraft:item_crush", "anvilcraft:stamping"):
        outputs = [(item["id"], item.get("count", 1)) for item in recipe["results"]]
        if all(name.startswith(MC) for name, _ in outputs):
            groups = [(vanilla_items(slot["items"], tags), slot.get("count", 1))
                      for slot in recipe["ingredients"]]
            if all(options for options, _ in groups):
                def supported(slot):
                    return not set(slot) - {"items", "count"} or (
                        kind == "anvilcraft:item_crush" and slot == {
                            "items": MC + "shulker_box", "components": {MC + "container": []}})
                if any(set(out) - {"id", "count"} for out in recipe["results"]) or not all(
                        supported(slot) for slot in recipe["ingredients"]):
                    raise ValueError("unsupported item properties: %r" % recipe)
                outputs = [(name, output_count(count)) for name, count in outputs]
                return kind.split(":")[1].replace("item_compress", "compress"), groups, outputs


def output_count(value):
    if isinstance(value, (int, long)) and value > 0:
        return value
    if (isinstance(value, dict) and set(value) == {"type", "n", "p"}
            and value["type"] == MC + "binomial" and value["n"] == int(value["n"])
            and value["n"] >= 0 and 0 <= value["p"] <= 1):
        return {"type": MC + "binomial", "n": int(value["n"]), "p": value["p"]}
    if (isinstance(value, dict) and set(value) == {"type", "min", "max"}
            and value["type"] == MC + "uniform" and 0 <= value["min"] <= value["max"]
            and all(value[key] == int(value[key]) for key in ("min", "max"))):
        return {"type": MC + "uniform", "min": int(value["min"]), "max": int(value["max"])}
    raise ValueError("unsupported output count: %r" % value)


def generated_mesh(tags):
    leaves = vanilla_items("#minecraft:leaves", tags)
    saplings = vanilla_items("#minecraft:saplings", tags)
    for leaf in sorted(leaves):
        tree = leaf.rsplit("_", 1)[0]
        plants = [plant for plant in sorted(saplings) if tree == (
            plant.rsplit("_", 1)[0] if "sapling" in plant else plant)]
        if not plants:
            continue
        # 与上游按树种 ID 关联树叶和树苗的规则一致，保留每种产物的独立概率。
        results = [{"id": leaf, "count": {"type": MC + "binomial", "n": 1, "p": 0.5}}]
        results.extend({"id": plant, "count": {"type": MC + "binomial", "n": 1, "p": 0.2}}
                       for plant in plants)
        yield "anvilcraft:mesh/generated/" + leaf.replace(":", "/"), {
            "type": "anvilcraft:mesh", "ingredients": [{"items": leaf}], "results": results}


def bedrock_id(name, registry):
    native = MC + ALIASES.get(name[len(MC):], name[len(MC):])
    if native not in registry:
        raise ValueError("missing Bedrock item: %s (from %s)" % (native, name))
    return native


def compile_recipes(recipes, tags, registry, block_tags):
    compressible = vanilla_items("#anvilcraft:compress_item", tags)
    storage = vanilla_items("#c:storage_blocks", tags)
    if not compressible or not storage:
        raise ValueError("missing compression tags")
    catalog = defaultdict(list)
    for source, recipe in sorted(list(recipes.items()) + list(generated_mesh(block_tags))):
        match = explicit(recipe, tags)
        if not match:
            match = wrap(recipe, compressible, storage, tags)
            if not match:
                continue
            source = "anvilcraft:generated/vanilla/%s/source/%s" % (match[0], source.replace(":", "/"))
        kind, inputs, outputs = match
        if recipe.get("neoforge:conditions"):
            raise ValueError("conditional recipe: %s" % source)
        if source == "anvilcraft:unpack/furnace_minecart" and MC + "furnace_minecart" not in registry:
            continue
        groups = [(sorted(bedrock_id(name, registry) for name in options), count)
                  for options, count in inputs]
        names = [name for options, _ in groups for name in options]
        if len(set(names)) != len(names):
            raise ValueError("overlapping input groups: %s" % source)
        results = [(bedrock_id(name, registry), count) for name, count in outputs]
        catalog[kind].append((source, groups, results))
    for rows in catalog.values():
        # 同平台的其他条件分值相同，按原料总数与产物种类数之和降序，同分按配方 ID 排序。
        rows.sort(key=lambda row: (-sum(n for _, n in row[1]) - len(row[2]), row[0]))
    return catalog


def compile_blocks(recipes, tags, registry):
    compressed, squeezed = [], []
    for source, recipe in sorted(recipes.items()):
        kind = recipe.get("type")
        if kind not in ("anvilcraft:block_compress", "anvilcraft:squeezing"):
            continue
        result = recipe["result"]
        if not result["block"].startswith(MC):
            continue
        if kind == "anvilcraft:block_compress":
            groups = [sorted(vanilla_items(slot["blocks"], tags)) for slot in recipe["inputs"]]
            if not all(groups):
                continue
            if len(groups) != 2 or any(set(slot) != {"blocks"} for slot in recipe["inputs"]):
                raise ValueError("unsupported block inputs: %s" % source)
            inputs = [[bedrock_id(name, registry) for name in group] for group in groups]
            compressed.append((source, inputs[0], inputs[1], bedrock_id(result["block"], registry)))
        else:
            transform = recipe["transform"]
            if not transform["id"].startswith(MC):
                continue
            block = recipe["ingredient"]["blocks"]
            if not block.startswith(MC):
                continue
            if (recipe.get("fluid") != [] or transform["amount"] != 250 or
                    set(recipe["ingredient"]) != {"blocks"} or
                    set(recipe) - {"type", "ingredient", "result", "fluid", "transform"}):
                raise ValueError("unsupported squeezing condition: %s" % source)
            if transform["id"] not in (MC + "water", MC + "lava", MC + "powder_snow"):
                raise ValueError("unsupported cauldron fluid: %s" % source)
            squeezed.append((source, bedrock_id(block, registry), bedrock_id(result["block"], registry),
                             transform["id"], transform["amount"]))
        if set(result) != {"block"} or recipe.get("neoforge:conditions"):
            raise ValueError("unsupported block result: %s" % source)
    return compressed, squeezed


def compile_smearing(recipes, tags, registry):
    smearing = []
    for source, recipe in sorted(recipes.items()):
        if recipe.get("type") != "anvilcraft:block_smear":
            continue
        groups = [sorted(vanilla_items(slot["blocks"], tags)) for slot in recipe["inputs"]]
        result = recipe["result"]
        if not result["block"].startswith(MC) or not all(groups):
            continue
        if len(groups) != 2 or set(result) != {"block"}:
            raise ValueError("unsupported smearing result: %s" % source)
        first, second = recipe["inputs"]
        condition = {}
        if first.get("properties"):
            if first["properties"] != [{"face": "ceiling"}] or groups[0] != [MC + "grindstone"]:
                raise ValueError("unsupported smearing state: %s" % source)
            condition["attachment"] = "hanging"
        if set(first) - {"blocks", "properties"} or set(second) != {"blocks"}:
            raise ValueError("unsupported smearing predicate: %s" % source)
        inputs = [[bedrock_id(name, registry) for name in group] for group in groups]
        smearing.append((source, inputs[0], condition, inputs[1], bedrock_id(result["block"], registry)))
    return smearing


def render(catalog, compressed, squeezed, smearing):
    lines = ["# -*- coding: utf-8 -*-", "# SPDX-License-Identifier: LGPL-3.0-or-later",
             u'"""由 tools/sync_vanilla_recipes.py 生成。"""', "", "CRUSH_RESULTS = {"]
    for _, groups, results in catalog["crush"]:
        names, count = groups[0]
        if len(names) != 1 or count != 1 or len(results) != 1 or results[0][1] != 1:
            raise ValueError("unsupported block replacement: %r" % groups)
        lines.append('    "%s": "%s",' % (names[0], results[0][0]))
    lines.append("}")
    for kind in ("compress", "unpack", "mesh", "item_crush", "stamping"):
        lines.extend(["", kind.upper() + " = ("])
        for source, groups, results in catalog[kind]:
            lines.extend(['    ("%s",' % source, "     %s," % json.dumps(groups, sort_keys=True),
                          "     %s)," % json.dumps(results, sort_keys=True)])
        lines.append(")")
    lines.extend(["", "BLOCK_COMPRESS = ("])
    for source, upper, lower, result in compressed:
        lines.extend(['    ("%s",' % source, "     %s, %s," % (json.dumps(upper), json.dumps(lower)),
                      '     "%s"),' % result])
    lines.extend([")", "", "SQUEEZING = {"])
    for source, block, result, fluid, amount in squeezed:
        lines.extend(['    "%s": ("%s",' % (block, source),
                      '        "%s", "%s", %d),' % (result, fluid, amount)])
    lines.append("}")
    lines.extend(["", "BLOCK_SMEAR = ("])
    for row in smearing:
        lines.append("    %s," % json.dumps(row, sort_keys=True))
    lines.append(")")
    return (u"\n".join(lines) + u"\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minecraft", required=True)
    parser.add_argument("--neoforge", required=True)
    parser.add_argument("--anvilcraft", required=True)
    parser.add_argument("--bedrock-items", required=True)
    parser.add_argument("--bedrock-blocks", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    paths = [args.minecraft, args.neoforge] + [
        os.path.join(args.anvilcraft, "src", folder, "resources") for folder in ("generated", "main")]
    print("Loading default recipes and tags...")
    recipes, tags, block_tags = load_packs(paths)
    with open(args.bedrock_items, "rb") as handle:
        registry = {row["name"] for row in json.load(handle)["data_items"]}
    catalog = compile_recipes(recipes, tags, registry, block_tags)
    with open(args.bedrock_blocks, "rb") as handle:
        blocks = {row["name"] for row in json.load(handle)["data_items"]}
    compressed, squeezed = compile_blocks(recipes, block_tags, blocks)
    smearing = compile_smearing(recipes, block_tags, blocks)
    data = render(catalog, compressed, squeezed, smearing)
    if args.check:
        with open(CATALOG, "rb") as handle:
            if handle.read().replace("\r\n", "\n") != data:
                sys.exit("catalog differs from upstream")
    else:
        with open(CATALOG, "wb") as handle:
            handle.write(data)
    print("crush=%d compress=%d unpack=%d mesh=%d item_crush=%d stamping=%d block_compress=%d squeezing=%d block_smear=%d" % (
        len(catalog["crush"]), len(catalog["compress"]), len(catalog["unpack"]), len(catalog["mesh"]),
        len(catalog["item_crush"]), len(catalog["stamping"]), len(compressed), len(squeezed), len(smearing)))


if __name__ == "__main__":
    main()
