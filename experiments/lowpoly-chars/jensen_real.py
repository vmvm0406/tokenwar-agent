"""젠슨 황 실물 로우폴리 마무리 (운영자 2026-11-18 "실물을 그대로 로우폴리화", "이 방향으로").

입력: out/jensen_real_lp.glb (lowpoly_from_glb.py가 공개 사진 → TRELLIS 3D → 로우폴리로 만든 흉상, 키 2.2 기준)
하는 일: 재킷을 검정으로 다시 칠함(질감이 회갈색으로 나옴) · 가는 실제 눈(깜박임용) · 하프림 안경(위테만 굵게)
        · 말할 때 입(어두운 입 안, 크기로 벌림) — 실물 얼굴이라 만화 표정 대신 입·눈꺼풀만 움직임(운영자 결정).
얼굴 위치는 probe(정면 직교 렌더)로 잰 값: 코끝 x -0.11, 눈 z 1.60, 입 z 1.25, 얼굴이 살짝 왼쪽으로 돌아감.

실행: & "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe" --background --python experiments/lowpoly-chars/jensen_real.py -- [--quick]
결과: out/jensen_real_head.glb, out/jensen_real_front.png, out/jensen_real_q34.png, out/jensen_real_talk.png
"""
import bpy, bmesh, os, sys, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B  # noqa: E402

FACE_X = -0.10        # 얼굴 가운데 (코끝 x -0.109)
EYE_Z, EYE_DX = 1.595, 0.165
MOUTH_Z = 1.255
JACKET, TEE = "#17171A", "#26262A"
GLASS_RX, GLASS_RZ, GLASS_DZ, GLASS_OUT = 0.115, 0.07, -0.008, 0.0   # 안경알 반너비·반높이·눈 대비 높이·바깥 이동 (jensen_simple이 사진 비율로 바꿈)


def load():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(B.OUT, "jensen_real_lp.glb"))
    ob = [o for o in bpy.data.objects if o not in before and o.type == "MESH"][0]   # 책상·전구 말고 불러온 흉상
    ob.name = "jensen_real_body"
    return ob


def recolor(ob):
    """목 아래 = 검정 가죽 재킷, 가슴 가운데 V = 짙은 회색 티셔츠. 면 색 흔들기는 build.facet_colors와 같게."""
    import random
    rng = random.Random(7)
    attr = ob.data.color_attributes[0]   # glb에서 불러오면 이름이 Color로 바뀜
    jc, tc = B.hex2rgb(JACKET), B.hex2rgb(TEE)
    for p in ob.data.polygons:
        c = ob.matrix_world @ p.center
        dx = abs(c.x - FACE_X)
        if c.z > 1.13 or (c.z > 1.0 and dx < 0.24):   # 턱·목 앞은 피부 그대로
            continue
        col = tc if (c.y < -0.25 and c.z > 0.55 and dx < 0.06 + (c.z - 0.55) * 0.22) else jc
        k = 1 + rng.uniform(-0.12, 0.12)
        for li in p.loop_indices:
            attr.data[li].color = (col[0] * k, col[1] * k, col[2] * k, 1)


def front_y(bvh, x, z):
    hit = bvh.ray_cast(Vector((x, -3, z)), Vector((0, 1, 0)))
    return hit[0].y if hit[0] else -0.45


def mat(name, hexc, rough=0.4, emit=0.0):
    return B.material(name, B.hex2rgb(hexc), rough=rough, emit=emit)


HEAD_SCALE = 1.35                  # 캐릭터화: 머리를 몸보다 크게 (운영자 2026-11-18 "실제 비율 말고 조금 캐릭터화")
PIVOT = Vector((FACE_X, 0.0, 1.08))  # 목 아래 (여기 위로 머리가 커짐)


