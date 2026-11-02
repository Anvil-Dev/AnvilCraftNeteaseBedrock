# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""构建可分别启用的游戏包，以及供 MC Studio 本地导入的 ZIP。"""

from __future__ import absolute_import, print_function

import json
import os
import sys
import uuid
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = (("behavior_pack", "behavior_pack_anvilcraft"),
        ("resource_pack", "resource_pack_anvilcraft"))
LAB = (("tests/addon/behavior_pack", "behavior_pack_anvilcraft_lab"),
       ("tests/addon/resource_pack", "resource_pack_anvilcraft_lab"))
EXTENSIONS = (".py", ".json", ".lang", ".mcfunction", ".png")
LEGAL_FILES = ("LICENSE", "ASSETS_LICENSE", "NOTICE.md")
PACK_DIRECTORIES = {"data": "entities", "resources": "textures"}


def _manifest(path):
    with open(os.path.join(ROOT, path, "manifest.json"), "rb") as source:
        return json.loads(source.read().decode("utf-8"))


def check_packs():
    """构建前检查双包配对和依赖版本，避免实验包覆盖主包。"""
    seen = set()
    headers = {}
    packs = [_manifest(path) for path, _ in MAIN + LAB]
    for (path, _), pack in zip(MAIN + LAB, packs):
        header = pack["header"]
        for module in pack["modules"]:
            marker = os.path.join(ROOT, path, PACK_DIRECTORIES[module["type"]])
            if not os.path.isdir(marker):
                raise ValueError("missing MC Studio pack directory: " + marker)
        if header["min_engine_version"] != [1, 21, 130]:
            raise ValueError("min_engine_version: " + header["uuid"])
        for part in [header] + pack["modules"]:
            value = str(uuid.UUID(part["uuid"]))
            if value in seen:
                raise ValueError("duplicate uuid: " + value)
            seen.add(value)
        headers[header["uuid"]] = header["version"]
    for i, pack in enumerate(packs):
        expected = ((1,), (), (0, 3), ())[i]
        deps = pack.get("dependencies", [])
        if {ref["uuid"] for ref in deps} != {packs[j]["header"]["uuid"] for j in expected}:
            raise ValueError("pack dependencies: " + pack["header"]["uuid"])
        for ref in deps:
            if ref["version"] != headers[ref["uuid"]]:
                raise ValueError("dependency version: " + ref["uuid"])


def _entry(archive, filename, path=None):
    info = zipfile.ZipInfo(filename, (1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    if path is None:
        info.external_attr = (0o40755 << 16) | 0x10
        archive.writestr(info, "")
        return
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    with open(path, "rb") as source:
        archive.writestr(info, source.read())


def _build(destination, packs):
    with zipfile.ZipFile(destination, "w") as archive:
        for source, name in packs:
            parent = os.path.join(ROOT, source)
            for current, dirs, files in os.walk(parent):
                dirs[:] = sorted(d for d in dirs if not d.startswith((".", "__pycache__")))
                prefix = name + "/"
                if current != parent:
                    prefix += os.path.relpath(current, parent).replace(os.sep, "/") + "/"
                _entry(archive, prefix)
                for file_name in sorted(files):
                    # 网易模板用 .dummy 保留目录，工作台按文件复制组件时也会带上它。
                    if file_name != ".dummy" and not file_name.endswith(EXTENSIONS):
                        continue
                    path = os.path.join(current, file_name)
                    _entry(archive, prefix + file_name, path)
            if name.startswith("behavior_pack"):
                for file_name in LEGAL_FILES:
                    _entry(archive, name + "/" + file_name, os.path.join(ROOT, file_name))


def main(output=None):
    if sys.version_info[:2] != (2, 7):
        sys.stderr.write("Python 2.7 is required.\n")
        return 2
    check_packs()
    if output is None:
        output = os.path.join(ROOT, "dist")
    if not os.path.isdir(output):
        os.makedirs(output)
    for name, packs in (("AnvilCraft.mcaddon", MAIN), ("AnvilCraft-Lab.mcaddon", LAB),
                        ("AnvilCraft-Studio.zip", MAIN), ("AnvilCraft-Lab-Studio.zip", LAB)):
        destination = os.path.join(output, name)
        _build(destination, packs)
        print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
