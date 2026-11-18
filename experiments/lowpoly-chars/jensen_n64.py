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


def hair_relief(ob):
    """머리 덩어리에 살짝 결 (운영자 2026-11-18 "머리가 너무 매끈한 덩어리, 살짝 보완"): 앞→뒤로 넘긴 다발 굴곡 + 조금 부풀림.
    머리 영역만(정수리·뒤통수·귀 위 옆머리, z 1.55 위), 크기 최대 2.2cm로 작게."""
    me = ob.data
    me.update()
    cl = lambda t: max(0.0, min(1.0, t))
    for v in me.vertices:
        co = v.co
        dx = co.x - FACE_X
        w = max(cl((co.z - 1.84) / 0.06), cl((co.z - 1.55) / 0.08) * cl((co.y + 0.1) / 0.1),
                cl((co.z - 1.62) / 0.06) * cl((abs(dx) - 0.3) / 0.05) * cl((co.y + 0.35) / 0.08))
        if w <= 0:
            continue
        ang = math.atan2(dx, -co.y)
        ridge = max(0.0, math.sin(ang * 12 + co.y * 4.0)) ** 1.5
        co += v.normal * (w * (0.01 + 0.012 * ridge))
    me.update()


def build_shape():
    L.SRC = os.path.join(REF, "jensen_trellis.glb")
    src_bm, _ = L.load_src()
    L.normalize(src_bm)
    me = bpy.data.meshes.new("jensen_n64")
    src_bm.to_mesh(me)
    ob = B.link(bpy.data.objects.new("jensen_n64", me))
    # 코를 입체로 키움 (넓고 둥근 코끝 + 큰 콧볼, 운영자 2026-11-18 "코 키우고")
    from mathutils import Matrix
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for c, r in (((FACE_X, -0.565, 1.425), (0.078, 0.068, 0.058)),      # 코끝 (아래로 덜 튀어나오게)
                 ((FACE_X - 0.072, -0.5, 1.395), (0.05, 0.048, 0.038)),
                 ((FACE_X + 0.072, -0.5, 1.395), (0.05, 0.048, 0.038)),
                 ((FACE_X, -0.515, 1.51), (0.04, 0.05, 0.1))):
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0,
                                  matrix=Matrix.Translation(Vector(c)) @ Matrix.Diagonal((*r, 1)))
    bm.to_mesh(ob.data)
    bm.free()
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
            elif (n.z < -0.2 and 1.30 < c.z < 1.43 and dx < 0.16) or (n.z < -0.3 and c.z < 1.17) or (n.y > -0.3 and dx > 0.16):   # 코 밑·턱 밑·옆면만  # 아래를 향한 면(코 밑·턱 밑)·옆을 향한 면: 정면 사진이 늘어나 얼룩지므로 피부 견본
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


def photo_bounds(py):
    """사진에서 얼굴 피부(귀 포함)의 가로 범위 (가장자리에서 12px 안쪽)."""
    import bisect
    ys = [r[0] for r in PHOTO_OUTLINE]
    i = min(max(bisect.bisect_left(ys, py), 1), len(ys) - 1)
    (y0, l0, r0), (y1, l1, r1) = PHOTO_OUTLINE[i - 1], PHOTO_OUTLINE[i]
    t = min(max((py - y0) / (y1 - y0), 0), 1)
    l, r = l0 + (l1 - l0) * t + 12, r0 + (r1 - r0) * t - 12
    if 590 < py < 760:          # 귀 높이는 귀까지
        l, r = min(l, 365), max(r, 1010)
    return l, r


def to_model(px, py):
    return FACE_X + (px - EYE_PX[0]) / SX, EYE_Z - (py - EYE_PX[1]) / SZ