def symmetrize(body, side):
    """좌우 대칭 (운영자 2026-11-18 "입이 삐뚤어진 느낌"): 코 x를 가운데로, 한쪽 반을 거울로 복사. side = X(+x 반 유지) | -X(-x 반 유지)."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    for v in bm.verts:
        v.co.x -= FACE_X
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction=side, dist=0.002)
    for v in bm.verts:
        v.co.x += FACE_X
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    for p in body.data.polygons:
        p.use_smooth = False


def level_mouth(body, radius_x=0.17, radius_z=0.09):
    """입꼬리만 바로잡기 (운영자 2026-11-18 "좌우를 맞추는 게 아니라 입꼬리만 다시"): 입술 사이 어두운 선의 기울기를 재서
    입 주변 정점만 반대로 기울임(가장자리로 갈수록 약하게). 얼굴 나머지는 실물 그대로."""
    import numpy as np
    me = body.data
    attr = me.color_attributes[0]
    pts = []
    for p in me.polygons:
        c = p.center
        if abs(c.x - FACE_X) < 0.13 and abs(c.z - MOUTH_Z) < 0.05 and c.y < -0.3:
            col = attr.data[p.loop_indices[0]].color
            pts.append((c.x, c.z, 0.2126 * col[0] + 0.7152 * col[1] + 0.0722 * col[2]))
    if len(pts) < 6:
        return 0.0
    a = np.array(pts)
    dark = a[a[:, 2] <= np.percentile(a[:, 2], 25)]       # 입술 사이 어두운 면
    slope = np.polyfit(dark[:, 0], dark[:, 1], 1)[0]
    for v in me.vertices:
        dx, dz = v.co.x - FACE_X, v.co.z - MOUTH_Z
        if v.co.y < -0.2 and abs(dx) < radius_x and abs(dz) < radius_z:
            w = (1 - (dx / radius_x) ** 2) * (1 - (dz / radius_z) ** 2)
            v.co.z -= slope * dx * max(0.0, w) ** 0.5
    me.update()
    print("mouth slope", round(float(slope), 3))
    return slope


def flatten_mouth(body, rx=0.18, rz=0.09, iters=60):
    """입 주변 흔적 지우기 (운영자 2026-11-18): 튀어나온 입술 굴곡을 이웃 평균으로 펴서 매끈한 피부 면으로. 앞뒤(y)만 움직임."""
    bm = bmesh.new()
    bm.from_mesh(body.data)
    region = [v for v in bm.verts if v.co.y < -0.25 and abs(v.co.x - FACE_X) < rx and abs(v.co.z - MOUTH_Z) < rz]
    inside = set(region)
    for _ in range(iters):
        new = {}
        for v in region:
            nb = [e.other_vert(v) for e in v.link_edges]
            if nb:
                new[v] = sum(n.co.y for n in nb) / len(nb)
        for v, y in new.items():
            w = (1 - ((v.co.x - FACE_X) / rx) ** 2) * (1 - ((v.co.z - MOUTH_Z) / rz) ** 2)
            v.co.y += (y - v.co.y) * max(0.0, min(1.0, w * 1.6))
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    for p in body.data.polygons:
        p.use_smooth = False


def crescent(name, w, depth, curve, t):
    """웃는 초승달 입: 위는 얕은 호, 아래는 깊은 호, 양 끝에서 만남 (x=가로, z=세로, y=두께)."""
    n = 10
    top = [(w * (-1 + 2 * k / n), curve * (-1 + 2 * k / n) ** 2) for k in range(n + 1)]
    bot = [(w * (1 - 2 * k / n), curve * (1 - 2 * k / n) ** 2 - depth * (1 - (1 - 2 * k / n) ** 2)) for k in range(1, n)]
    pts = top + bot
    bm = bmesh.new()
    fr = [bm.verts.new((x, -t / 2, z)) for x, z in pts]
    bk = [bm.verts.new((x, t / 2, z)) for x, z in pts]
    bm.faces.new(fr)
    bm.faces.new(list(reversed(bk)))
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        bm.faces.new((fr[j], fr[i], bk[i], bk[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = B.bm_to_obj(bm, name)
    B.shade_flat(ob)
    return ob


def paint_lips(body, w=0.1, up=0.028, lo=0.036):
    """로우폴리 면은 그대로, 그 면들에 원래 비율·원래 색의 빨간 입술을 좌우 대칭으로 칠함 (운영자 2026-11-18).
    입 폭 ≈ 0.16(사진 기준), 윗입술 얇게·아랫입술 도톰하게, 가운데 입술선은 진하게."""
    import random
    # 입 자리 면만 잘게 나눔 (큰 삼각형이면 입 모양이 세모로 쏠림). 나머지 로우폴리는 그대로.
    bm = bmesh.new()
    bm.from_mesh(body.data)
    reg = [f for f in bm.faces if f.normal.y < -0.15 and abs(f.calc_center_median().x - FACE_X) < w * 1.4
           and abs(f.calc_center_median().z - MOUTH_Z) < 0.07]
    edges = list({e for f in reg for e in f.edges})
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=2, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(body.data)
    bm.free()
    for p in body.data.polygons:
        p.use_smooth = False
    rng = random.Random(9)
    attr = body.data.color_attributes[0]
    # 자연스러운 입술색 (운영자 2026-11-18 "색은 자연스럽게"): 옆 피부색에서 붉은 기만 살짝 더한 톤.
    import numpy as np
    ring = [tuple(attr.data[p.loop_indices[0]].color)[:3] for p in body.data.polygons
            if p.normal.y < -0.15 and w * 1.1 < abs(p.center.x - FACE_X) < w * 1.9 and abs(p.center.z - MOUTH_Z) < 0.06]
    skin = np.median(np.array(ring), axis=0) if ring else np.array(B.hex2rgb("#D7A07A"))
    tint = lambda r, g, b: tuple(float(v) for v in skin * np.array((r, g, b)))
    upper, lower, line = tint(0.88, 0.5, 0.5), tint(0.98, 0.58, 0.57), tint(0.5, 0.27, 0.27)
    for p in body.data.polygons:
        c = p.center
        if p.normal.y > -0.15:   # 앞을 향한 면만 (얼굴이 살짝 돌아가 있어 y 높이로 거르면 한쪽이 빠짐)
            continue
        dx, dz = abs(c.x - FACE_X) / w, c.z - MOUTH_Z
        if dx >= 1:
            continue
        span = 1 - dx * dx
        col = None
        if abs(dz) < 0.0055 + 0.004 * span:
            col = line
        elif 0 < dz < up * span * (1 - 0.35 * math.exp(-(dx / 0.18) ** 2)):   # 윗입술 (가운데 살짝 오목: 큐피드 활)
            col = upper
        elif -lo * span ** 0.7 < dz < 0:
            col = lower
        if col:
            edge = max(0.0, (dx - 0.75) / 0.25)            # 입꼬리 쪽은 피부색으로 서서히
            col = [col[i] * (1 - edge * 0.6) + skin[i] * edge * 0.6 for i in range(3)]
            k = 1 + rng.uniform(-0.04, 0.04)
            for li in p.loop_indices:
                attr.data[li].color = (col[0] * k, col[1] * k, col[2] * k, 1)


def clean_mouth(body):
    """입 주변 면을 옆 피부색으로 다시 칠함 (한쪽만 붉던 입술 색이 삐뚤어 보이게 함). 입은 캐릭터 입선으로 새로 그림."""
    import numpy as np, random
    me = body.data
    attr = me.color_attributes[0]
    ring, inner = [], []
    for p in me.polygons:
        c = p.center
        dx, dz = abs(c.x - FACE_X), c.z - MOUTH_Z
        if c.y > -0.3:
            continue
        if dx < 0.16 and abs(dz) < 0.07:
            inner.append(p)
        elif 0.16 <= dx < 0.25 and abs(dz) < 0.09:
            ring.append(tuple(attr.data[p.loop_indices[0]].color)[:3])
    if not ring:
        return
    skin = np.median(np.array(ring), axis=0)
    rng = random.Random(5)
    for p in inner:
        k = 1 + rng.uniform(-0.05, 0.05)
        for li in p.loop_indices:
            attr.data[li].color = (skin[0] * k, skin[1] * k, skin[2] * k, 1)


def stylize(body, face):
    """얼굴형·머리·코·입 모양은 실물 그대로 두고, 머리(+얼굴 부품)를 목 기준으로 키움. 목 1.00~1.13은 부드럽게 이어짐."""
    me = body.data
    for v in me.vertices:
        t = min(1.0, max(0.0, (v.co.z - 1.00) / 0.13))
        s = 1 + (HEAD_SCALE - 1) * (t * t * (3 - 2 * t))
        v.co = PIVOT + (v.co - PIVOT) * s
    me.update()
    from mathutils import Matrix
    S = Matrix.Translation(PIVOT) @ Matrix.Scale(HEAD_SCALE, 4) @ Matrix.Translation(-PIVOT)
    bpy.context.view_layer.update()
    for o in face.children:
        o.matrix_world = S @ o.matrix_world


def box(name, w, d, h, bev):
    """모서리를 깎은 상자 (x=너비, y=두께, z=높이)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w
        v.co.y *= d
        v.co.z *= h
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bev, segments=1, affect="EDGES")
    ob = B.bm_to_obj(bm, name)
    B.shade_flat(ob)
    return ob


