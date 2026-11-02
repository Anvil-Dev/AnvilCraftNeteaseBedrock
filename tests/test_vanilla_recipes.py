# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""验证上游转换条件，以及每条游戏配方的原料变种与产物可达性。"""

from collections import Counter
from itertools import product
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "behavior_pack"))

from anvilcraft_scripts.common.drop_recipes import Drop, RECIPES, SCAFFOLDING, match_drops, products
from sync_vanilla_recipes import explicit, generated_mesh, output_count, wrap


class VanillaRecipeTests(unittest.TestCase):

    def test_every_input_variant_reaches_its_declared_products(self):
        for platform, recipes in RECIPES.items():
            for recipe in recipes:
                for names in product(*(options for options, _ in recipe.inputs)):
                    drops = [Drop(i, (), {"newItemName": name, "count": recipe.inputs[i][1]})
                             for i, name in enumerate(names)]
                    batch = match_drops(platform, drops)
                    self.assertIsNotNone(batch, recipe.source)
                    self.assertEqual(recipe.source, batch.recipe.source)
                    self.assertItemsEqual([(d, d.item["count"]) for d in drops], batch.debits)
                    result = Counter()
                    for item in products(batch, roll=lambda: 0):
                        result[item["newItemName"]] += item["count"]
                    expected = {}
                    for name, count in recipe.outputs:
                        expected[name] = count["n"] if isinstance(count, dict) else count
                    self.assertEqual(expected, dict(result), recipe.source)

    def test_mesh_rolls_each_result_for_each_input_with_strict_probability_boundaries(self):
        drop = Drop("gravel", (), {"newItemName": "minecraft:gravel", "count": 2})
        batch = match_drops(SCAFFOLDING, [drop])
        rolls = iter((0.49, 0.5, 0.249, 0.25, 0.199, 0.2))
        result = list(products(batch, roll=rolls.next))
        self.assertEqual([("minecraft:gravel", 1), ("minecraft:flint", 1), ("minecraft:iron_nugget", 1)],
                         [(item["newItemName"], item["count"]) for item in result])
        self.assertEqual([(drop, 2)], batch.debits)

    def test_mesh_limit_and_empty_roll_results(self):
        drop = Drop("sand", (), {"newItemName": "minecraft:sand", "count": 65})
        batch = match_drops(SCAFFOLDING, [drop])
        self.assertEqual((64, [(drop, 64)]), (batch.times, batch.debits))
        self.assertEqual([], list(products(batch, roll=lambda: 0.99)))
        self.assertEqual([64, 64, 64], [item["count"] for item in products(batch, roll=lambda: 0)])

    def test_generated_mesh_follows_upstream_tree_ids_and_normalizes_binomial_counts(self):
        tags = {"minecraft:leaves": [{"values": ["minecraft:oak_leaves", "minecraft:mangrove_leaves",
                                               "minecraft:flowering_azalea_leaves"]}],
                "minecraft:saplings": [{"values": ["minecraft:oak_sapling", "minecraft:mangrove_propagule",
                                                   "minecraft:flowering_azalea"]}]}
        generated = list(generated_mesh(tags))
        plants = [result["id"] for _, recipe in generated for result in recipe["results"][1:]]
        self.assertItemsEqual(["minecraft:oak_sapling", "minecraft:flowering_azalea"], plants)
        count = output_count({"type": "minecraft:binomial", "n": 1.0, "p": 0.2})
        self.assertEqual(1, count["n"])
        self.assertIsInstance(count["n"], int)
        self.assertRaises(ValueError, output_count, {"type": "minecraft:uniform", "min": 1, "max": 2})

    def test_shaped_compression_uses_only_the_common_vanilla_ingredient(self):
        iron = "minecraft:iron_ingot"
        block = "minecraft:iron_block"
        tags = {"c:ingots": [{"values": ["#c:mixed"]}],
                "c:mixed": [{"values": [iron, "example:ingot", "minecraft:copper_ingot"]}]}
        recipe = {"type": "minecraft:crafting_shaped", "pattern": [" AB", " AA"],
                  "key": {"A": {"tag": "c:ingots"}, "B": {"item": iron}},
                  "result": {"id": block}}
        self.assertEqual(("compress", [({iron}, 4)], [(block, 1)]),
                         wrap(recipe, {block}, set(), tags))
        self.assertIsNone(wrap(recipe, set(), {block}, tags))
        recipe["key"]["B"] = {"item": "minecraft:coal"}
        self.assertIsNone(wrap(recipe, {block}, set(), tags))
        recipe["pattern"] = ["AAA", "   ", "AAA"]
        self.assertIsNone(wrap(recipe, {block}, set(), tags))

    def test_only_one_to_many_and_vanilla_outputs_are_unpacked(self):
        recipe = {"type": "minecraft:crafting_shapeless",
                  "ingredients": [[{"item": "example:log"}, {"item": "minecraft:oak_log"}]],
                  "result": {"id": "minecraft:oak_planks", "count": 4}}
        self.assertEqual(("unpack", [({"minecraft:oak_log"}, 1)], [("minecraft:oak_planks", 4)]),
                         wrap(recipe, set(), set(), {}))
        recipe["result"]["count"] = 1
        self.assertIsNone(wrap(recipe, set(), set(), {}))
        recipe["result"] = {"id": "example:planks", "count": 4}
        self.assertIsNone(wrap(recipe, set(), set(), {}))
        self.assertIsNone(explicit({"type": "anvilcraft:unpack",
                                    "ingredients": [{"items": "minecraft:minecart"}],
                                    "results": [{"id": "minecraft:minecart"},
                                                {"id": "anvilcraft:fluid_tank"}]}, {}))