GLASS_W = 0.88


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
        x = FACE_X + (x - FACE_X) * GLASS_W        # 옆 폭만 좁힘 (운영자 2026-11-18 "안경 옆 폭이 너무 넓다")
        return (x, y0 + 0.16 * ((x - FACE_X) / 0.45) ** 2 + extra, z)
    black = B.material("glasses_frame", B.hex2rgb("#18181A"), rough=0.3)
    wire = B.material("glasses_wire", B.hex2rgb("#B9BDC3"), rough=0.25)
    parts = []

    def tube(name, pts, r, m):
        o = B.arc_tube(name, pts, r, ring=6)
        o.data.materials.append(m)
        B.shade_flat(o)
        parts.append(o)
    # 사진 렌즈 윤곽을 그대로 딴 점 (왼쪽 렌즈; 오른쪽은 x' = 1380 - x 거울). 운영자 2026-11-18 "안경 비율도 좀 달라"
    # 위테: 거의 일자, 바깥 끝만 살짝 내려감 / 아래: 바깥에서 둥글게 내려와 가운데가 가장 낮고, 코 쪽에서 올라감 (가로로 넓고 납작)
    TOP = [(416, 574), (438, 561), (550, 557), (660, 560), (672, 568)]
    BOT = [(416, 574), (423, 618), (448, 658), (500, 680), (560, 686), (620, 674), (654, 646), (667, 612), (672, 568)]
    for sd, mir in (("L", lambda x: x), ("R", lambda x: 1380 - x)):
        tube(f"glasses_top_{sd}", [P(mir(x), y) for x, y in TOP], 0.015, black)    # 굵은 윗테
        tube(f"glasses_wire_{sd}", [P(mir(x), y) for x, y in BOT], 0.0045, wire)   # 가는 아랫선
        x_ear = FACE_X + (-0.43 if sd == "L" else 0.43)
        ox, oy, oz = P(mir(416), 572)
        tube(f"glasses_arm_{sd}", [(ox, oy, oz), (x_ear * 0.98 + FACE_X * 0.02, oy + 0.18, oz + 0.005), (x_ear, 0.08, oz - 0.02)], 0.009, black)
    tube("glasses_bridge", [P(672, 567), P(690, 558, -0.01), P(708, 567)], 0.009, black)
    for o in parts:
        o.parent = ob
    return parts


HEAD_W, JAW_W = 0.88, 0.84   # 머리 가로 비율 (운영자 2026-11-18 "정면이 너무 넓다"): 위쪽 12%, 볼·턱 16% 좁힘


def x_scale(z):
    """높이별 가로 배율: 어깨(z<1.0)=1 → 목에서 서서히 → 볼·턱(1.13~1.35)=JAW_W → 눈 위(1.5~)=HEAD_W."""
    sm = lambda t: t * t * (3 - 2 * t)
    if z < 1.0:
        return 1.0
    if z < 1.13:
        return 1.0 + (JAW_W - 1.0) * sm((z - 1.0) / 0.13)
    if z < 1.35:
        return JAW_W
    if z < 1.5:
        return JAW_W + (HEAD_W - JAW_W) * sm((z - 1.35) / 0.15)
    return HEAD_W


# 사진 얼굴 윤곽 (귀 제외, 사진 격자에서 읽음): 사진 y → (왼쪽 끝 x, 오른쪽 끝 x). 운영자 2026-11-18 "얼굴 사진에 맞게 입체 모형도 따라가자"
PHOTO_OUTLINE = [(420, 470, 905), (500, 440, 930), (600, 420, 945), (700, 425, 950), (760, 440, 945),
                 (845, 465, 915), (900, 500, 890), (950, 545, 855), (1000, 610, 790), (1020, 650, 740)]