def add_face_parts(body):
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)
    face = B.link(bpy.data.objects.new("jensen_real_face", None))
    eye_m, lid_m = mat("jr_eye", "#1A1310", 0.2), mat("jr_hl", "#FFFFFF", 0.2, emit=1.0)
    for sd, sx in (("L", -1), ("R", 1)):
        x = FACE_X + sx * EYE_DX
        y = front_y(bvh, x, EYE_Z) - 0.008
        # 네모 눈 (운영자 2026-11-18: 실제 눈은 이상함, "네모네모로 캐릭터다 싶게"). 모서리만 살짝 깎은 세로 직사각형
        e = box(f"jensen_real_eye_{sd}", 0.085, 0.02, 0.045, 0.01)   # 가로로 긴 네모 (운영자 2026-11-18)
        e.location = (x, y - 0.004, EYE_Z)
        e.data.materials.append(eye_m)
        e.parent = face
        hl = box(f"jensen_real_eyehl_{sd}", 0.016, 0.008, 0.016, 0.002)
        hl.location = (x + 0.022, y - 0.016, EYE_Z + 0.008)
        hl.data.materials.append(lid_m)
        hl.parent = face
    # 말할 때 입: 어두운 입 안 (평소엔 납작 → three.js가 높이를 키워 벌림)
    my = front_y(bvh, FACE_X, MOUTH_Z) - 0.006
    m = B.lowpoly_ellipsoid("jensen_real_mouth_open", 0.07, 0.03, 0.02, seg=12, rings=4)
    m.rotation_euler = (math.radians(90), 0, 0)
    m.location = (FACE_X, my, MOUTH_Z - 0.01)
    m.data.materials.append(mat("jr_mouth", "#3A0F14", 0.6))
    m.parent = face
    m.hide_render = True   # 평소엔 숨김, 말할 때만 (three.js가 켜고 높이로 벌림)
    add_glasses(bvh, face)
    return face


