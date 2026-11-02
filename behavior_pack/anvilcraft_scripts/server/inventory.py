# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""保存机器物品与设置，方块替换和拆除期间仍可取回完整物品数据。"""

from copy import deepcopy

from anvilcraft_scripts.common.drop_recipes import item_name


def cell_key(dim, pos):
    return "%d:%d:%d:%d" % ((dim,) + tuple(pos))


def stack_equal(left, right):
    a, b = dict(left), dict(right)
    a.pop("count", None)
    b.pop("count", None)
    return a == b


def insert(items, item, slots, maximum, same_item_limit=False):
    """返回新库存和实际接收数量，附加数据不同的物品分别占槽。"""
    result = deepcopy(items)
    available = item["count"]
    if same_item_limit:
        available = min(available, max(0, maximum - sum(
            row["count"] for row in result if item_name(row) == item_name(item))))
    remaining = available
    for row in result:
        if stack_equal(row, item):
            take = min(remaining, max(0, maximum - row["count"]))
            row["count"] += take
            remaining -= take
    while remaining and len(result) < slots:
        row = deepcopy(item)
        row["count"] = min(remaining, maximum)
        result.append(row)
        remaining -= row["count"]
    return result, available - remaining


class Inventories(object):
    """以世界扩展数据为库存来源，保存失败时保留此前记录。"""

    KEY = "anvilcraft:machine_inventories_v1"

    def __init__(self, factory, level, log):
        self._factory, self._level, self._log = factory, level, log
        self._store = None
        self._records = {}
        self._cursor = 0

    def load(self):
        if self._store is None:
            self._store = self._factory.CreateExtraData(self._level)
            self._records = self._store.GetExtraData(self.KEY) or {}

    def get(self, dim, pos):
        self.load()
        return deepcopy(self._records.get(cell_key(dim, pos), {"items": []}))

    def scan(self, limit):
        self.load()
        keys = sorted(self._records)
        if not keys:
            return []
        result = []
        for _ in range(min(limit, len(keys))):
            self._cursor %= len(keys)
            key = keys[self._cursor]
            self._cursor += 1
            values = [int(part) for part in key.split(":")]
            result.append((values[0], tuple(values[1:]), deepcopy(self._records[key])))
        return result

    def write(self, dim, pos, record):
        return self.change([(dim, pos, record)])

    def change(self, updates):
        self.load()
        records = deepcopy(self._records)
        for dim, pos, record in updates:
            key = cell_key(dim, pos)
            if record is None:
                records.pop(key, None)
            else:
                records[key] = deepcopy(record)
        if not self._store.SetExtraData(self.KEY, records, True):
            self._log.error("[AnvilCraft] could not save machine inventories")
            return False
        self._records = records
        return True
