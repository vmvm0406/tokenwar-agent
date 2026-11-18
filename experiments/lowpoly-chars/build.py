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
    # 2026-11-18 운영자: 광선이 다리처럼 보여 이상 → 로고 모양은 그대로 두고 광선만 가운데 쪽으로 줄임(ray_k).
    # (별 모양 star= 시안은 "클로드 느낌이 사라졌다"로 되돌림)
    # 2026-11-18 운영자 레퍼런스(통통한 구름 덩어리 + 짧은 발 + 세로 막대 눈, 입 없음): "이런 느낌".
    # 로고 광선을 아주 짧은 혹으로(ray_k) + 크게 부풀려(dilate) 한 덩어리로, 두껍게(h), 아래에 짧은 발 2개,
    # 위 밝고 아래 짙은 색(grad). 얼굴은 눈만 (eyes_only) — 표정은 눈·눈썹·볼터치·땀으로만.
    # 운영자 2026-11-18: 구름 덩어리 방향 OK, 혹 7개 시안은 "꽃 같다" → 로고 광선을 짧은 혹으로(구름),
    # 레퍼런스처럼 옆으로 조금 넓고(xscale) 혹은 더 매끈하게, 아래는 살짝 평평하게(bottom_flat) 발이 보이게
    "claude": dict(svg="claude.svg", half=0.12, h=0.62, hmin=0.12, power=0.45, dcap=0.5,
                   ray_k=dict(r0=0.36, k=0.42), xscale=1.1, bottom_flat=-0.62,
                   smooth_it=18, jitter=0.04,
                   disc=dict(r=0.5, sides=28), faces=1600, dilate=0.11,
                   feet=dict(dx=0.26, s=(0.18, 0.12, 0.2)), grad=("#F2A47C", "#C9552F"),
                   face=dict(cx=0.0, cy=0.06, eye_dx=0.2, eye_s=0.21, mouth_dy=-0.16, mouth_w=0.08,
                             blush=(0.33, -0.10, 0.08), eyes_only=True)),
    # 제미나이: 네 꼭짓점을 조금 짧고 둥글게 (별 모양은 그대로 알아보게)
    "gemini": dict(svg="gemini.svg", half=0.12, h=0.58, hmin=0.08, power=0.45, dcap=None,
                   ray_k=dict(r0=0.3, k=0.72), smooth_it=6, jitter=0.04,
                   disc=None, faces=1600, dilate=0.09,
                   feet=dict(dx=0.2, s=(0.15, 0.11, 0.18)), grad=(1.12, 0.82),
                   face=dict(cx=0.0, cy=0.05, eye_dx=0.17, eye_s=0.17, mouth_dy=-0.16, mouth_w=0.08,
                             blush=(0.28, -0.10, 0.07), eyes_only=True)),
    # 챗GPT: 가운데 육각 얼굴판 + 매듭 꽃잎, 조금 더 통통하게
    "chatgpt": dict(svg="openai.svg", half=0.10, h=0.5, hmin=0.1, power=0.45, dcap=0.40,
                    ray_k=dict(r0=0.5, k=0.85), smooth_it=5, jitter=0.04,
                    disc=dict(r=0.5, sides=6, rot=30), faces=2400, dilate=0.05,
                    feet=dict(dx=0.22, s=(0.16, 0.11, 0.19)), grad=("#E4E4DF", "#9A9A95"),
                    face=dict(cx=0.0, cy=0.03, eye_dx=0.17, eye_s=0.17, mouth_dy=-0.16, mouth_w=0.08,
                              blush=(0.28, -0.10, 0.07), eyes_only=True)),
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


def facet_colors(ob, color_fn, jitter=0.11, seed=1):   # 면마다 명암 차이 크게 → 다각형이 보이게 (운영자 2026-11-18)
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


def dilate(ob, dist, iters=3):
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
    m.factor, m.iterations = 0.5, iters  # 덜 매끈하게 → 각이 보이게 (캐릭터별 smooth_it)
    apply_mod(ob, m)


