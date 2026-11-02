# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""使用 Python 2.7 检查项目脚本语法和 JSON，避免检查时执行游戏接口。"""

from __future__ import absolute_import, print_function

import json
import os
import sys


def _report(stream, message):
    stream.write((message + u"\n").encode("utf-8"))


def main():
    """检查开发目录并返回退出码，供本地开发与后续持续集成使用。"""
    if sys.version_info[:2] != (2, 7):
        sys.stderr.write("Python 2.7 is required; current version: {0}\n".format(
            sys.version.split()[0]))
        return 2

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    counts = {".py": 0, ".json": 0}
    errors = 0
    for directory in ("behavior_pack", "resource_pack", "docs", "tools", "tests"):
        for current, directories, files in os.walk(os.path.join(root, directory)):
            directories[:] = sorted(name for name in directories if name != "__pycache__")
            for name in sorted(files):
                extension = os.path.splitext(name)[1]
                if extension not in counts:
                    continue
                path = os.path.join(current, name)
                relative = os.path.relpath(path, root).decode(sys.getfilesystemencoding())
                counts[extension] += 1
                try:
                    with open(path, "rb") as source:
                        content = source.read()
                    if extension == ".py":
                        content.decode("utf-8")
                        compile(content, path, "exec")
                    else:
                        json.loads(content.decode("utf-8"))
                except (IOError, OSError, SyntaxError, ValueError) as error:
                    errors += 1
                    _report(sys.stderr, u"检查失败：{0}：{1}".format(relative, error))

    _report(sys.stdout, u"已检查 {0} 个 Python 文件、{1} 个 JSON 文件；错误 {2} 个。".format(
        counts[".py"], counts[".json"], errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
