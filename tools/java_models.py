# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""读取 Java 方块模型并转换坐标、逐面 UV 与立方体旋转。"""

from copy import deepcopy
import json
import os
import zipfile


def resource_config(name, particle):
    """让网易方块实体与手持形态使用同一份转换模型。"""
    return {"sound": "anvil" if name.startswith("held_") else "metal", "textures": particle,
            "client_entity": {"identifier": "anvilcraft:" + name,
                              "hand_model_use_client_entity": True,
                              "block_icon": "anvilcraft_icon_" + name, "destroyed_textures": particle}}


def split_id(value):
    namespace, path = value.split(":", 1) if ":" in value else ("minecraft", value)
    if path.startswith("/") or ".." in path.split("/"):
        raise ValueError("invalid resource path: " + value)
    return namespace, path


class JavaModels(object):
    """解析模型继承和纹理别名，保持父模型不受子模型的覆盖影响。"""

    def __init__(self, upstream, minecraft):
        self.upstream, self.minecraft = upstream, minecraft
        self._models = {}

    def read(self, name, parents=()):
        if name in parents:
            raise ValueError("cyclic model parent: " + name)
        if name in self._models:
            return deepcopy(self._models[name])
        namespace, path = split_id(name)
        relative = "assets/%s/models/%s.json" % (namespace, path)
        if namespace == "minecraft":
            with zipfile.ZipFile(self.minecraft) as pack:
                raw = json.loads(pack.read(relative))
        elif namespace == "anvilcraft":
            for folder in ("main", "generated"):
                source = os.path.join(self.upstream, "src", folder, "resources", relative)
                if os.path.isfile(source):
                    with open(source, "rb") as handle:
                        raw = json.load(handle)
                    break
            else:
                raise ValueError("missing model: " + name)
        else:
            raise ValueError("unsupported model namespace: " + namespace)
        model = self.read(raw["parent"], parents + (name,)) if "parent" in raw else {}
        textures = dict(model.get("textures", {}))
        textures.update(raw.get("textures", {}))
        display = dict(model.get("display", {}))
        display.update(raw.get("display", {}))
        model.update(raw)
        model["textures"] = textures
        model["display"] = display
        self._models[name] = deepcopy(model)
        return model

    def texture(self, model, value):
        seen = set()
        while value.startswith("#"):
            if value in seen:
                raise ValueError("cyclic texture reference: " + value)
            seen.add(value)
            value = model["textures"][value[1:]]
        namespace, path = split_id(value)
        return namespace + ":" + path


def face_uv(face, direction, width, height):
    """Java 与基岩模型的上下表面使用相反的 UV 起点。"""
    u0, v0, u1, v1 = face["uv"]
    if direction in ("up", "down"):
        u0, v0, u1, v1 = u1, v1, u0, v0
    result = {"uv": [u0 * width / 16.0, v0 * height / 16.0],
              "uv_size": [(u1 - u0) * width / 16.0, (v1 - v0) * height / 16.0]}
    if face.get("rotation"):
        result["uv_rotation"] = face["rotation"]
    return result


def geometry(models, model, texture, identifier, size, root_rotation=None):
    """按纹理分组保留全部可见面，避免合并或重绘原仓库贴图。"""
    cubes = []
    for element in model["elements"]:
        faces = {direction: face_uv(face, direction, *size) for direction, face in element["faces"].items()
                 if models.texture(model, face["texture"]) == texture}
        if not faces:
            continue
        start, end = element["from"], element["to"]
        cube = {"origin": [-end[0], start[1], start[2]],
                "size": [end[i] - start[i] for i in range(3)], "uv": faces}
        rotation = element.get("rotation")
        if rotation and rotation.get("rescale"):
            raise ValueError("unsupported rescaled element")
        if rotation and rotation["angle"]:
            pivot = rotation["origin"]
            cube["pivot"] = [-pivot[0], pivot[1], pivot[2]]
            angles = [0, 0, 0]
            axis = "xyz".index(rotation["axis"])
            angles[axis] = rotation["angle"] * (1 if axis == 2 else -1)
            cube["rotation"] = angles
        cubes.append(cube)
    root = {"name": "root", "pivot": [-8, 8, 8], "cubes": cubes}
    if root_rotation:
        root["rotation"] = root_rotation
    return {"description": {"identifier": identifier, "texture_width": size[0], "texture_height": size[1],
                            "visible_bounds_width": 4, "visible_bounds_height": 4,
                            "visible_bounds_offset": [0, 1, 0]}, "bones": [root]}