def add_glasses(bvh, face):
    """하프림(브로우라인): 위테만 굵은 검정, 아래는 가는 은색. 실제 사진의 사각형에 가까운 렌즈."""
    black, wire = mat("jr_frame", "#151517", 0.3), mat("jr_wire", "#AEB3BA", 0.25)
    rx, rz = GLASS_RX, GLASS_RZ
    zc = EYE_Z + GLASS_DZ

    def tube(name, pts, r, m):
        o = B.arc_tube(name, pts, r, ring=5)
        o.data.materials.append(m)
        o.parent = face
        return o

    def rim(xc, y, t):
        c, s = math.cos(math.radians(t)), math.sin(math.radians(t))
        return (xc + rx * math.copysign(abs(c) ** 0.45, c), y, zc + rz * math.copysign(abs(s) ** 0.6, s))
    inner = []
    for sd, sx in (("L", -1), ("R", 1)):
        xc = FACE_X + sx * (EYE_DX + GLASS_OUT)
        y = front_y(bvh, xc, EYE_Z) - 0.045
        tube(f"jensen_real_glasses_top_{sd}", [rim(xc, y, t) for t in range(-12, 193, 12)], 0.016, black)
        tube(f"jensen_real_glasses_wire_{sd}", [rim(xc, y, t) for t in range(192, 349, 12)], 0.004, wire)
        outer = (xc + sx * rx, y, zc + 0.02)
        ear_x = FACE_X + sx * 0.44
        tube(f"jensen_real_glasses_arm_{sd}", [outer, (ear_x * 0.95, y + 0.25, zc + 0.03), (ear_x, 0.05, zc + 0.0)], 0.009, black)
        inner.append((xc - sx * rx, y, zc + 0.03))
    tube("jensen_real_glasses_bridge", [inner[0], (FACE_X, inner[0][1] - 0.005, zc + 0.045), inner[1]], 0.008, black)


def main():
    quick = "--quick" in sys.argv
    sc = B.setup_scene()
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.data.use_shadow = False
            if o.name == "key":
                o.data.energy = 900   # 실물 피부가 날아가지 않게
    body = load()
    side = sys.argv[sys.argv.index("--sym") + 1] if "--sym" in sys.argv else None
    if side:   # 예전 시험용 (운영자는 대칭 말고 입꼬리만 고치길 원함)
        symmetrize(body, side)
    else:
        level_mouth(body)
        clean_mouth(body)
        paint_lips(body)
    recolor(body)
    for m in body.data.materials:  # 넓은 조명이 검은 재킷에 하얗게 반사돼 회색으로 보이던 것 줄이기
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Roughness"].default_value = 0.85
            if "Specular IOR Level" in bsdf.inputs:
                bsdf.inputs["Specular IOR Level"].default_value = 0.2
    face = add_face_parts(body)
    stylize(body, face)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    for c in face.children_recursive:
        c.select_set(True)
    face.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(B.OUT, "jensen_real_head.glb"), export_format="GLB", use_selection=True, export_vertex_color="ACTIVE")
    fz = 1.72   # 커진 머리의 얼굴 높이쯤
    B.camera(sc, (0.0, -4.4, fz + 0.1), (FACE_X, 0, fz - 0.1), lens=50, focus=(FACE_X, -0.6, fz), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, "jensen_real_front.png" if not side else f"jensen_real_front_{side}.png"), 1080, 1350)
    B.camera(sc, (2.4, -3.7, fz + 0.2), (FACE_X, 0, fz - 0.15), lens=50, focus=(FACE_X, -0.5, fz), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, "jensen_real_q34.png"), 1080, 1350)
    bpy.data.objects["jensen_real_mouth_open"].hide_render = False   # 말하는 모습 시험
    B.camera(sc, (0.0, -4.4, fz + 0.1), (FACE_X, 0, fz - 0.1), lens=50, focus=(FACE_X, -0.6, fz), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, "jensen_real_talk.png"), 1080, 1350)


if __name__ == "__main__":
    main()
