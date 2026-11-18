"""사람 캐릭터 (젠슨 황·일반 남성) 로우폴리 + 뼈대 — Blender 스크립트.

운영자 2026-11-18: 사람 캐릭터는 일단 젠슨 황, 일반 남성 두 명. AI 캐릭터(build.py)와 같은 통통한 로우폴리 화풍.
① 캐릭터 원본: 머리·얼굴·몸·의상·관절. 부위마다 따로 덩어리(장난감 피규어처럼) → 뼈에 붙임(관절에서 꺾임).
얼굴은 build.py와 같은 표정 부품(EMOTIONS) — three.js가 켜고 끔.
젠슨 황은 실제 인물: 패러디 캐리커처(검정 가죽 재킷·은회색 머리)로만 쓰고, 하지 않은 말을 진짜 발언처럼 쓰지 않는다.

실행:
  & "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe" --background --python experiments/lowpoly-chars/build_humans.py -- [--only jensen] [--quick] [--sheet]
결과: out/<이름>.glb (뼈대 포함, 앞 = glTF +Z), out/q34_<이름>.png, out/pose_<이름>.png(관절 시험 포즈), out/preview_humans.png
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B  # noqa: E402  (도구·표정 부품·장면 공용)

argv = B.argv
ONLY = argv[argv.index("--only") + 1].split(",") if "--only" in argv else ["jensen", "man"]
OUT = B.OUT

SKIN = "#EDBF98"
# 면 수: 삼각형을 더 잘게 나눈 각진 로우폴리 (운영자 2026-11-18 "일반 남성은 그대로, 삼각형 좀 더 세부적으로")
FACES = dict(head=1400, hair=1000, body=4200)
FACET_SMOOTH, FACET_JITTER = 1, 0.11   # 덜 매끈하게 + 면마다 명암 차이 → 각이 보이게
HUMANS = {
    "jensen": dict(
        skin="#C98F6A", hair="#8E8E8A", top="#1A1A1C", top_rough=0.32, tee="#34343A",
        pants="#25272E", shoes="#111111", sleeves="top",
        # 얼굴 (운영자 2026-11-18 "얼굴형 더 잘"): 각지고 넓은 턱, 웃는 볼, 큰 코, 가는 눈, 짙은 눈썹, 이 보이는 큰 웃음
        # 느낌만 살린 로우폴리 (운영자 2026-11-18 "코 옆으로 넓고, 안경, 사각 얼굴형, 비율"): 사각 턱·각진 턱 모서리·넓은 코
        head_shapes=[("e", (0, 0.06, -0.03), (0.39, 0.37, 0.38)),          # 윗머리
                     ("e", (0, -0.17, 0.03), (0.38, 0.24, 0.33)),          # 넓은 아래 얼굴
                     ("e", (0.2, -0.26, 0.04), (0.15, 0.1, 0.24)),         # 턱 모서리 (사각 얼굴형, 매끈하게)
                     ("e", (-0.2, -0.26, 0.04), (0.15, 0.1, 0.24)),
                     ("e", (0, -0.08, 0.40), (0.09, 0.065, 0.065)),        # 넓은 코끝
                     ("e", (0.075, -0.11, 0.36), (0.055, 0.045, 0.05)),    # 큰 콧볼
                     ("e", (-0.075, -0.11, 0.36), (0.055, 0.045, 0.05))],
        hair_main=((0, 0.15, -0.13), (0.43, 0.40, 0.40)),       # 앞머리 라인을 올리고 뒤로 (이마가 넓게 보이게)       # 옆은 짧고 뒤로 넘긴 은회색 머리
        # 참고: 엔비디아 공식 'Toy Jensen' — 옆 가르마로 한쪽에 볼륨 있게 넘긴 은회색 머리(짙은 줄무늬)
        hair_extra=[((0.05, 0.42, 0.04), (0.34, 0.13, 0.25)),   # 위로 세워 뒤로 넘긴 볼륨 (앞으로 내려오지 않게)
                    ((0.14, 0.40, -0.14), (0.27, 0.13, 0.26)), ((-0.18, 0.34, -0.12), (0.2, 0.11, 0.24))],
        hair_streak="#8E8E8A",
        brow="#3B3936", glasses="#1C1C1E",   # 안경 (운영자 2026-11-18)
        face=dict(eye_s=0.064, eye_aspect=0.62, eye_dx=0.15, mouth_w=0.075, mouth_dy=-0.20, brows=True, grin=True),
        emo={"neutral": ["eye_open", "brow_neutral", "mouth_grin"],
             "happy": ["eye_happy", "brow_neutral", "mouth_grin", "blush"]},
        collar=True, blocky=True, fashion="jensen", blocky_head=True, photo_tint=0.85, photo_face=True),   # 각진 블록 몸 + 젠슨 황 패션 (운영자 2026-11-18)
    "man": dict(
        skin="#E2AE86", hair="#2B211C", top="#7FA6D4", top_rough=0.7, tee=None,
        pants="#3A3F4A", shoes="#5B3B29", sleeves="top",
        hair_main=((0, 0.12, -0.05), (0.46, 0.44, 0.44)),
        hair_extra=[((0, 0.30, 0.15), (0.37, 0.10, 0.12))],  # 앞머리: 이마에 붙게 (운영자 2026-11-18 "앞머리 왜 튀어나왔어")
        brow="#241C18", face=dict(brows=True), blocky=True, glasses="#2A2A2E", glasses_style="round",   # 각진 블록 몸 + 얇은 원형테 (운영자 2026-11-18)
        collar=False),
}
FACE = dict(cx=0.0, cy=0.0, eye_dx=0.15, eye_s=0.075, mouth_dy=-0.17, mouth_w=0.06, blush=(0.26, -0.10, 0.06))

# 뼈 (머리, 꼬리, 부모) — 키 2.2, 머리가 큰 2.6등신
BONES = {
    "root": ((0, 0, 0), (0, 0, 0.2), None),
    "hips": ((0, 0, 0.74), (0, 0, 0.95), "root"),
    "spine": ((0, 0, 0.95), (0, 0, 1.30), "hips"),
    "neck": ((0, 0, 1.30), (0, 0, 1.42), "spine"),
    "head": ((0, 0, 1.42), (0, 0, 1.95), "neck"),
}
for sd, sx in (("L", 1), ("R", -1)):
    BONES[f"upper_arm.{sd}"] = ((0.35 * sx, 0, 1.23), (0.47 * sx, 0, 0.98), "spine")
    BONES[f"lower_arm.{sd}"] = ((0.47 * sx, 0, 0.98), (0.53 * sx, -0.02, 0.66), f"upper_arm.{sd}")
    BONES[f"thigh.{sd}"] = ((0.16 * sx, 0, 0.82), (0.16 * sx, 0, 0.45), "hips")
    BONES[f"shin.{sd}"] = ((0.16 * sx, 0, 0.45), (0.16 * sx, 0, 0.10), f"thigh.{sd}")


# ---------- 덩어리 만들기 ----------
def ellipsoid_into(bm, c, s):
    m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal((*s, 1.0))
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=1.0, matrix=m)


def capsule_into(bm, a, b, r, r2=None):
    """r → r2로 가늘어지는 팔다리 (운영자 2026-11-18 "몸을 자연스러운 모양으로")."""
    a, b = Vector(a), Vector(b)
    r2 = r if r2 is None else r2
    n = max(2, int((b - a).length / (min(r, r2) * 0.4)) + 1)
    for k in range(n):
        t = k / (n - 1)
        rr = r + (r2 - r) * t
        ellipsoid_into(bm, a.lerp(b, t), (rr, rr, rr))


def blob(name, shapes, faces, color, rough=0.68, voxel=0.018, smooth=4, jitter=0.07, color_fn=None):
    smooth, jitter = min(smooth, FACET_SMOOTH + 1), max(jitter, FACET_JITTER)
    """shapes: [('e', 중심, 반지름3) | ('c', a, b, r)] → 합쳐 리메시 → 매끈 → 면 줄이기 → 평면 셰이딩 + 면 색."""
    bm = bmesh.new()
    for s in shapes:
        if s[0] == "e":
            ellipsoid_into(bm, s[1], s[2])
        else:
            capsule_into(bm, s[1], s[2], s[3], s[4] if len(s) > 4 else None)
    ob = B.bm_to_obj(bm, name)
    B.remesh(ob, voxel)
    if smooth:
        m = ob.modifiers.new("sm", "SMOOTH")
        m.factor, m.iterations = 0.5, smooth
        B.apply_mod(ob, m)
    B.decimate(ob, faces)
    B.shade_flat(ob)
    base = B.hex2rgb(color)
    B.facet_colors(ob, color_fn or (lambda c: base), jitter=jitter, seed=hash(name) % 1000)
    ob.data.materials.append(B.material(f"{name}_mat", vcol=True, rough=rough))
    return ob


def rounded_box(bm, center, size, round_=0.35, cuts=3, top_scale=1.0, matrix=None):
    """모서리를 둥글린 상자 (각진 면 유지). size=(가로 x, 세로 y, 앞뒤 z) 반지름. top_scale: 위쪽 가로 비율."""
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=2.0)
    bmesh.ops.subdivide_edges(tmp, edges=tmp.edges[:], cuts=cuts, use_grid_fill=True)
    for v in tmp.verts:
        p = v.co.copy()
        p = p * (1 - round_) + p.normalized() * 1.25 * round_
        k = 1.0 + (top_scale - 1.0) * max(0.0, p.y)
        v.co = Vector((center[0] + p.x * size[0] * k, center[1] + p.y * size[1], center[2] + p.z * size[2]))
        if matrix is not None:
            v.co = matrix @ v.co
    me = bpy.data.meshes.new("_rb")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def photo_uv(head):
    """원본 사진 질감을 머리 앞면에 맞춰 붙임 (운영자 2026-11-18 "원래 사진 원본을 저 모델에 맞게 살짝").
    가로: 사진 눈 사이 205px = 캐릭터 눈 사이 0.30 / 세로: 사진 눈→입선 240px = 캐릭터 눈→입 0.20 (눈·입 위치가 겹치게)."""
    me = head.data
    uv = me.uv_layers.new(name="UVMap")
    W, H = 1459, 1740
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            px, py = 682 + co.x * 683, 605 - co.y * 1200
            uv.data[li].uv = (min(max(px / W, 0), 1), 1 - min(max(py / H, 0), 1))
    img = bpy.data.images.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref", "jensen_face_tex.png"))
    m = bpy.data.materials.new("jensen_face_photo")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.72
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def photo_tint(head, amount):
    """앞을 향한 면 색에 사진 피부 명암(ref/jensen_skin_detail.png)을 섞음. 머리 좌표(앞 +Z, 위 +Y, 눈 높이 y=0) → 사진 눈 (682,605), 683px/단위."""
    import numpy as np
    img = bpy.data.images.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref", "jensen_skin_detail.png"))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[..., :3]
    lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    me = head.data
    attr = me.color_attributes["Col"]
    ref = lin(px[h - 1 - 820, 560:620].mean(axis=0))          # 볼 피부 기준 밝기 (사진 전체 톤 맞춤)
    for p in me.polygons:
        c, n = p.center, p.normal
        a = amount * max(0.0, min(1.0, (n.z - 0.15) / 0.5))   # 앞을 향한 면일수록 진하게
        if a <= 0 or c.y > 0.3:
            continue
        x, y = 682 + c.x * 683, 605 - c.y * 683
        xi, yi = int(min(max(x, 4), w - 5)), int(min(max(h - 1 - y, 4), h - 5))
        s = lin(px[yi - 2:yi + 3, xi - 2:xi + 3].reshape(-1, 3).mean(axis=0))
        lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        r1 = float(np.clip(lum(s) / max(lum(ref), 1e-4), 0.55, 1.3))   # 사진의 밝기 차이만 (색은 캐릭터 피부색 유지)
        rel = (r1, r1, r1)
        for li in p.loop_indices:
            col = attr.data[li].color
            attr.data[li].color = tuple(float(col[i] * (1 - a + a * rel[i])) for i in range(3)) + (1.0,)
    bpy.data.images.remove(img)


def make_blocky_head(key, cfg):
    """각진 블록 머리 (운영자 2026-11-18 "원통형 같은 거 붙이지 말고 각지게, 전체적인 느낌만"):
    둥근 모서리 상자 하나로 사각 얼굴 + 각진 넓은 코 + 각진 귀 / 머리카락은 각진 판 두 개."""
    from mathutils import Matrix
    bm = bmesh.new()
    rounded_box(bm, (0, -0.02, 0), (0.39, 0.42, 0.37), round_=0.3, cuts=7, top_scale=0.95)      # 사각 얼굴: 규칙적인 격자 면 (운영자 2026-11-18 "불규칙한 각짐 말고")
    rounded_box(bm, (0, -0.09, 0.39), (0.085, 0.06, 0.06), round_=0.2, cuts=1)                   # 넓은 코
    for sx in (1, -1):
        rounded_box(bm, (0.4 * sx, -0.02, 0), (0.05, 0.09, 0.06), round_=0.2, cuts=1)           # 귀
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    head = B.bm_to_obj(bm, f"{key}_head")
    # 턱: 아래로 갈수록 살짝 좁게 (운영자 2026-11-18 "턱이 너무 사각은 아니게")
    for v in head.data.vertices:
        if v.co.y < -0.04:
            t = min(1.0, (-0.04 - v.co.y) / 0.4)
            v.co.x *= 1.0 - 0.32 * t ** 1.6
    head.data.update()
    B.shade_flat(head)
    sk = B.hex2rgb(cfg["skin"])
    B.facet_colors(head, lambda c: sk, jitter=0.04, seed=7)
    if cfg.get("photo_face"):
        head.data.materials.append(photo_uv(head))          # 원본 사진 질감 (face_texture.py)
    else:
        if cfg.get("photo_tint"):
            photo_tint(head, cfg["photo_tint"])
        head.data.materials.append(B.material(f"{key}_head_mat", vcol=True, rough=0.72))
    # 머리카락 (운영자 2026-11-18 "앞에서 보면 모자 쓴 느낌"): 상자를 얹지 않고 머리 모양을 따라 감싸는 껍질.
    # 얼굴 쪽은 실제 이마선(가운데 높고 관자놀이로 들어감)으로 따내고, 귀 주변·목 아래는 비움.
    bm = bmesh.new()
    rounded_box(bm, (0, 0.0, -0.015), (0.415, 0.45, 0.395), round_=0.3, cuts=5, top_scale=0.95)
    rounded_box(bm, (0.04, 0.4, 0.0), (0.3, 0.08, 0.3), round_=0.25, cuts=2,                     # 위로 넘긴 볼륨 (낮게)
                matrix=Matrix.Rotation(math.radians(-6), 4, "Z"))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])

    def hairline(x):           # 이 높이 아래 앞쪽은 얼굴 (가르마 x -0.12 쪽은 살짝 높음)
        return 0.25 - 1.1 * max(0.0, abs(x) - 0.1) ** 1.2 + (0.02 if x < -0.05 else 0.0)
    kill = [f for f in bm.faces if (lambda c: (c.z > 0.03 and c.y < hairline(c.x))
                                    or c.y < -0.32
                                    or (abs(c.x) > 0.3 and c.y < 0.06 and c.z > -0.17))(f.calc_center_median())]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    hair = B.bm_to_obj(bm, f"{key}_hair")
    B.shade_flat(hair)
    hc, hd = B.hex2rgb(cfg["hair"]), B.hex2rgb("#4E4E4B")
    # 가르마 선과 판 사이 그늘은 짙게
    B.facet_colors(hair, lambda c: hd if (-0.16 < c.x < -0.1 and c.y > 0.2 and c.z > -0.25) else hc, jitter=0.07, seed=8)
    hair.data.materials.append(B.material(f"{key}_hair_mat", vcol=True, rough=0.8))
    return head, hair


def make_head(key, cfg, mats):
    """머리는 로고 캐릭터와 같은 좌표(앞 +Z, 위 +Y)로 만들고 얼굴 부품을 붙인 뒤 세운다."""
    grp = B.link(bpy.data.objects.new(f"{key}_headgrp", None))
    if cfg.get("blocky_head"):
        head, hair = make_blocky_head(key, cfg)
        head.parent = grp
        hair.parent = grp
        bpy.context.view_layer.update()
        m2 = {**mats, "brow": B.material(f"{key}_brow", B.hex2rgb(cfg.get("brow", "#222222")), rough=0.8),
              "teeth": B.material("teeth", B.hex2rgb("#F4F1EA"), rough=0.35)}
        fc = {**FACE, **cfg.get("face", {})}
        B.add_face(key, head, grp, mats=m2, **fc)
        if cfg.get("glasses"):
            add_glasses(key, fc, cfg["glasses"])
        return grp
    skin = cfg.get("head_shapes") or [("e", (0, 0, 0), (0.42, 0.40, 0.40)),   # 머리
                                      ("e", (0, -0.07, 0.40), (0.05, 0.045, 0.04))]  # 코
    skin = skin + [("e", (0.41, -0.02, 0), (0.06, 0.10, 0.07)),       # 귀
                   ("e", (-0.41, -0.02, 0), (0.06, 0.10, 0.07))]
    head = blob(f"{key}_head", skin, FACES["head"], cfg["skin"], rough=0.72, voxel=0.014)
    head.parent = grp
    hs = [("e", *cfg["hair_main"])] + [("e", *h) for h in cfg["hair_extra"]]
    hfn = None
    if cfg.get("hair_streak"):  # 앞→뒤로 흐르는 짙은 줄무늬
        hc, sc_ = B.hex2rgb(cfg["hair"]), B.hex2rgb(cfg["hair_streak"])
        hfn = lambda c: sc_ if math.sin(c.x * 26 + c.z * 3 + c.y * 4) > 0.45 else hc
    hair = blob(f"{key}_hair", hs, FACES["hair"], cfg["hair"], rough=0.8, voxel=0.016, smooth=3, jitter=0.08, color_fn=hfn)
    hair.parent = grp
    bpy.context.view_layer.update()
    m2 = {**mats, "brow": B.material(f"{key}_brow", B.hex2rgb(cfg.get("brow", "#222222")), rough=0.8),
          "teeth": B.material("teeth", B.hex2rgb("#F4F1EA"), rough=0.35)}
    fc = {**FACE, **cfg.get("face", {})}
    B.add_face(key, head, grp, mats=m2, **fc)
    if cfg.get("glasses") and cfg.get("glasses_style") == "round":
        add_round_glasses(key, fc, cfg["glasses"])
    elif cfg.get("glasses"):
        add_glasses(key, fc, cfg["glasses"])
    return grp


def add_round_glasses(key, fc, color):
    """얇은 원형테 안경 (일반 남성, 운영자 2026-11-18 "젠슨 황과 똑같은 안경 말고 얇은 원형테"): 위아래 같은 굵기."""
    face = bpy.data.objects[f"{key}_face"]
    z0 = face.location.z
    s, dx = fc["eye_s"], fc["eye_dx"]
    r, zf, t = s * 1.35, s * 0.8, s * 0.07
    m = B.material(f"{key}_glasses", B.hex2rgb(color), rough=0.3)

    def tube(name, pts, rad):
        ob = B.arc_tube(name, pts, rad, ring=5)
        ob.data.materials.append(m)
        ob.parent = face
    for sd, sx in (("L", -1), ("R", 1)):
        ex = sx * dx
        tube(f"{key}_glasses_rim_{sd}", [(ex + r * math.cos(math.radians(a)), s * 0.1 + r * math.sin(math.radians(a)), zf) for a in range(0, 361, 15)], t)
        x_out = ex + sx * r
        tube(f"{key}_glasses_arm_{sd}", [(x_out, s * 0.25, zf), (sx * 0.40, s * 0.3, zf - 0.12), (sx * 0.42, s * 0.2, -z0 + 0.02)], t)
    tube(f"{key}_glasses_bridge", [(-dx + r, s * 0.35, zf), (0, s * 0.55, zf + 0.01), (dx - r, s * 0.35, zf)], t)


def add_glasses(key, fc, color):
    """하프림(브로우라인) 안경 — 위에만 굵은 검정 테, 아래는 테 없음(가는 은색 선). 운영자 2026-11-18 "위에만 테".
    항상 보임(표정과 무관). 얼굴 묶음 좌표(앞 +Z)."""
    face = bpy.data.objects[f"{key}_face"]
    z0 = face.location.z
    s, dx = fc["eye_s"], fc["eye_dx"]
    rx, ry, zf = s * 1.6, s * 1.15, s * 0.8
    black = B.material(f"{key}_glasses", B.hex2rgb(color), rough=0.3)
    wire = B.material(f"{key}_glasses_wire", B.hex2rgb("#B8BCC2"), rough=0.25)

    def tube(name, pts, rad, mat):
        ob = B.arc_tube(name, pts, rad, ring=5)
        ob.data.materials.append(mat)
        ob.parent = face
        return ob

    def rim_pt(ex, t):  # 둥근 사각형 둘레 (t: 0=오른쪽, 90=위)
        c, sn = math.cos(math.radians(t)), math.sin(math.radians(t))
        return (ex + rx * math.copysign(abs(c) ** 0.6, c), ry * math.copysign(abs(sn) ** 0.6, sn), zf)
    for sd, sx in (("L", -1), ("R", 1)):
        ex = sx * dx
        top = [rim_pt(ex, t) for t in range(-10, 191, 10)]          # 위 반쪽 + 옆 조금: 굵은 검정 윗테
        tube(f"{key}_glasses_top_{sd}", top, s * 0.2, black)
        bot = [rim_pt(ex, t) for t in range(190, 351, 10)]          # 아래 반쪽: 가는 은색 선
        tube(f"{key}_glasses_wire_{sd}", bot, s * 0.04, wire)
        x_out = ex + sx * rx
        tube(f"{key}_glasses_arm_{sd}", [(x_out, s * 0.4, zf), (sx * 0.40, s * 0.5, zf - 0.12), (sx * 0.42, s * 0.35, -z0 + 0.02)], s * 0.1, black)
    tube(f"{key}_glasses_bridge", [(-dx + rx * 0.97, s * 0.55, zf), (0, s * 0.7, zf + 0.01), (dx - rx * 0.97, s * 0.55, zf)], s * 0.1, black)


def make_body(key, cfg):
    """몸 전체를 이어진 한 덩어리로 (운영자 2026-11-18 "몸도 자연스럽게"): 가슴→허리→골반→다리, 어깨→팔.
    옷 구분은 덧붙인 덩어리 없이 면 색으로만 (깃 등을 달면 지저분해짐). 좌표: 서 있는 자세(위 +Z, 앞 -Y), 팔은 살짝 벌린 A자."""
    S = [("e", (0, 0, 1.12), (0.30, 0.20, 0.19)),            # 가슴
         ("e", (0, 0, 0.96), (0.26, 0.18, 0.16)),            # 허리
         ("e", (0, 0, 0.83), (0.28, 0.19, 0.12)),            # 골반
         ("c", (-0.27, 0, 1.22), (0.27, 0, 1.22), 0.10),      # 어깨선 (둥글게 처진 어깨)
         ("c", (0, 0, 1.22), (0, 0, 1.44), 0.075)]            # 목
    for sx in (1, -1):
        S += [("e", (0.33 * sx, 0, 1.22), (0.105, 0.10, 0.10)),                     # 어깨 둥근 곳
              ("c", (0.35 * sx, 0, 1.22), (0.47 * sx, 0, 0.98), 0.1, 0.092),        # 위팔: 넉넉한 소매 (운영자 2026-11-18 "쫄쫄이 느낌")
              ("c", (0.47 * sx, 0, 0.98), (0.525 * sx, -0.02, 0.71), 0.09, 0.08),    # 아래팔: 소매 끝까지 넉넉하게
              ("e", (0.535 * sx, -0.025, 0.655), (0.06, 0.045, 0.082)),            # 손: 납작한 손바닥
              ("c", (0.16 * sx, 0, 0.84), (0.155 * sx, -0.01, 0.45), 0.135, 0.118), # 허벅지: 넉넉한 바지
              ("c", (0.155 * sx, -0.01, 0.45), (0.155 * sx, 0.01, 0.13), 0.115, 0.108),  # 바짓가랑이: 거의 일자로
              ("e", (0.16 * sx, -0.05, 0.07), (0.115, 0.175, 0.075))]               # 신발
    top_c, pants_c = B.hex2rgb(cfg["top"]), B.hex2rgb(cfg["pants"])
    skin_c, shoes_c = B.hex2rgb(cfg["skin"]), B.hex2rgb(cfg["shoes"])
    tee_c = B.hex2rgb(cfg["tee"]) if cfg["tee"] else None

    def color(c):
        ax = abs(c.x)
        if c.z < 0.135:
            return shoes_c
        if c.z < 0.725 and ax > 0.42:                 # 손
            return skin_c
        if c.z > 1.31 and ax < 0.12:                  # 목
            return skin_c
        if c.z < 0.86 and ax < 0.33:                  # 바지
            return pants_c
        if tee_c and c.y < -0.08 and c.z > 0.88 and ax < 0.035 + (c.z - 0.88) * 0.33:   # 열린 재킷 안 티셔츠(V)
            return tee_c
        return top_c
    return blob(f"{key}_body", S, FACES["body"], cfg["top"], cfg["top_rough"], voxel=0.016, smooth=8, color_fn=color)


def skin_to(ob, ao):
    """뼈에 자동 가중치 (관절이 자연스럽게 휨). root 뼈는 변형에서 뺌."""
    ao.data.bones["root"].use_deform = False
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    ao.select_set(True)
    bpy.context.view_layer.objects.active = ao
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    # 관절 가중치를 부드럽게 펴서 꺾일 때 찌그러지지 않게 (운영자 2026-11-18 "관절 때문에 이상한 느낌")
    smooth_weights(ob, repeat=12, factor=0.6)


def smooth_weights(ob, repeat=12, factor=0.6):
    """정점 가중치를 이웃 평균으로 여러 번 펴고 다시 합이 1이 되게 (관절에서 부드럽게 휨)."""
    me = ob.data
    n = len(me.vertices)
    groups = [g.index for g in ob.vertex_groups]
    W = {g: [0.0] * n for g in groups}
    for v in me.vertices:
        for ge in v.groups:
            if ge.group in W:
                W[ge.group][v.index] = ge.weight
    nb = [[] for _ in range(n)]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    for _ in range(repeat):
        for g in groups:
            w = W[g]
            W[g] = [w[i] * (1 - factor) + factor * (sum(w[j] for j in nb[i]) / len(nb[i]) if nb[i] else w[i]) for i in range(n)]
    for i in range(n):
        tot = sum(W[g][i] for g in groups) or 1.0
        for g in groups:
            val = W[g][i] / tot
            vg = ob.vertex_groups[g]
            if val > 0.001:
                vg.add([i], val, "REPLACE")
            else:
                vg.remove([i])


def emo_table(key):
    """캐릭터별 표정 덮어쓰기 (젠슨 황: 평소에도 이 보이는 웃음)."""
    return {**B.EMOTIONS, **HUMANS[key].get("emo", {})}


# 비율 (운영자 2026-11-18 "상체가 너무 짧고 다리가 기괴하게 길다"): 블록 몸 캐릭터만 적용
LEG_K, TORSO_K, HIP_Z, CHEST_Z = 0.78, 1.14, 0.86, 1.30
PROP = {"on": False}


def pz(z, arm=False):
    """원래 높이 → 새 높이. 다리(엉덩이 아래)는 줄이고 상체는 늘리고, 그 위(목·머리)와 팔은 통째로 이동."""
    if not PROP["on"]:
        return z
    hip = HIP_Z * LEG_K
    top_shift = hip + (CHEST_Z - HIP_Z) * TORSO_K - CHEST_Z
    if arm:
        return z + top_shift
    if z <= HIP_Z:
        return z * LEG_K
    if z <= CHEST_Z:
        return hip + (z - HIP_Z) * TORSO_K
    return z + top_shift


def pv(p, arm=False):
    return (p[0], p[1], pz(p[2], arm))


def make_rig(key):
    arm = bpy.data.armatures.new(f"{key}_rig")
    ao = B.link(bpy.data.objects.new(key, arm))
    bpy.context.view_layer.objects.active = ao
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ao.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (h, t, par) in BONES.items():
        eb = arm.edit_bones.new(name)
        is_arm = name.startswith(("upper_arm", "lower_arm"))
        eb.head, eb.tail = Vector(pv(h, is_arm)), Vector(pv(t, is_arm))
        if name.startswith(("upper_arm", "lower_arm")) or name.startswith("thigh") or name.startswith("shin"):
            eb.roll = 0
    for name, (h, t, par) in BONES.items():
        if par:
            arm.edit_bones[name].parent = arm.edit_bones[par]
    bpy.ops.object.mode_set(mode="OBJECT")
    return ao


def attach(ob, ao, bone):
    mw = ob.matrix_world.copy()
    ob.parent = ao
    ob.parent_type = "BONE"
    ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = mw


def block(name, a, b, w, d, color, rough=0.75, taper=1.0, bevel=0.018, paint=None, cuts=5, arm=False, seams=None):
    a, b = pv(a, arm), pv(b, arm)
    """a→b 축을 따라 늘인 상자 (가로 w, 앞뒤 d), 모서리 살짝 깎음. taper = b쪽 끝 크기 비율. 운영자 2026-11-18 레퍼런스처럼 각진 블록 몸."""
    from mathutils import Matrix
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        k = 1.0 + (taper - 1.0) * (v.co.z + 0.5)
        v.co = Vector((v.co.x * w * k, v.co.y * d * k, (v.co.z + 0.5) * L))
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    if paint and cuts and not seams:   # 옷 디테일을 면 색으로 그리려면 면을 잘게 (모양은 그대로 상자)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    q = (b - a).normalized().to_track_quat("Z", "Y")
    bmesh.ops.transform(bm, matrix=Matrix.Translation(a) @ q.to_matrix().to_4x4(), verts=bm.verts[:])
    for co, no in (seams or []):   # 옷 무늬 선을 따라 실제로 잘라 경계를 반듯하게 (운영자 2026-11-18 "경계 다듬고")
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no, dist=0.0003)
    if seams:
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    ob = B.bm_to_obj(bm, name)
    B.shade_flat(ob)
    base = B.hex2rgb(color)
    fn = (lambda c: B.hex2rgb(paint(c) or color)) if paint else (lambda c: base)
    B.facet_colors(ob, fn, jitter=0.05, seed=hash(name) % 1000)
    ob.data.materials.append(B.material(f"{name}_mat", vcol=True, rough=rough))
    return ob


# 옷 디자인 (운영자 2026-11-18 "옷도 레퍼런스 계정처럼"): 블록 위에 셔츠·티·벨트·바지 주름·밑창을 면 색으로
SHIRT_D, TEE_W, BELT, BUCKLE, PANTS_D, SOLE = "#5E86B8", "#EDEDE8", "#1E1E22", "#C9A94E", "#2E3138", "#2A1C14"


def paint_torso(c):
    ax = abs(c.x)
    if c.y < -0.1 and c.z > pz(1.1) and ax < 0.02 + (c.z - pz(1.1)) * 0.55:
        return TEE_W                                   # 깃 사이로 보이는 흰 티 (V)
    if c.z > pz(1.22) and ax < 0.17 and c.y < 0.05:
        return SHIRT_D                                 # 셔츠 깃
    if c.y < -0.14 and ax < 0.014 and c.z < pz(1.1):
        return SHIRT_D                                 # 단추 줄
    if c.y < -0.14 and 0.08 < c.x < 0.2 and pz(1.02) < c.z < pz(1.14):
        return SHIRT_D                                 # 가슴 주머니
    if c.z < pz(0.9):
        return SHIRT_D                                 # 밑단
    return None


def paint_sleeve(c):
    return SHIRT_D if c.z < pz(0.78, arm=True) else None             # 소매 끝 커프스


def paint_hips(c):
    if c.z > pz(0.83):
        return BUCKLE if (abs(c.x) < 0.045 and c.y < -0.12) else BELT
    return None


def paint_hips_silver(c):
    if c.z > pz(0.83):
        return "#B8BCC2" if (abs(c.x) < 0.045 and c.y < -0.12) else BELT
    return None


def paint_leg(cx):
    return lambda c: PANTS_D if (abs(c.x - cx) < 0.014 and c.y < -0.08) else None   # 바지 앞 주름선


def paint_shoe(c):
    return SOLE if c.z < 0.035 else None


def torso_seams():
    z0 = pz(1.1)
    S = [((0.02, 0, z0), (1, 0, -0.55)), ((-0.02, 0, z0), (-1, 0, -0.55)), ((0, 0, z0), (0, 0, 1)),   # V넥
         ((0, 0, pz(1.22)), (0, 0, 1)), ((0.17, 0, 0), (1, 0, 0)), ((-0.17, 0, 0), (1, 0, 0)),         # 깃
         ((0.014, 0, 0), (1, 0, 0)), ((-0.014, 0, 0), (1, 0, 0)),                                     # 단추 줄
         ((0.08, 0, 0), (1, 0, 0)), ((0.2, 0, 0), (1, 0, 0)), ((0, 0, pz(1.02)), (0, 0, 1)), ((0, 0, pz(1.14)), (0, 0, 1)),  # 주머니
         ((0, 0, pz(0.9)), (0, 0, 1)), ((0, -0.12, 0), (0, 1, 0)), ((0, -0.14, 0), (0, 1, 0))]       # 밑단, 앞면
    return S


# 젠슨 황 패션: 열린 검정 가죽 재킷(은색 지퍼 두 줄, 넓은 깃) + 안에 검정 티
JACKET_COLLAR, ZIP, TEE_BLACK, JACKET_HEM = "#2A2A2E", "#A9AEB5", "#0E0E10", "#141416"


def paint_jacket(c):
    ax = abs(c.x)
    if c.y < -0.1 and ax < 0.07:
        return TEE_BLACK                               # 열린 앞섶 사이 검정 티
    if c.y < -0.1 and ax < 0.085:
        return ZIP                                     # 양쪽 은색 지퍼
    if c.z > pz(1.2) and ax < 0.22:
        return JACKET_COLLAR                           # 넓은 깃
    if c.z < pz(0.9):
        return JACKET_HEM                              # 밑단 밴드
    return None


def jacket_seams():
    return [((0.07, 0, 0), (1, 0, 0)), ((-0.07, 0, 0), (1, 0, 0)), ((0.085, 0, 0), (1, 0, 0)), ((-0.085, 0, 0), (1, 0, 0)),
            ((0.22, 0, 0), (1, 0, 0)), ((-0.22, 0, 0), (1, 0, 0)), ((0, 0, pz(1.2)), (0, 0, 1)), ((0, 0, pz(0.9)), (0, 0, 1)),
            ((0, -0.1, 0), (0, 1, 0))]


def make_blocky_body(key, cfg, ao):
    """각진 블록 몸: 부위마다 상자 하나를 뼈에 붙임 (관절에서 블록째 꺾임)."""
    top, pants, skin, shoes = cfg["top"], cfg["pants"], cfg["skin"], cfg["shoes"]
    jensen = cfg.get("fashion") == "jensen"
    torso_paint, torso_s, top_rough = (paint_jacket, jacket_seams(), 0.38) if jensen else (paint_torso, torso_seams(), 0.75)
    parts = [
        (block(f"{key}_torso", (0, 0, 0.86), (0, 0, 1.30), 0.56, 0.32, top, taper=1.12, paint=torso_paint, seams=torso_s, rough=top_rough), "spine"),
        (block(f"{key}_neck", (0, 0, 1.26), (0, 0, 1.46), 0.15, 0.15, skin), "neck"),
        (block(f"{key}_hips", (0, 0, 0.72), (0, 0, 0.90), 0.52, 0.31, pants, paint=(paint_hips_silver if jensen else paint_hips), seams=[((0, 0, pz(0.83)), (0, 0, 1)), ((0.045, 0, 0), (1, 0, 0)), ((-0.045, 0, 0), (1, 0, 0)), ((0, -0.12, 0), (0, 1, 0))]), "hips"),
    ]
    for sd, sx in (("L", 1), ("R", -1)):
        parts += [
            (block(f"{key}_uarm{sd}", (0.36 * sx, 0, 1.27), (0.47 * sx, 0, 0.97), 0.17, 0.17, top, arm=True), f"upper_arm.{sd}"),
            (block(f"{key}_larm{sd}", (0.47 * sx, 0, 0.99), (0.525 * sx, -0.02, 0.71), 0.155, 0.155, top, paint=(None if jensen else paint_sleeve), seams=[((0, 0, pz(0.78, arm=True)), (0, 0, 1))], arm=True), f"lower_arm.{sd}"),
            (block(f"{key}_hand{sd}", (0.525 * sx, -0.02, 0.72), (0.54 * sx, -0.025, 0.58), 0.12, 0.09, skin, bevel=0.015, arm=True), f"lower_arm.{sd}"),
            (block(f"{key}_thigh{sd}", (0.155 * sx, 0, 0.84), (0.155 * sx, 0, 0.44), 0.22, 0.24, pants, paint=paint_leg(0.155 * sx), seams=[((0.155 * sx + 0.014, 0, 0), (1, 0, 0)), ((0.155 * sx - 0.014, 0, 0), (1, 0, 0)), ((0, -0.08, 0), (0, 1, 0))]), f"thigh.{sd}"),
            (block(f"{key}_shin{sd}", (0.155 * sx, 0, 0.47), (0.155 * sx, 0, 0.11), 0.2, 0.22, pants, paint=paint_leg(0.155 * sx), seams=[((0.155 * sx + 0.014, 0, 0), (1, 0, 0)), ((0.155 * sx - 0.014, 0, 0), (1, 0, 0)), ((0, -0.08, 0), (0, 1, 0))]), f"shin.{sd}"),
            (block(f"{key}_shoe{sd}", (0.155 * sx, -0.05, 0.0), (0.155 * sx, -0.05, 0.13), 0.2, 0.32, shoes, rough=0.5, paint=paint_shoe, seams=[((0, 0, 0.035), (0, 0, 1))]), f"shin.{sd}"),
        ]
    for ob, bone in parts:
        attach(ob, ao, bone)


def make_human(key, mats):
    cfg = HUMANS[key]
    PROP["on"] = bool(cfg.get("blocky"))
    ao = make_rig(key)
    head = make_head(key, cfg, mats)
    head.rotation_euler = (math.radians(90), 0, 0)   # 앞 +Z → -Y
    head.location = (0, 0, pz(1.67))
    bpy.context.view_layer.update()
    attach(head, ao, "head")
    if cfg.get("blocky"):
        make_blocky_body(key, cfg, ao)
    else:
        skin_to(make_body(key, cfg), ao)
    return ao


def test_pose(ao, on):
    """관절 시험: 오른손 흔들기 + 왼다리 앞으로 + 고개 갸웃."""
    pb = ao.pose.bones
    for b in pb:
        b.rotation_mode = "XYZ"
        b.rotation_euler = (0, 0, 0)
    if not on:
        return
    # 방향 규칙(뼈 좌표로 확인 2026-11-18): 팔 들기 = R은 +Z, L은 -Z / 다리 앞으로 = -X / 무릎 굽힘 = +X / 고개 갸웃 = Z, 끄덕 = X, 돌리기 = Y
    pb["upper_arm.R"].rotation_euler = (0, 0, math.radians(150))
    pb["lower_arm.R"].rotation_euler = (0, 0, math.radians(35))
    pb["thigh.L"].rotation_euler = (math.radians(-40), 0, 0)
    pb["shin.L"].rotation_euler = (math.radians(50), 0, 0)
    pb["head"].rotation_euler = (0, 0, math.radians(12))


def main():
    sc = B.setup_scene()
    mats = {"eye": B.material("eye", B.hex2rgb("#141414"), rough=0.25),
            "hl": B.material("hl", (1, 1, 1), rough=0.2, emit=1.5),
            "blush": B.material("blush", B.hex2rgb("#FF6F86"), rough=0.6, emit=0.25),
            "inner": B.material("inner", B.hex2rgb("#2A0A10"), rough=0.5),
            "sweat": B.material("sweat", B.hex2rgb("#9FD8FF"), rough=0.1, emit=0.3)}
    rigs = {}
    for i, key in enumerate(ONLY):
        ao = make_human(key, mats)
        ao.location = ((i - (len(ONLY) - 1) / 2) * 1.6, 0, 0)
        B.set_emotion(ao, key, "neutral", emo_table(key))
        rigs[key] = ao
    bpy.context.view_layer.update()

    for key, ao in rigs.items():
        loc = ao.location.copy()
        ao.location = (0, 0, 0)
        bpy.ops.object.select_all(action="DESELECT")
        ao.select_set(True)
        for c in ao.children_recursive:
            c.select_set(True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{key}.glb"), export_format="GLB", use_selection=True, export_vertex_color="ACTIVE")
        ao.location = loc

    for o in bpy.data.objects:  # 연속 렌더에서 그림자가 꼬여 까매지는 일 방지
        if o.type == "LIGHT":
            o.data.use_shadow = False
    n = len(ONLY)
    B.camera(sc, (0.6, -3.2 - 1.6 * n, 1.5), (0, 0, 1.1), lens=50, focus=(0, 0, 1.1), fstop=2.8)
    B.render(sc, os.path.join(OUT, "preview_humans.png"), 1920, 1080)
    home = {k: a.location.copy() for k, a in rigs.items()}
    for key, ao in rigs.items():
        for k, a in rigs.items():
            a.location = (0, 0, 0) if k == key else (home[k].x, 60, 0)
        bpy.context.view_layer.update()
        B.camera(sc, (1.5, -4.0, 1.5), (0, 0, 1.1), lens=50, focus=(0, -0.3, 1.2), fstop=2.0)
        B.render(sc, os.path.join(OUT, f"q34_{key}.png"), 1080, 1350)
        test_pose(ao, True)
        bpy.context.view_layer.update()
        B.render(sc, os.path.join(OUT, f"pose_{key}.png"), 1080, 1350)
        test_pose(ao, False)
        if "--sheet" in argv:
            d = os.path.join(OUT, "sheet")
            os.makedirs(d, exist_ok=True)
            B.camera(sc, (0, -2.4, 1.85), (0, 0, 1.78), lens=50, focus=(0, -0.4, 1.78), fstop=1.6)
            for emo in B.EMOTIONS:
                B.set_emotion(ao, key, emo, emo_table(key))
                B.render(sc, os.path.join(d, f"{key}_{emo}.png"), 640, 640)
            B.set_emotion(ao, key, "neutral", emo_table(key))
        bpy.context.view_layer.update()
    for k, a in rigs.items():
        a.location = home[k]


if __name__ == "__main__":
    main()
