# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
"""用原模型几何和原贴图离屏渲染方块物品栏图标。"""

from cStringIO import StringIO
from math import cos, floor, radians, sin

from PIL import Image

FACES = {"north": (5, 4, 0, 1), "south": (6, 7, 3, 2), "east": (7, 5, 1, 3),
         "west": (4, 6, 2, 0), "up": (4, 5, 7, 6), "down": (2, 3, 1, 0)}
SHADE = {"up": 1, "down": 0.5, "north": 0.8, "south": 0.8, "east": 0.65, "west": 0.65}


def rotate(point, angles, pivot):
    x, y, z = [point[i] - pivot[i] for i in range(3)]
    for axis in (2, 1, 0):
        value = angles[axis]
        angle = radians(value)
        a, b = cos(angle), sin(angle)
        if axis == 0:
            y, z = y * a - z * b, y * b + z * a
        elif axis == 1:
            x, z = x * a + z * b, -x * b + z * a
        else:
            x, y = x * a - y * b, x * b + y * a
    return tuple(value + pivot[i] for i, value in enumerate((x, y, z)))


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _triangle(target, depths, vertices, uv, image, shade):
    area = _cross(*vertices)
    if abs(area) < 0.000001:
        return
    pixels, texels = target.load(), image.load()
    left = max(0, int(floor(min(v[0] for v in vertices))))
    right = min(target.width - 1, int(max(v[0] for v in vertices)) + 1)
    top = max(0, int(floor(min(v[1] for v in vertices))))
    bottom = min(target.height - 1, int(max(v[1] for v in vertices)) + 1)
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            point = (x + 0.5, y + 0.5)
            weights = [_cross(point, vertices[1], vertices[2]) / area,
                       _cross(vertices[0], point, vertices[2]) / area]
            weights.append(1 - sum(weights))
            if min(weights) < -0.000001:
                continue
            depth = sum(weights[i] * vertices[i][2] for i in range(3))
            if depth <= depths[y][x]:
                continue
            u, v = [sum(weights[i] * uv[i][axis] for i in range(3)) for axis in range(2)]
            color = texels[min(image.width - 1, max(0, int(floor(u * image.width / 16)))),
                           min(image.height - 1, max(0, int(floor(v * image.height / 16))))]
            if color[3] < 128:
                continue
            pixels[x, y] = tuple(int(channel * shade) for channel in color[:3]) + (255,)
            depths[y][x] = depth


def render_icon(models, model, textures, size=64):
    """按深度采样每个可见面，透明孔洞和细部使用原贴图。"""
    camera = model.get("display", {}).get("gui", {}).get("rotation", [30, 225, 0])
    polygons = []
    for element in model["elements"]:
        start, end = element["from"], element["to"]
        vertices = [(x, y, z) for y in (start[1], end[1]) for z in (start[2], end[2])
                    for x in (start[0], end[0])]
        rotation = element.get("rotation")
        if rotation and rotation["angle"]:
            angles = [0, 0, 0]
            angles["xyz".index(rotation["axis"])] = rotation["angle"]
            vertices = [rotate(v, angles, rotation["origin"]) for v in vertices]
        vertices = [rotate(v, camera, [8, 8, 8]) for v in vertices]
        for direction, face in element["faces"].items():
            points = [vertices[i] for i in FACES[direction]]
            if _cross(*points[:3]) >= 0:
                continue
            u0, v0, u1, v1 = face["uv"]
            uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            step = face.get("rotation", 0) // 90
            if step:
                uv = uv[-step:] + uv[:-step]
            polygons.append((points, uv,
                             textures[models.texture(model, face["texture"])], SHADE[direction]))
    all_points = [point for points, _, _, _ in polygons for point in points]
    bounds = [(min(p[i] for p in all_points), max(p[i] for p in all_points)) for i in range(2)]
    scale = (size - 6) / max(b - a for a, b in bounds)
    center = [(a + b) / 2 for a, b in bounds]
    target = Image.new("RGBA", (size, size))
    depths = [[float("-inf")] * size for _ in range(size)]
    for points, uv, texture, shade in polygons:
        points = [(size / 2 + (p[0] - center[0]) * scale,
                   size / 2 - (p[1] - center[1]) * scale, p[2]) for p in points]
        for indexes in ((0, 1, 2), (0, 2, 3)):
            _triangle(target, depths, [points[i] for i in indexes], [uv[i] for i in indexes], texture, shade)
    output = StringIO()
    target.save(output, format="PNG")
    return output.getvalue()
