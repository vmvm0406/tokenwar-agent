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
HUMANS = {
    "jensen": dict(
        skin="#D7A07A", hair="#7E7E7A", top="#1A1A1C", top_rough=0.32, tee="#34343A",
        pants="#25272E", shoes="#111111", sleeves="top",
        # 얼굴 (운영자 2026-11-18 "얼굴형 더 잘"): 각지고 넓은 턱, 웃는 볼, 큰 코, 가는 눈, 짙은 눈썹, 이 보이는 큰 웃음
        head_shapes=[("e", (0, 0.02, -0.02), (0.40, 0.38, 0.39)),          # 윗머리
                     ("e", (0, -0.16, 0.04), (0.40, 0.21, 0.34)),          # 넓고 각진 턱
                     ("e", (0.21, -0.11, 0.27), (0.14, 0.11, 0.10)),       # 웃는 볼
                     ("e", (-0.21, -0.11, 0.27), (0.14, 0.11, 0.10)),
                     ("e", (0, -0.06, 0.40), (0.07, 0.06, 0.055))],        # 코
        hair_main=((0, 0.15, -0.13), (0.43, 0.40, 0.40)),       # 앞머리 라인을 올리고 뒤로 (이마가 넓게 보이게)       # 옆은 짧고 뒤로 넘긴 은회색 머리
        # 참고: 엔비디아 공식 'Toy Jensen' — 옆 가르마로 한쪽에 볼륨 있게 넘긴 은회색 머리(짙은 줄무늬)
        hair_extra=[((0.05, 0.42, 0.04), (0.34, 0.13, 0.25)),   # 위로 세워 뒤로 넘긴 볼륨 (앞으로 내려오지 않게)
                    ((0.14, 0.40, -0.14), (0.27, 0.13, 0.26)), ((-0.18, 0.34, -0.12), (0.2, 0.11, 0.24))],
        hair_streak="#55555A",
        brow="#3B3936", glasses="#1C1C1E",   # 안경 (운영자 2026-11-18)
        face=dict(eye_s=0.064, eye_aspect=0.62, eye_dx=0.15, mouth_w=0.075, mouth_dy=-0.20, brows=True, grin=True),
        emo={"neutral": ["eye_open", "brow_neutral", "mouth_grin"],
             "happy": ["eye_happy", "brow_neutral", "mouth_grin", "blush"]},
        collar=True),
    "man": dict(
        skin="#E2AE86", hair="#2B211C", top="#7FA6D4", top_rough=0.7, tee=None,
        pants="#3A3F4A", shoes="#5B3B29", sleeves="top",
        hair_main=((0, 0.12, -0.05), (0.46, 0.44, 0.44)),
        hair_extra=[((0, 0.31, 0.24), (0.36, 0.11, 0.16)), ((0.2, 0.28, 0.2), (0.16, 0.1, 0.14))],  # 앞머리
        brow="#241C18", face=dict(brows=True),
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


def capsule_into(bm, a, b, r):
    a, b = Vector(a), Vector(b)
    n = max(2, int((b - a).length / (r * 0.45)) + 1)
    for k in range(n):
        ellipsoid_into(bm, a.lerp(b, k / (n - 1)), (r, r, r))


def blob(name, shapes, faces, color, rough=0.68, voxel=0.018, smooth=4, jitter=0.07, color_fn=None):
    """shapes: [('e', 중심, 반지름3) | ('c', a, b, r)] → 합쳐 리메시 → 매끈 → 면 줄이기 → 평면 셰이딩 + 면 색."""
    bm = bmesh.new()
    for s in shapes:
        if s[0] == "e":
            ellipsoid_into(bm, s[1], s[2])
        else:
            capsule_into(bm, s[1], s[2], s[3])
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


def make_head(key, cfg, mats):
    """머리는 로고 캐릭터와 같은 좌표(앞 +Z, 위 +Y)로 만들고 얼굴 부품을 붙인 뒤 세운다."""
    grp = B.link(bpy.data.objects.new(f"{key}_headgrp", None))
    skin = cfg.get("head_shapes") or [("e", (0, 0, 0), (0.42, 0.40, 0.40)),   # 머리
                                      ("e", (0, -0.07, 0.40), (0.05, 0.045, 0.04))]  # 코
    skin = skin + [("e", (0.41, -0.02, 0), (0.06, 0.10, 0.07)),       # 귀
                   ("e", (-0.41, -0.02, 0), (0.06, 0.10, 0.07))]
    head = blob(f"{key}_head", skin, 700, cfg["skin"], rough=0.72, voxel=0.014)
    head.parent = grp
    hs = [("e", *cfg["hair_main"])] + [("e", *h) for h in cfg["hair_extra"]]
    hfn = None
    if cfg.get("hair_streak"):  # 앞→뒤로 흐르는 짙은 줄무늬
        hc, sc_ = B.hex2rgb(cfg["hair"]), B.hex2rgb(cfg["hair_streak"])
        hfn = lambda c: sc_ if math.sin(c.x * 26 + c.z * 3 + c.y * 4) > 0.45 else hc
    hair = blob(f"{key}_hair", hs, 520, cfg["hair"], rough=0.8, voxel=0.016, smooth=3, jitter=0.08, color_fn=hfn)
    hair.parent = grp
    bpy.context.view_layer.update()
    m2 = {**mats, "brow": B.material(f"{key}_brow", B.hex2rgb(cfg.get("brow", "#222222")), rough=0.8),
          "teeth": B.material("teeth", B.hex2rgb("#F4F1EA"), rough=0.35)}
    fc = {**FACE, **cfg.get("face", {})}
    B.add_face(key, head, grp, mats=m2, **fc)
    if cfg.get("glasses"):
        add_glasses(key, fc, cfg["glasses"])
    return grp


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
              ("c", (0.35 * sx, 0, 1.22), (0.47 * sx, 0, 0.98), 0.083),             # 위팔
              ("c", (0.47 * sx, 0, 0.98), (0.525 * sx, -0.02, 0.71), 0.076),        # 아래팔
              ("e", (0.535 * sx, -0.025, 0.645), (0.066, 0.058, 0.078)),            # 손
              ("c", (0.16 * sx, 0, 0.84), (0.16 * sx, 0, 0.45), 0.118),             # 허벅지
              ("c", (0.16 * sx, 0, 0.45), (0.16 * sx, 0, 0.12), 0.102),             # 종아리
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
    return blob(f"{key}_body", S, 2600, cfg["top"], cfg["top_rough"], voxel=0.016, smooth=8, color_fn=color)


def skin_to(ob, ao):
    """뼈에 자동 가중치 (관절이 자연스럽게 휨). root 뼈는 변형에서 뺌."""
    ao.data.bones["root"].use_deform = False
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    ao.select_set(True)
    bpy.context.view_layer.objects.active = ao
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")


def emo_table(key):
    """캐릭터별 표정 덮어쓰기 (젠슨 황: 평소에도 이 보이는 웃음)."""
    return {**B.EMOTIONS, **HUMANS[key].get("emo", {})}


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
        eb.head, eb.tail = Vector(h), Vector(t)
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


def make_human(key, mats):
    cfg = HUMANS[key]
    ao = make_rig(key)
    head = make_head(key, cfg, mats)
    head.rotation_euler = (math.radians(90), 0, 0)   # 앞 +Z → -Y
    head.location = (0, 0, 1.67)
    bpy.context.view_layer.update()
    attach(head, ao, "head")
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
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{key}.glb"), export_format="GLB", use_selection=True)
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
