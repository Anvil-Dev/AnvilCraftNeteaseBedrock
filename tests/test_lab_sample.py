# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""区分样品正常往返与引擎丢失物品附加数据的情况。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "addon", "behavior_pack"))
from anvilcraft_lab_scripts.sample import make_sample, sample_status, within_reach


class SampleTests(unittest.TestCase):

    def test_round_trip_accepts_lists_and_additional_engine_tags(self):
        item = make_sample()
        item["enchantData"] = [[15, 1]]
        item["userData"]["Damage"] = {"__type__": 3, "__value__": 177}
        self.assertEqual(u"耐久、附魔和标记均相符", sample_status(item))

    def test_damage_enchant_and_marker_are_checked_independently(self):
        for field, label in (("durability", u"耐久"), ("enchantData", u"附魔"), ("userData", u"userData")):
            item = make_sample()
            del item[field]
            result = sample_status(item)
            self.assertIn(u"不匹配", result)
            self.assertIn(label, result)

    def test_remote_and_unloaded_players_cannot_use_the_probe(self):
        self.assertTrue(within_reach((1.5, 8.5, -1.5), (1, 8, -2)))
        self.assertFalse(within_reach((8, 8.5, -1.5), (1, 8, -2)))
        self.assertFalse(within_reach(None, (1, 8, -2)))
