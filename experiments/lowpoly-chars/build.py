"""로우폴리 로고 캐릭터 (클로드·제미나이·챗GPT) 만들기 — Blender 스크립트.

운영자 2026-11-18: 회사 로고 모양을 그대로 몸으로, 팔다리 없이 표정(눈·입)으로만 연기,
로우폴리(잘게 쪼갠 다각형, 면이 보이게).

실행:
  & "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe" --background --python experiments/lowpoly-chars/build.py -- [--only claude,gemini] [--quick]
준비물: logos/<이름>.svg (공식 로고 윤곽, 위키미디어 커먼스. 공개 저장소라 커밋하지 않음, README 참고)
결과: out/<이름>.glb, out/preview_*.png, out/q34_<이름>.png

만드는 법: SVG 윤곽 → 면 채우기 → 두께 → 복셀 리메시 → 가장자리에서 멀수록 부풀리기
→ Decimate로 면 줄이기(불규칙한 삼각형) → 평면 셰이딩 → 면마다 색을 살짝 흔들기(정점색 Col = glTF COLOR_0).
"""
import bpy, bmesh, math, sys, os, random
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ONLY = argv[argv.index("--only") + 1].split(",") if "--only" in argv else ["claude", "gemini", "chatgpt"]
QUICK = "--quick" in argv
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)


def hex2rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]  # sRGB → linear


# 캐릭터 설정: 로고 파일, 두께, 부풀림, 얼굴 자리
CHARS = {
    # 클로드: 가운데 몸(얼굴 자리)을 키우고 광선은 그 둘레로 (운영자: 변형 OK, 알아볼 수만 있게, 얼굴은 크게)
    # 통통하게(운영자 레퍼런스 2026-11-18): 두껍고 둥근 단면(power 0.5) + 윤곽을 사방으로 부풀림(dilate) + 큼직한 면(faces)
    "claude": dict(svg="claude.svg", half=0.12, h=0.40, hmin=0.05, power=0.5, dcap=0.46,
                   disc=dict(r=0.46, sides=28), faces=1100, dilate=0.07,
                   face=dict(cx=0.0, cy=0.02, eye_dx=0.16, eye_s=0.10, mouth_dy=-0.16, mouth_w=0.08,
                             blush=(0.28, -0.10, 0.075))),
    "gemini": dict(svg="gemini.svg", half=0.12, h=0.42, hmin=0.04, power=0.5, dcap=None,
                   disc=None, faces=900, dilate=0.06,
                   face=dict(cx=0.0, cy=0.03, eye_dx=0.17, eye_s=0.10, mouth_dy=-0.16, mouth_w=0.08,
                             blush=(0.29, -0.11, 0.07))),
    # 챗GPT: 가운데를 큰 육각 얼굴판으로 덮고 매듭 꽃잎은 바깥에 남김
    "chatgpt": dict(svg="openai.svg", half=0.10, h=0.36, hmin=0.06, power=0.5, dcap=0.40,
                    disc=dict(r=0.47, sides=6, rot=30), faces=1700, dilate=0.025,
                    face=dict(cx=0.0, cy=0.02, eye_dx=0.16, eye_s=0.10, mouth_dy=-0.16, mouth_w=0.08,
                              blush=(0.27, -0.10, 0.07))),
}
# 제미나이 2025 아이콘 색 (위 빨강, 왼쪽 노랑, 아래 초록, 오른쪽·가운데 파랑)
GEM_STOPS = [((0.0, 0.95), "#FC413D"), ((0.45, 0.45), "#969DFF"), ((-0.95, 0.0), "#FBBC04"),
             ((-0.4, -0.35), "#5FC27A"), ((0.0, -0.95), "#00B95C"), ((0.95, 0.0), "#3186FF"),
             ((0.15, 0.0), "#3186FF")]


