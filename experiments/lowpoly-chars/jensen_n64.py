"""젠슨 황 — 각진 로우폴리 + 사진 질감 (90년대 게임기 화풍, 운영자 2026-11-18 선택).
참고: 운영자가 보여 준 릴스 화풍(면 몇백 개짜리 각진 머리에 실제 얼굴 사진을 질감으로). 게임 캐릭터·화면은 쓰지 않음.

1) 형태: 참고 3D(ref/jensen_trellis.glb)를 굵게 뭉개고 좌우 대칭 → 면 몇백 개로 줄임(각진 실루엣, 부드러운 셰이딩).
2) 질감: 공개 사진(ref/jensen_photo_bust.jpg = Wikimedia Commons "Jensen huang stanford 2026-04-30 011", Anders Eidesvik, CC BY 4.0)을
   정면에서 투영. 기준점: 사진 눈(580,600)·(785,610), 입선 y 845 ↔ 모델 눈 x=FACE_X±0.165·z 1.60, 입 z 1.255.
3) 뒤를 향한 면: 머리 = 사진의 머리카락 띠, 옷 = 사진의 재킷 띠에서 가져옴. 질감은 원본 해상도 (--tex N으로 줄일 수 있음).

실행: & "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe" --background --python experiments/lowpoly-chars/jensen_n64.py -- [--faces 700] [--tex 256]
결과: out/jensen_n64.glb, out/jensen_n64_front.png, out/jensen_n64_q34.png, out/jensen_n64_tex.png
"""
import bpy, bmesh, os, sys, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build as B              # noqa: E402
import lowpoly_from_glb as L   # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FACES = int(args[args.index("--faces") + 1]) if "--faces" in args else 1200   # 좀 더 잘게, 각진 느낌은 유지
TEX = int(args[args.index("--tex") + 1]) if "--tex" in args else 0   # 0 = 원본 해상도 그대로 (운영자 2026-11-18 "해상도까지 낮출 필요는 없지")
REF = os.path.join(HERE, "ref")
SMOOTH = "--smooth" in args
FACE_X = -0.10
# 모델 좌표 → 사진 픽셀 (사진 1459x1740)
EYE_PX, EYE_Z = (682.5, 605.0), 1.60
SX = 205 / 0.33                     # 가로: 사진 눈 사이 205px = 모델 0.33
SZ = (845 - 605) / (1.60 - 1.255)   # 세로: 눈→입선 240px = 모델 0.345
HAIR_V, JACKET_V = 360, 1500        # 뒤를 향한 면이 가져올 사진 띠 (머리카락 / 재킷)


def to_px(x, z):
    return EYE_PX[0] + (x - FACE_X) * SX, EYE_PX[1] - (z - EYE_Z) * SZ


def build_shape():
    L.SRC = os.path.join(REF, "jensen_trellis.glb")
    src_bm, _ = L.load_src()
    L.normalize(src_bm)
    me = bpy.data.meshes.new("jensen_n64")
    src_bm.to_mesh(me)
    ob = B.link(bpy.data.objects.new("jensen_n64", me))
    B.remesh(ob, 0.03)
    m = ob.modifiers.new("sm", "SMOOTH")
    m.factor, m.iterations = 0.6, 8
    B.apply_mod(ob, m)
    B.remesh(ob, 0.014)
    for v in ob.data.vertices:
        v.co.x -= FACE_X
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction="X", dist=0.002)
    bm.to_mesh(ob.data)
    bm.free()
    n = len(ob.data.polygons) * 2
    dm = ob.modifiers.new("dec", "DECIMATE")
    dm.decimate_type, dm.ratio, dm.use_symmetry, dm.symmetry_axis = "COLLAPSE", min(1.0, FACES / n), True, "X"
    dm.use_collapse_triangulate = True
    B.apply_mod(ob, dm)
    for v in ob.data.vertices:
        v.co.x += FACE_X
    ob.data.update()
    for p in ob.data.polygons:
        p.use_smooth = SMOOTH     # 기본 평면 셰이딩: 면이 보이는 각진 로우폴리 (운영자 2026-11-18 "각진 느낌 살리기")
    return ob


def project_uv(ob, w, h):
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        n, c = p.normal, p.center
        # 정면 사진에 안 찍힌 면(옆·뒤·정수리)은 사진 배경이 묻으므로 같은 재질 띠에서 가져옴
        if c.z > 1.13:
            dx = abs(c.x - FACE_X)
            if n.y > 0.25 or (n.z > 0.6 and c.z > 1.85) or (n.y > -0.4 and c.z > 1.5 and (dx > 0.28 or c.y > -0.3)):
                kind = "hair"   # 뒤통수·정수리·옆머리만 (콧등은 정면 사진 그대로)
            elif n.y > -0.4 and abs(c.x - FACE_X) > 0.3:   # 얼굴 가장자리(귀 쪽)만. 코 옆면은 정면 사진 그대로
                kind = "skin"
            else:
                kind = "front"
        else:
            kind = "jacket" if n.y > 0.25 else "front"
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            px, py = to_px(co.x, co.z)
            if kind == "hair":      # 머리카락 견본(20~310)을 위에서 내려다본 좌표로: 가닥이 앞→뒤로 흐름, 이음새 없음
                px = 30 + min(max((co.x - FACE_X + 0.6) / 1.2, 0), 1) * 270
                py = 30 + min(max((co.y + 0.6) / 1.2, 0), 1) * 270
            elif kind == "skin":    # 피부 견본(20~310, 345~395)을 옆에서 본 좌표로
                px = 30 + min(max((co.y + 0.6) / 1.2, 0), 1) * 270
                py = 348 + min(max((2.0 - co.z) / 0.9, 0), 1) * 45
            elif kind == "jacket":
                px, py = 150 + (px % 400), JACKET_V + (py % 120)
            uv.data[li].uv = (min(max(px / w, 0), 1), 1 - min(max(py / h, 0), 1))