def fit_to_photo(ob):
    """높이마다 모형 앞쪽 얼굴 폭을 사진 윤곽 폭에 맞춤 (단면 전체를 같은 배율로). 질감 투영 전에 해서 사진과 모형 가장자리가 겹침.
    이마선 위(머리)는 맨 위 배율 유지, 턱 밑~목은 원래 폭으로 서서히."""
    import bisect
    me = ob.data
    pts = sorted((EYE_Z - (py - EYE_PX[1]) / SZ, (r - l) / 2 / SX) for py, l, r in PHOTO_OUTLINE)   # (z, 반너비) z 오름차순
    zs = [p[0] for p in pts]

    def photo_hw(z):
        i = bisect.bisect_left(zs, z)
        if i <= 0:
            return pts[0][1]
        if i >= len(pts):
            return pts[-1][1]
        (z0, w0), (z1, w1) = pts[i - 1], pts[i]
        return w0 + (w1 - w0) * (z - z0) / (z1 - z0)

    def mesh_hw(z):
        ws = [abs(v.co.x - FACE_X) for v in me.vertices if abs(v.co.z - z) < 0.02 and v.co.y < 0.0]   # 볼 옆까지 (앞쪽 절반 전체)
        return max(ws) if ws else None
    zlo, zhi = zs[0], zs[-1]
    table = []
    for k in range(40):
        z = zlo + (zhi - zlo) * k / 39
        mw = mesh_hw(z)
        if mw:
            table.append((z, min(1.05, max(0.55, photo_hw(z) / mw))))   # 넓히는 건 최대 5%
    # 부드럽게 (이웃 평균)
    sm = [(table[i][0], sum(t[1] for t in table[max(0, i - 2):i + 3]) / len(table[max(0, i - 2):i + 3])) for i in range(len(table))]
    tz = [t[0] for t in sm]

    def factor(z):
        if z >= tz[-1]:
            return sm[-1][1]
        if z <= tz[0]:
            f0 = sm[0][1]
            t = min(1.0, max(0.0, (tz[0] - z) / 0.1))     # 턱 밑 0.1 동안 원래 폭으로
            return f0 + (1 - f0) * t * t * (3 - 2 * t)
        i = bisect.bisect_left(tz, z)
        (z0, f0), (z1, f1) = sm[i - 1], sm[i]
        return f0 + (f1 - f0) * (z - z0) / (z1 - z0)
    for v in me.vertices:
        v.co.x = FACE_X + (v.co.x - FACE_X) * factor(v.co.z)
    me.update()
    print("fit", " ".join(f"{z:.2f}:{f:.2f}" for z, f in sm[::6]))


def jaw_taper(co):
    """턱선 (운영자 2026-11-18 "턱 각도도 달라"): 사진은 광대 폭 대비 입 0.84 → 입·턱 사이 0.54로 좁아지는데 모델은 0.74.
    입 아래(z 1.30)부터 턱끝(1.06)까지 얼굴 앞부분만 30%까지 더 좁혀 턱선이 안쪽으로 비스듬히 모이게. 어깨·뒷목은 그대로."""
    sm = lambda t: t * t * (3 - 2 * t)
    if co.y > 0.05 or abs(co.x - FACE_X) > 0.42 or co.z > 1.30 or co.z < 0.96:
        return 1.0
    if co.z >= 1.06:
        return 1.0 - 0.3 * sm((1.30 - co.z) / 0.24)
    return 0.7 + 0.3 * sm((1.06 - co.z) / 0.10)      # 턱 밑 → 목: 다시 원래 폭으로


def narrow_head(ob, glasses):
    """질감(UV)·안경을 입힌 뒤에 좁혀서 그린 눈·코·입·안경도 같이 좁아짐."""
    for v in ob.data.vertices:
        v.co.x = FACE_X + (v.co.x - FACE_X) * x_scale(v.co.z) * jaw_taper(v.co)
    ob.data.update()
    for g in glasses:
        for v in g.data.vertices:
            v.co.x = FACE_X + (v.co.x - FACE_X) * x_scale(v.co.z)
        g.data.update()


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
    d = bpy.data.lights.new("under", "AREA")                 # 정면 아래 약한 보조광 (코 밑·턱 밑 그늘 누그러뜨림, 미리보기용)
    d.energy, d.size = 80, 3
    ul = B.link(bpy.data.objects.new("under", d))
    ul.location = (0, -3.5, 0.6)
    ul.rotation_euler = (Vector((0, 0, 1.5)) - Vector(ul.location)).to_track_quat("-Z", "Y").to_euler()
    ob = build_shape()
    photo = args[args.index("--photo") + 1] if "--photo" in args else "jensen_mixed.png"   # 그린 얼굴 + 사진 50% (blend_photo.py)   # 게임 그림처럼 단순화한 질감 (toon_texture.py)
    src = bpy.data.images.load(os.path.join(REF, photo))
    W, H = src.size
    fit_to_photo(ob)          # 사진 윤곽에 모형 폭 맞춤 (예전 눈대중 좁히기 narrow_head 대신)
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