# ---------- 기본 도구 ----------
def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bm_to_obj(bm, name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def apply_mod(ob, mod):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.remove(mod)
    ob.data = me
    bpy.data.meshes.remove(old)


def remesh(ob, voxel):
    m = ob.modifiers.new("rm", "REMESH")
    m.mode = "VOXEL"
    m.voxel_size = voxel
    apply_mod(ob, m)


def decimate(ob, faces):
    n = len(ob.data.polygons) * 2  # 사각형 → 삼각형 기준
    m = ob.modifiers.new("dec", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = min(1.0, faces / max(n, 1))
    m.use_collapse_triangulate = True
    apply_mod(ob, m)


def shade_flat(ob):
    for p in ob.data.polygons:
        p.use_smooth = False


# ---------- SVG → 몸 ----------
def svg_bmesh(path):
    """SVG를 불러와 채운 2D 면(bmesh, z=0), 크기를 높이·너비 중 큰 쪽 2로 맞춤."""
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.type == "CURVE":
            o.data.resolution_u = 24
            o.data.dimensions = "2D"
            o.data.fill_mode = "BOTH"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for o in new:
        if o.type != "CURVE":
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    for o in new:
        bpy.data.objects.remove(o)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    s = 2.0 / max(max(xs) - min(xs), max(ys) - min(ys))
    for v in bm.verts:
        v.co = Vector(((v.co.x - cx) * s, (v.co.y - cy) * s, 0))
    return bm


def solid_from_flat(bm, half):
    for v in bm.verts:
        v.co.z = -half
    ret = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:] + bm.edges[:])
    for v in [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]:
        v.co.z = half
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def add_prism(bm, r, sides, half, rot=0):
    """얼굴 자리용 원판·육각판 (몸과 합쳐짐)."""
    bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=r, radius2=r, depth=2 * half,
                          matrix=Matrix.Rotation(math.radians(rot), 4, "Z"))


def inflate(ob, half, h, hmin, power, dcap=None):
    """가장자리(옆면)에서 멀수록 두껍게 (말랑하게 부푼 모양). 합쳐진 판까지 한 번에."""
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    side = np.where(np.abs(co[:, 2]) < half * 0.7)[0]
    kd = KDTree(len(side))
    for i, j in enumerate(side):
        kd.insert((co[j, 0], co[j, 1], 0.0), i)
    kd.balance()
    d = np.array([kd.find((x, y, 0.0))[2] for x, y in co[:, :2]])
    cap = dcap or d.max()
    thick = hmin + (h - hmin) * np.clip(d / cap, 0, 1) ** power
    co[:, 2] = co[:, 2] / half * thick
    me.vertices.foreach_set("co", co.ravel())
    me.update()


def facet_colors(ob, color_fn, jitter=0.07, seed=1):
    """면마다 색 하나 (평면 다각형 느낌). color_fn(중심 xyz) → 선형 rgb."""
    me = ob.data
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    rng = random.Random(seed)
    for p in me.polygons:
        c = color_fn(p.center)
        k = 1 + rng.uniform(-jitter, jitter)
        rgba = (c[0] * k, c[1] * k, c[2] * k, 1.0)
        for li in p.loop_indices:
            attr.data[li].color = rgba