def to_model(px, py):
    return FACE_X + (px - EYE_PX[0]) / SX, EYE_Z - (py - EYE_PX[1]) / SZ


def add_glasses3d(ob):
    """입체 하프림 안경 (운영자 2026-11-18 "얼굴 그림에선 지우고 같은 위치에 입체로").
    사진 위치: 렌즈 x 425~668 / 712~958, 위테 y 560, 아래 y 678. 얼굴 곡면을 따라 바깥쪽이 뒤로 살짝 휨."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    eye_y = []
    for px in (580, 785):
        x, z = to_model(px, 605)
        hit = bvh.ray_cast(Vector((x, -3, z)), Vector((0, 1, 0)))
        eye_y.append(hit[0].y if hit[0] else -0.47)
    y0 = min(eye_y) - 0.06                     # 렌즈 면: 눈보다 조금 앞

    def P(px, py, extra=0.0):
        x, z = to_model(px, py)
        return (x, y0 + 0.16 * ((x - FACE_X) / 0.45) ** 2 + extra, z)
    black = B.material("glasses_frame", B.hex2rgb("#18181A"), rough=0.3)
    wire = B.material("glasses_wire", B.hex2rgb("#B9BDC3"), rough=0.25)
    parts = []

    def tube(name, pts, r, m):
        o = B.arc_tube(name, pts, r, ring=6)
        o.data.materials.append(m)
        B.shade_flat(o)
        parts.append(o)
    for sd, (l0, l1) in (("L", (425, 668)), ("R", (712, 958))):
        top = [P(l0, 574), P(l0 + 22, 560), P((l0 + l1) / 2, 558), P(l1 - 22, 560), P(l1, 574)]
        tube(f"glasses_top_{sd}", top, 0.016, black)                          # 굵은 윗테
        bot = [P(l0, 574), P(l0 + 6, 640), P(l0 + 40, 678), P((l0 + l1) / 2, 682), P(l1 - 40, 678), P(l1 - 6, 640), P(l1, 574)]
        tube(f"glasses_wire_{sd}", bot, 0.0045, wire)                         # 가는 아랫선
        outer = l0 if sd == "L" else l1
        x_ear = FACE_X + (-0.43 if sd == "L" else 0.43)
        ox, oy, oz = P(outer, 570)
        tube(f"glasses_arm_{sd}", [(ox, oy, oz), (x_ear * 0.98 + FACE_X * 0.02, oy + 0.18, oz + 0.005), (x_ear, 0.08, oz - 0.02)], 0.009, black)
    tube("glasses_bridge", [P(668, 568), P(690, 556, -0.01), P(712, 568)], 0.009, black)
    for o in parts:
        o.parent = ob
    return parts


def material(img):
    m = bpy.data.materials.new("jensen_n64_mat")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def main():
    sc = B.setup_scene()
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.data.use_shadow = False
            if o.name == "key":
                o.data.energy = 800
    ob = build_shape()
    photo = args[args.index("--photo") + 1] if "--photo" in args else "jensen_painted.png"   # 게임 그림처럼 단순화한 질감 (toon_texture.py)
    src = bpy.data.images.load(os.path.join(REF, photo))
    W, H = src.size
    project_uv(ob, W, H)
    img = src
    if TEX:   # 해상도를 줄일 때만 (경로를 바꾸면 Blender가 그 경로의 예전 파일을 다시 불러오므로 먼저 지움)
        p = os.path.join(B.OUT, "jensen_n64_tex.png")
        if os.path.exists(p):
            os.remove(p)
        img = src.copy()
        img.scale(TEX, int(TEX * H / W))
        img.filepath_raw = p
        img.file_format = "PNG"
        img.save()
    ob.data.materials.append(material(img))
    glasses = add_glasses3d(ob)
    print("faces", len(ob.data.polygons), "TEX", TEX, "photo", photo, "img", tuple(img.size))
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    for g in glasses:
        g.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(B.OUT, "jensen_n64.glb"), export_format="GLB", use_selection=True)
    fz = 1.55
    B.camera(sc, (0.0, -4.0, fz + 0.1), (FACE_X, 0, fz - 0.05), lens=50, focus=(FACE_X, -0.5, fz), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, "jensen_n64_front.png"), 1080, 1350)
    B.camera(sc, (2.3, -3.3, fz + 0.2), (FACE_X, 0, fz - 0.1), lens=50, focus=(FACE_X, -0.4, fz), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, "jensen_n64_q34.png"), 1080, 1350)


main()