def star_bmesh(st):
    """짧고 통통한 별 (클로드 로고 광선을 줄이고 짧게, 운영자 2026-11-18 "다리가 달린 것 같아 이상").
    st: n 광선 수, r_in 골 반지름, lens 광선 길이들(반복), w_base/w_tip 광선 폭, rot 회전(도),
    offs 광선마다 각도 어긋남(도, 로고처럼 살짝 들쭉날쭉, 운영자 2026-11-18)."""
    bm = bmesh.new()
    n, r_in = st["n"], st["r_in"]
    lens, wb, wt = st["lens"], st["w_base"], st["w_tip"]
    offs = st.get("offs", (0,))
    A = [math.radians(st.get("rot", 0) + offs[i % len(offs)]) + 2 * math.pi * i / n for i in range(n)]
    pts = []
    for i in range(n):
        a = A[i]
        L = lens[i % len(lens)]
        d = Vector((math.cos(a), math.sin(a)))
        p = Vector((-d.y, d.x))
        prev = A[i - 1] - (2 * math.pi if i == 0 else 0)
        nxt = A[(i + 1) % n] + (2 * math.pi if i == n - 1 else 0)
        lm, rm = (prev + a) / 2, (a + nxt) / 2                   # 이웃 광선과의 가운데 골
        bw = math.asin(min(0.9, wb / 2 / r_in))                  # 광선 뿌리 반폭(각도)
        for k in range(3):                                       # 왼쪽 골: 가운데 → 뿌리 앞까지 둥근 호
            t = lm + (a - bw - lm) * k / 3
            pts.append(Vector((math.cos(t), math.sin(t))) * r_in)
        base = d * (r_in + 0.02)
        tip = d * L
        pts.append(base - p * wb / 2)
        pts.append(tip - p * wt / 2)
        for k in range(1, 4):                                    # 끝은 둥글게
            t = math.pi * k / 4
            pts.append(tip + d * (wt / 2) * math.sin(t) - p * (wt / 2) * math.cos(t))
        pts.append(tip + p * wt / 2)
        pts.append(base + p * wb / 2)
        for k in range(1, 3):                                    # 오른쪽 골: 뿌리 뒤 → 가운데 앞 (가운데는 다음 광선이 넣음)
            t = a + bw + (rm - a - bw) * k / 3
            pts.append(Vector((math.cos(t), math.sin(t))) * r_in)
    vs = [bm.verts.new((q.x, q.y, 0.0)) for q in pts]
    bm.faces.new(vs)
    return bm


def make_body(key, cfg):
    bm = star_bmesh(cfg["star"]) if cfg.get("star") else svg_bmesh(os.path.join(HERE, "logos", cfg["svg"]))
    if cfg.get("ray_k"):                       # 로고 광선을 가운데 쪽으로 짧게 (모양·들쭉날쭉함은 그대로)
        r0, k = cfg["ray_k"]["r0"], cfg["ray_k"]["k"]
        for v in bm.verts:
            r = v.co.length
            if r > r0:
                v.co *= (r0 + (r - r0) * k) / r
    for v in bm.verts:                         # 옆으로 넓게 / 아래 평평하게 (레퍼런스 덩어리 비율)
        v.co.x *= cfg.get("xscale", 1.0)
        if cfg.get("bottom_flat") is not None and v.co.y < cfg["bottom_flat"]:
            v.co.y = cfg["bottom_flat"] + (v.co.y - cfg["bottom_flat"]) * 0.35
    solid_from_flat(bm, cfg["half"])
    if cfg["disc"]:
        dsc = cfg["disc"]
        add_prism(bm, dsc["r"], dsc["sides"], cfg["half"], dsc.get("rot", 0))
    ob = bm_to_obj(bm, f"{key}_body")
    remesh(ob, 0.010)
    inflate(ob, cfg["half"], cfg["h"], cfg["hmin"], cfg["power"], cfg["dcap"])
    if cfg.get("dilate"):
        dilate(ob, cfg["dilate"], cfg.get("smooth_it", 3))
    decimate(ob, cfg["faces"])
    shade_flat(ob)
    return ob