def material(name, rgb=None, rough=0.55, vcol=False, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    if vcol:
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def dilate(ob, dist):
    """사방으로 통통하게: 법선 방향으로 밀고 → 다시 리메시(겹친 곳 정리) → 살짝 매끈하게."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    nr = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    me.vertices.foreach_get("normal", nr)
    me.vertices.foreach_set("co", co + nr * dist)
    me.update()
    remesh(ob, 0.012)
    m = ob.modifiers.new("sm", "SMOOTH")
    m.factor, m.iterations = 0.5, 6
    apply_mod(ob, m)


def make_body(key, cfg):
    bm = svg_bmesh(os.path.join(HERE, "logos", cfg["svg"]))
    solid_from_flat(bm, cfg["half"])
    if cfg["disc"]:
        dsc = cfg["disc"]
        add_prism(bm, dsc["r"], dsc["sides"], cfg["half"], dsc.get("rot", 0))
    ob = bm_to_obj(bm, f"{key}_body")
    remesh(ob, 0.010)
    inflate(ob, cfg["half"], cfg["h"], cfg["hmin"], cfg["power"], cfg["dcap"])
    if cfg.get("dilate"):
        dilate(ob, cfg["dilate"])
    decimate(ob, cfg["faces"])
    shade_flat(ob)
    return ob


def body_color(key):
    if key == "claude":
        base = hex2rgb("#D97757")
        return lambda c: base
    if key == "chatgpt":
        base = hex2rgb("#B4B4AF")
        return lambda c: base
    stops = [(Vector((x, y)), hex2rgb(h)) for (x, y), h in GEM_STOPS]

    def grad(c):
        p = Vector((c.x, c.y))
        ws = [1 / ((p - q).length ** 2 + 0.005) ** 2 for q, _ in stops]
        tot = sum(ws)
        return [sum(w * col[i] for w, (_, col) in zip(ws, stops)) / tot for i in range(3)]
    return grad


# ---------- 얼굴 ----------
def lowpoly_ellipsoid(name, sx, sy, sz, seg=10, rings=6):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    ob = bm_to_obj(bm, name)
    shade_flat(ob)
    return ob


def arc_tube(name, pts, rad, ring=6):
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        a = Vector(pts[max(i - 1, 0)])
        b = Vector(pts[min(i + 1, len(pts) - 1)])
        T = (b - a).normalized()
        N = T.cross(Vector((0, 0, 1))).normalized()
        B = N.cross(T).normalized()
        rings.append([bm.verts.new(Vector(p) + rad * (math.cos(2 * math.pi * j / ring) * N + math.sin(2 * math.pi * j / ring) * B)) for j in range(ring)])
    for k in range(len(rings) - 1):
        for j in range(ring):
            jj = (j + 1) % ring
            bm.faces.new((rings[k][j], rings[k + 1][j], rings[k + 1][jj], rings[k][jj]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    ob = bm_to_obj(bm, name)
    shade_flat(ob)
    return ob


def add_face(key, body, root, cx, cy, eye_dx, eye_s, mouth_dy, mouth_w, mats, blush=None):
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)

    def zat(x, y):
        hit = bvh.ray_cast(Vector((x, y, 5)), Vector((0, 0, -1)))
        return hit[0].z if hit[0] else 0.0
    mouth_xy = []
    for k in range(9):
        a = math.radians(200 + 140 * k / 8)
        mouth_xy.append((cx + mouth_w * math.cos(a), cy + mouth_dy + mouth_w * 0.9 + mouth_w * 0.9 * math.sin(a)))
    samples = [(cx - eye_dx, cy), (cx + eye_dx, cy)] + mouth_xy
    if blush:
        samples += [(cx - blush[0], cy + blush[1]), (cx + blush[0], cy + blush[1])]
    z0 = max(zat(x, y) for x, y in samples)  # 얼굴은 한 평면에 (울퉁불퉁한 면 위에 떠 있게)
    for side, sx in (("L", -1), ("R", 1)):
        e = lowpoly_ellipsoid(f"{key}_eye_{side}", eye_s * 0.78, eye_s, eye_s * 0.45)
        e.location = (cx + sx * eye_dx, cy, z0 + eye_s * 0.15)
        e.data.materials.append(mats["eye"])
        e.parent = root
        hl = lowpoly_ellipsoid(f"{key}_eyehl_{side}", eye_s * 0.26, eye_s * 0.26, eye_s * 0.15, seg=6, rings=4)
        hl.location = (eye_s * 0.28, eye_s * 0.38, eye_s * 0.36)
        hl.data.materials.append(mats["hl"])
        hl.parent = e
    if blush:  # 볼터치 (발그레한 표정용, 나중에 켜고 끔)
        for side, sx in (("L", -1), ("R", 1)):
            b = lowpoly_ellipsoid(f"{key}_blush_{side}", blush[2] * 1.25, blush[2] * 0.75, 0.012, seg=8, rings=4)
            b.location = (cx + sx * blush[0], cy + blush[1], z0 + 0.004)
            b.data.materials.append(mats["blush"])
            b.parent = root
    m = arc_tube(f"{key}_mouth_smile", [(x, y, z0 + 0.012) for x, y in mouth_xy], eye_s * 0.2)
    m.data.materials.append(mats["eye"])
    m.parent = root


# ---------- 장면·렌더 ----------
def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            pass
    try:
        sc.eevee.taa_render_samples = 16 if QUICK else 64
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.006, 0.008, 0.016, 1)
    sc.world = w

    # 미리보기용 책상 + 뒤쪽 꼬마전구(흐릿한 빛망울). 캐릭터 glb에는 들어가지 않음.
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    desk = bm_to_obj(bm, "desk")
    desk.data.materials.append(material("desk", hex2rgb("#3B2A20"), rough=0.75))
    bulb = material("bulb", hex2rgb("#FFB35A"), emit=12.0)
    rng = random.Random(3)
    for k in range(26):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=rng.uniform(0.08, 0.16))
        b = bm_to_obj(bm, f"bulb{k}")
        b.location = (rng.uniform(-9, 9), rng.uniform(7, 12), rng.uniform(1.2, 5.5))
        b.data.materials.append(bulb)

    def area(name, loc, energy, color, size):
        d = bpy.data.lights.new(name, "AREA")
        d.energy, d.color, d.size = energy, color, size
        o = link(bpy.data.objects.new(name, d))
        o.location = loc
        o.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return o
    area("key", (-3.0, -4.5, 4.5), 1500, (1.0, 0.86, 0.68), 4)   # 따뜻한 스탠드 빛
    area("fill", (5.0, -3.5, 2.0), 300, (0.7, 0.8, 1.0), 5)       # 모니터 쪽 찬 빛
    area("rim", (1.5, 4.5, 4.0), 900, (1.0, 0.8, 0.6), 3)
    return sc


def camera(sc, loc, target, lens=50, focus=None, fstop=1.4):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    if focus is not None:  # 얕은 심도 (뒤 꼬마전구가 빛망울로)
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(focus) - Vector(loc)).length
        cd.dof.aperture_fstop = fstop
    cam = link(bpy.data.objects.new("cam", cd))
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    return cam


def render(sc, path, w, h):
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    sc = setup_scene()
    mats = {"eye": material("eye", hex2rgb("#141414"), rough=0.25),
            "hl": material("hl", (1, 1, 1), rough=0.2, emit=1.5),
            "blush": material("blush", hex2rgb("#FF6F86"), rough=0.6, emit=0.25)}
    roots = {}
    for i, key in enumerate(ONLY):
        cfg = CHARS[key]
        root = link(bpy.data.objects.new(key, None))
        body = make_body(key, cfg)
        facet_colors(body, body_color(key), seed=11 + i)
        body.data.materials.append(material(f"{key}_mat", vcol=True, rough=0.68))
        body.parent = root
        add_face(key, body, root, mats=mats, **cfg["face"])
        print(key, "faces", len(body.data.polygons))
        # 로고 평면(XY, 앞 +Z)을 세워서 앞이 -Y(카메라 쪽). glTF에서는 앞이 +Z.
        root.rotation_euler = (math.radians(90), 0, 0)
        root.location = ((i - (len(ONLY) - 1) / 2) * 2.7, 0, 1.0 + cfg.get("dilate", 0))
        roots[key] = root
    bpy.context.view_layer.update()

    for key, root in roots.items():
        loc = root.location.copy()
        root.location = (0, 0, 1.08)
        bpy.ops.object.select_all(action="DESELECT")
        root.select_set(True)
        for c in root.children_recursive:
            c.select_set(True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{key}.glb"), export_format="GLB", use_selection=True)
        root.location = loc

    tag = "_".join(ONLY)
    n = len(ONLY)
    camera(sc, (0.9, -4.2 - 2.2 * n, 1.5), (0, 0, 1.0), lens=50, focus=(0, 0, 1.0), fstop=2.8)
    render(sc, os.path.join(OUT, f"preview_{tag}.png"), 1920, 1080)
    home = {k: r.location.copy() for k, r in roots.items()}
    for key, root in roots.items():
        for k, r in roots.items():  # 클로즈업은 한 캐릭터만 가운데에 (조명이 같게)
            r.location = home[k] if k != key else (0, 0, home[k].z)
            r.location.y = 0 if k == key else 50
        bpy.context.view_layer.update()
        x, z = 0.0, root.location.z
        camera(sc, (x + 1.3, -3.3, 1.25), (x, 0, z), lens=50, focus=(x, -0.3, z), fstop=1.2)
        render(sc, os.path.join(OUT, f"q34_{key}.png"), 1080, 1350)


main()
