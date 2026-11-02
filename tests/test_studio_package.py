# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""从实际解压目录按网易附加包规范查找两类包及各自的清单。"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import package_addon


class StudioPackageTests(unittest.TestCase):

    def test_import_main_and_lab_from_extracted_zip(self):
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir)
        self.assertEqual(0, package_addon.main(temp_dir))
        headers = {}
        dependencies = []
        for name in ("AnvilCraft-Studio", "AnvilCraft-Lab-Studio"):
            filename = os.path.join(temp_dir, name + ".zip")
            destination = os.path.join(temp_dir, name)
            with zipfile.ZipFile(filename) as archive:
                # 只复制文件，重现工作台导入时空目录可能丢失的情况。
                for entry in archive.namelist():
                    if not entry.endswith("/"):
                        archive.extract(entry, destination)

            kinds = []
            for directory in os.listdir(destination):
                pack = os.path.join(destination, directory)
                for marker, kind in (("entities", "data"), ("textures", "resources")):
                    if not os.path.isdir(os.path.join(pack, marker)):
                        continue
                    with open(os.path.join(pack, "manifest.json"), "rb") as manifest:
                        data = json.loads(manifest.read().decode("utf-8"))
                    self.assertIn(kind, [module["type"] for module in data["modules"]])
                    header = data["header"]
                    self.assertNotIn(header["uuid"], headers)
                    headers[header["uuid"]] = header["version"]
                    dependencies.extend(data.get("dependencies", []))
                    kinds.append(kind)
            self.assertItemsEqual(["data", "resources"], kinds)

        for dependency in dependencies:
            self.assertEqual(dependency["version"], headers[dependency["uuid"]])