def body_color(key):
    g = CHARS[key].get("grad")
    if g and isinstance(g[0], str):            # 위 밝은 색 → 아래 짙은 색 (레퍼런스처럼 높이에 따라 층)
        top, bot = hex2rgb(g[0]), hex2rgb(g[1])

        def vert(c):
            t = max(0.0, min(1.0, (c.y + 0.9) / 1.8))
            return [bot[i] + (top[i] - bot[i]) * t for i in range(3)]
        return vert
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
        col = [sum(w * col[i] for w, (_, col) in zip(ws, stops)) / tot for i in range(3)]
        if g:                                  # 제미나이: 색은 그대로, 위 밝게·아래 어둡게만
            t = max(0.0, min(1.0, (c.y + 0.9) / 1.8))
            col = [v * (g[1] + (g[0] - g[1]) * t) for v in col]
        return col
    return grad


def add_feet(key, body, root, cfg, mat):
    """짧고 통통한 발 2개 (레퍼런스처럼 몸 아래 살짝 보이게). 로고 평면 좌표: 아래 = -Y, 앞 = +Z."""
    ys = [v.co.y for v in body.data.vertices]
    ymin = min(ys)
    f = cfg["feet"]
    feet = []
    for sx in (-1, 1):
        o = lowpoly_ellipsoid(f"{key}_foot_{'L' if sx < 0 else 'R'}", *f["s"], seg=8, rings=6)
        loc = Vector((sx * f["dx"], ymin + f["s"][1] * 0.35, 0.02))
        col = body_color(key)
        facet_colors(o, lambda c: [v * 0.9 for v in col(c + loc)], jitter=0.04, seed=5)   # 몸 아래쪽 색 그대로, 살짝 짙게
        o.data.materials.append(mat)
        o.parent = root
        o.location = loc
        feet.append(o)
    return ymin - f["s"][1] * 0.65           # 발바닥 높이


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


def d_mouth(name, w, h, t, n=10):
    """위가 평평하고 아래가 둥근 D자 입 (활짝 웃음·말하기). 원점 = 윗변 가운데."""
    pts = [(-w, 0)] + [(w * math.cos(math.pi + math.pi * k / n), h * math.sin(math.pi + math.pi * k / n)) for k in range(1, n)] + [(w, 0)]
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, -t / 2)) for x, y in pts]
    top = [bm.verts.new((x, y, t / 2)) for x, y in pts]
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    ob = bm_to_obj(bm, name)
    shade_flat(ob)
    return ob


def bar(name, w, h, d):
    """세로 막대 눈 (레퍼런스: 까만 직사각형)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * w, v.co.y * h, v.co.z * d))
    ob = bm_to_obj(bm, name)
    shade_flat(ob)
    return ob


def add_bar_eyes(put, key, eye_dx, s):
    """눈만 있는 얼굴 (운영자 2026-11-18 "눈만 띄우자, 표정은 눈으로만").
    bar 평소 / barwide 놀람(크게) / barlow 슬픔(짧게·아래) / squint >< 당황 / line 졸림(가로줄). ^^(happy)는 기존 eye_happy."""
    for side, sx in (("L", -1), ("R", 1)):
        ex = sx * eye_dx
        put(bar(f"{key}_eye_bar_{side}", s * 0.42, s * 1.45, s * 0.3), "eye", (ex, 0, s * 0.1))
        put(bar(f"{key}_eye_barwide_{side}", s * 0.55, s * 1.85, s * 0.3), "eye", (ex, s * 0.1, s * 0.1))
        put(bar(f"{key}_eye_barlow_{side}", s * 0.42, s * 0.85, s * 0.3), "eye", (ex, -s * 0.35, s * 0.1))
        put(bar(f"{key}_eye_line_{side}", s * 1.0, s * 0.26, s * 0.3), "eye", (ex, -s * 0.2, s * 0.1))
        k = -sx                                   # > <: 꼭짓점이 코 쪽
        pts = [(ex - k * s * 0.4, s * 0.5, 0.02), (ex + k * s * 0.4, 0, 0.02), (ex - k * s * 0.4, -s * 0.5, 0.02)]
        put(arc_tube(f"{key}_eye_squint_{side}", pts, s * 0.17), "eye")


def add_face(key, body, root, cx, cy, eye_dx, eye_s, mouth_dy, mouth_w, mats, blush=None,
             eye_aspect=1.0, brows=False, grin=False, eyes_only=False):
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)

    def zat(x, y):
        hit = bvh.ray_cast(Vector((x, y, 5)), Vector((0, 0, -1)))
        return hit[0].z if hit[0] else 0.0
    mouth_xy = []
    for k in range(9):
        a = math.radians(200 + 140 * k / 8)
        mouth_xy.append((cx + mouth_w * math.cos(a), cy + mouth_dy + mouth_w * 0.9 + mouth_w * 0.9 * math.sin(a)))
    samples = [(cx - eye_dx, cy), (cx + eye_dx, cy)] + ([] if eyes_only else mouth_xy)
    if blush:
        samples += [(cx - blush[0], cy + blush[1]), (cx + blush[0], cy + blush[1])]
    z0 = max(zat(x, y) for x, y in samples)  # 얼굴은 한 평면에 (울퉁불퉁한 면 위에 떠 있게)

    # 얼굴 묶음: 부품 이름 = <캐릭터>_<부품>_<변형>[_L|_R]. three.js가 표정마다 켜고 끈다 (EMOTIONS).
    face = link(bpy.data.objects.new(f"{key}_face", None))
    face.parent = root
    face.location = (cx, cy, z0)
    s = eye_s

    def put(ob, mat, loc=(0, 0, 0)):
        ob.data.materials.append(mats[mat])
        ob.parent = face
        ob.location = loc
        return ob

    def arc(name, ox, oy, r, a0, a1, rad, sy=1.0, n=9):
        pts = [(ox + r * math.cos(math.radians(a0 + (a1 - a0) * k / (n - 1))),
                oy + r * sy * math.sin(math.radians(a0 + (a1 - a0) * k / (n - 1))), 0.02) for k in range(n)]
        return arc_tube(name, pts, rad)

    for side, sx in (("L", -1), ("R", 1)):
        ex = sx * eye_dx
        # 눈: 기본 / 크게(놀람) / ^^(기쁨) / 감음(졸림·민망)
        for var, k in (() if eyes_only else (("open", 1.0), ("wide", 1.3))):
            e = put(lowpoly_ellipsoid(f"{key}_eye_{var}_{side}", s * 0.78 * k, s * k * eye_aspect, s * 0.45 * k), "eye", (ex, 0, s * 0.15))
            hl = lowpoly_ellipsoid(f"{key}_eyehl_{var}_{side}", s * 0.26 * k, s * 0.26 * k, s * 0.15, seg=6, rings=4)
            hl.data.materials.append(mats["hl"])
            hl.parent = e
            hl.location = (s * 0.28 * k, s * 0.38 * k, s * 0.36 * k)
        put(arc(f"{key}_eye_happy_{side}", ex, -s * 0.35, s * 0.75, 20, 160, s * 0.2), "eye")
        if not eyes_only:
            put(arc(f"{key}_eye_closed_{side}", ex, s * 0.45, s * 0.75, 205, 335, s * 0.18, sy=0.7), "eye")
        # 눈썹: 화남(안쪽이 내려감) / 슬픔(바깥이 내려감)
        for var, tilt in (("angry", -1), ("sad", 1)):
            y0 = s * 1.45
            pts = [(ex - sx * s * 0.6, y0 + tilt * s * 0.25, 0.02), (ex, y0, 0.02), (ex + sx * s * 0.6, y0 - tilt * s * 0.25, 0.02)]
            put(arc_tube(f"{key}_brow_{var}_{side}", pts, s * 0.16), "eye")
        if brows:  # 평소 눈썹 (사람 캐릭터)
            pts = [(ex - sx * s * 0.75, s * 1.15, 0.02), (ex - sx * s * 0.1, s * 1.42, 0.02), (ex + sx * s * 0.7, s * 1.3, 0.02)]
            put(arc_tube(f"{key}_brow_neutral_{side}", pts, s * 0.2), "brow" if "brow" in mats else "eye")
        if blush:  # 볼터치
            put(lowpoly_ellipsoid(f"{key}_blush_{side}", blush[2] * 1.25, blush[2] * 0.75, 0.012, seg=8, rings=4),
                "blush", (sx * blush[0], blush[1], 0.004))

    if eyes_only:
        add_bar_eyes(put, key, eye_dx, s)
        sw = put(lowpoly_ellipsoid(f"{key}_sweat", s * 0.45, s * 0.7, s * 0.3, seg=8, rings=6), "sweat",
                 (eye_dx + s * 1.4, s * 1.3, s * 0.1))
        sw.rotation_euler = (0, 0, math.radians(-20))
        return
    # 입: 웃음 / 시무룩 / 일자 / 벌림(아) / 오 / 물결(당황)
    mw, my = mouth_w, mouth_dy
    put(arc_tube(f"{key}_mouth_smile", [(x - cx, y - cy, 0.012) for x, y in mouth_xy], s * 0.2), "eye")
    put(arc(f"{key}_mouth_frown", 0, my - mw * 0.9, mw * 0.9, 25, 155, s * 0.2), "eye")
    put(arc_tube(f"{key}_mouth_flat", [(-mw * 0.7, my, 0.02), (0, my, 0.02), (mw * 0.7, my, 0.02)], s * 0.18), "eye")
    put(d_mouth(f"{key}_mouth_open", mw * 1.1, mw * 0.85, s * 0.18), "inner", (0, my + mw * 0.45, 0.02))
    put(lowpoly_ellipsoid(f"{key}_mouth_o", mw * 0.5, mw * 0.62, s * 0.25, seg=10, rings=6), "inner", (0, my - mw * 0.1, 0.01))
    wav = [(-mw + 2 * mw * k / 8, my + (s * 0.18 if k % 2 else -s * 0.18), 0.02) for k in range(9)]
    put(arc_tube(f"{key}_mouth_wavy", wav, s * 0.16), "eye")
    if grin:  # 이가 보이는 큰 웃음 (젠슨 황 트레이드마크)
        g = put(d_mouth(f"{key}_mouth_grin", mw * 1.4, mw * 0.8, s * 0.18), "inner", (0, my + mw * 0.55, 0.02))
        t = lowpoly_ellipsoid(f"{key}_teeth", mw * 1.2, mw * 0.2, s * 0.1, seg=10, rings=4)
        t.data.materials.append(mats.get("teeth", mats["hl"]))
        t.parent = g
        t.location = (0, -mw * 0.17, s * 0.08)
    # 땀방울 (당황) — 이마 오른쪽 위
    sw = put(lowpoly_ellipsoid(f"{key}_sweat", s * 0.45, s * 0.7, s * 0.3, seg=8, rings=6), "sweat",
             (eye_dx + s * 1.4, s * 1.3, s * 0.1))
    sw.rotation_euler = (0, 0, math.radians(-20))


# 감정 → 켤 부품 (나머지는 끔). three.js 재생기도 같은 표를 쓴다 (out/emotions.json).
EMOTIONS = {
    "neutral":     ["eye_open", "brow_neutral", "mouth_smile"],
    "happy":       ["eye_happy", "brow_neutral", "mouth_open", "blush"],
    "surprised":   ["eye_wide", "brow_neutral", "mouth_o"],
    "sad":         ["eye_open", "brow_sad", "mouth_frown"],
    "angry":       ["eye_open", "brow_angry", "mouth_flat"],
    "embarrassed": ["eye_closed", "brow_neutral", "mouth_wavy", "blush", "sweat"],
    "sleepy":      ["eye_closed", "brow_neutral", "mouth_flat"],
}
# AI 캐릭터: 입 없이 눈만 (운영자 2026-11-18). 눈 모양·눈썹·볼터치·땀으로 표정.
AI_EMOTIONS = {
    "neutral":     ["eye_bar"],
    "happy":       ["eye_happy", "blush"],
    "surprised":   ["eye_barwide"],
    "sad":         ["eye_barlow", "brow_sad"],
    "angry":       ["eye_bar", "brow_angry"],
    "embarrassed": ["eye_squint", "blush", "sweat"],
    "sleepy":      ["eye_line"],
}
FACE_PARTS = ["eye_open", "eye_wide", "eye_happy", "eye_closed", "brow_angry", "brow_sad", "blush",
              "mouth_smile", "mouth_frown", "mouth_flat", "mouth_open", "mouth_o", "mouth_wavy", "sweat",
              "brow_neutral", "mouth_grin",   # 이 둘은 사람 캐릭터만 (없으면 무시)
              "eye_barwide", "eye_barlow", "eye_bar", "eye_squint", "eye_line"]   # AI 눈 (barwide·barlow를 bar보다 먼저)


def part_of(name, key):
    """'claude_eye_open_L' → 'eye_open' (eyehl은 부모 눈을 따라감)."""
    rest = name[len(key) + 1:]
    for p in FACE_PARTS:
        if rest == p or rest.startswith(p + "_"):
            return p
    return None


def set_emotion(root, key, emo, table=None):
    on = set((table or EMOTIONS)[emo])
    for o in root.children_recursive:
        if o.name.startswith(f"{key}_eyehl_"):
            continue
        p = part_of(o.name, key)
        if p:
            hide = p not in on
            o.hide_render = hide
            for c in o.children_recursive:
                c.hide_render = hide


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


def emotion_sheet(sc, roots):
    """캐릭터마다 감정 7개 정면 사진 → out/sheet/<캐릭터>_<감정>.png (tile_sheet.py로 한 장에)."""
    d = os.path.join(OUT, "sheet")
    os.makedirs(d, exist_ok=True)
    for o in bpy.data.objects:  # 백그라운드 연속 렌더에서 그림자 지도가 꼬여 까맣게 나오는 일 방지
        if o.type == "LIGHT":
            o.data.use_shadow = False
    home = {k: r.location.copy() for k, r in roots.items()}
    for key, root in roots.items():
        for k, r in roots.items():
            r.location = (0, 0, home[k].z) if k == key else (home[k].x, 50, home[k].z)
        bpy.context.view_layer.update()
        z = root.location.z
        camera(sc, (0.0, -2.6, z + 0.15), (0, 0, z + 0.05), lens=50, focus=(0, -0.3, z), fstop=1.6)
        for emo in AI_EMOTIONS:
            set_emotion(root, key, emo, AI_EMOTIONS)
            render(sc, os.path.join(d, f"{key}_{emo}.png"), 640, 640)
        set_emotion(root, key, "neutral", AI_EMOTIONS)


def main():
    sc = setup_scene()
    mats = {"eye": material("eye", hex2rgb("#141414"), rough=0.25),
            "hl": material("hl", (1, 1, 1), rough=0.2, emit=1.5),
            "blush": material("blush", hex2rgb("#FF6F86"), rough=0.6, emit=0.25),
            "inner": material("inner", hex2rgb("#2A0A10"), rough=0.5),
            "sweat": material("sweat", hex2rgb("#9FD8FF"), rough=0.1, emit=0.3)}
    roots = {}
    for i, key in enumerate(ONLY):
        cfg = CHARS[key]
        root = link(bpy.data.objects.new(key, None))
        body = make_body(key, cfg)
        facet_colors(body, body_color(key), jitter=CHARS[key].get("jitter", 0.11), seed=11 + i)
        bmat = material(f"{key}_mat", vcol=True, rough=0.68)
        body.data.materials.append(bmat)
        body.parent = root
        add_face(key, body, root, mats=mats, **cfg["face"])
        sole = add_feet(key, body, root, cfg, bmat) if cfg.get("feet") else None
        print(key, "faces", len(body.data.polygons))
        # 로고 평면(XY, 앞 +Z)을 세워서 앞이 -Y(카메라 쪽). glTF에서는 앞이 +Z.
        root.rotation_euler = (math.radians(90), 0, 0)
        root.location = ((i - (len(ONLY) - 1) / 2) * 2.7, 0, -sole if sole is not None else 1.0 + cfg.get("dilate", 0))
        roots[key] = root
    bpy.context.view_layer.update()

    import json
    with open(os.path.join(OUT, "emotions.json"), "w", encoding="utf-8") as fp:
        json.dump({"parts": FACE_PARTS, "emotions": AI_EMOTIONS, "human_emotions": EMOTIONS}, fp, ensure_ascii=False, indent=1)
    for key, root in roots.items():
        loc = root.location.copy()
        root.location = (0, 0, loc.z)  # glb 원점 = 바닥 가운데 (통통 튀기·찌그러지기 기준)
        bpy.ops.object.select_all(action="DESELECT")
        root.select_set(True)
        for c in root.children_recursive:
            c.select_set(True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{key}.glb"), export_format="GLB", use_selection=True, export_vertex_color="ACTIVE")
        root.location = loc

    for key, root in roots.items():
        set_emotion(root, key, "neutral", AI_EMOTIONS)
    if "--sheet" in argv:
        return emotion_sheet(sc, roots)
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


if __name__ == "__main__":
    main()
