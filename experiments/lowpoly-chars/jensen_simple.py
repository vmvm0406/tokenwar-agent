"""젠슨 황 — 스캔은 형태 참고로만, 단순화해서 새로 만들기 (운영자 2026-11-18
"이 모델을 레퍼런스로 단순화해서 다시, 원본 로우폴리가 남아 부자연스러움, 아예 다 만들자").

1) 참고 형태: 공개 사진 → TRELLIS 3D(trellis.glb)를 크게 뭉갬(굵은 복셀 + 매끈하게) → 얼굴형·머리 덩어리·코·귀만 남음.
   원래 입술·눈 굴곡 같은 잔흔적은 사라짐.
2) 큼직한 면으로 다시 깎음(Decimate) → 평면 셰이딩.
3) 색은 영역별 단색: 참고 질감에서 머리(회색)·피부·옷을 나눈 뒤 이웃 다수결로 다듬고 팔레트 색으로 칠함 (질감 얼룩 없음).
4) 자연스러운 입술(입 자리만 면을 잘게), 네모 눈, 하프림 안경, 말할 때 입 — jensen_real.py 부품 재사용. 머리 1.35배 캐릭터 비율.

실행: & "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe" --background --python experiments/lowpoly-chars/jensen_simple.py -- <trellis.glb> [--quick] [--faces 1800]
결과: out/jensen.glb, out/jensen_front.png, out/jensen_q34.png
"""
import bpy, bmesh, os, sys, math, colorsys, random
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build as B          # noqa: E402
import lowpoly_from_glb as L   # noqa: E402
import jensen_real as J    # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
SRC = args[0]
FACES = int(args[args.index("--faces") + 1]) if "--faces" in args else 3500   # 조금 더 세밀하게, 잘게는 말고
PAL = dict(skin="#D9A27F", hair="#A3A39E", jacket="#1B1B1E", tee="#2B2B2F")

# 젠슨 황 얼굴 비율 (2026-11-18, 정면 사진 Stanford 2026-04-30 011을 격자로 잼). 단위: 눈 사이 거리(io) = 0.33.
# 눈 아래로: 코끝 0.66io, 콧볼 밑 0.76io, 입선 1.17io, 턱 1.93io / 눈 위로: 눈썹 0.29io, 이마선 1.15io
# 폭: 눈 0.34io, 콧볼 0.66io, 입 0.83io, 광대 2.6io, 안경알 한쪽 1.17io(넓음, 위테만 굵음)
IO = 0.33
J.EYE_DX = IO / 2
# 높이는 참고 3D의 옆얼굴 윤곽에서 잰 실제 위치 (콧등 가장 들어간 곳 = 눈 높이 1.60, 코끝 1.425, 입 1.255, 턱 1.06, 이마선 1.93)
J.EYE_Z, J.MOUTH_Z = 1.60, 1.255
J.GLASS_RX, J.GLASS_RZ = 0.58 * IO, 0.28 * IO
J.GLASS_DZ, J.GLASS_OUT = -0.035 * IO, 0.1 * IO
NOSE_TIP_Z, NOSTRIL_Z = 1.425, 1.39
MOUTH_HW = 0.83 * IO / 2                   # 입 반너비 0.137
NOSE_HW = 0.66 * IO / 2                    # 콧볼 반너비 0.109


def lin2srgb(c):
    return [12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055 for x in c]


def build_shape(src_bm):
    me = bpy.data.meshes.new("jensen_src")
    src_bm.to_mesh(me)
    ob = B.link(bpy.data.objects.new("jensen_body", me.copy()))
    # 젠슨 황 코: 넓고 끝이 둥근 코 + 큰 콧방울 (단순화하면 뾰족해져서 다시 빚음, 운영자 2026-11-18 "눈코입 모양 살리기")
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    from mathutils import Matrix
    for c, r in (((J.FACE_X, -0.565, NOSE_TIP_Z), (0.072, 0.066, 0.062)),                              # 코끝(둥글게)
                 ((J.FACE_X - NOSE_HW + 0.045, -0.5, NOSTRIL_Z), (0.05, 0.05, 0.042)),                # 콧방울 (콧볼 폭 0.66io)
                 ((J.FACE_X + NOSE_HW - 0.045, -0.5, NOSTRIL_Z), (0.05, 0.05, 0.042)),
                 ((J.FACE_X, -0.505, (NOSE_TIP_Z + J.EYE_Z) / 2), (0.036, 0.045, 0.1))):            # 좁은 콧대
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0,
                                  matrix=Matrix.Translation(Vector(c)) @ Matrix.Diagonal((*r, 1)))
    bm.to_mesh(ob.data)
    bm.free()
    B.remesh(ob, 0.022)                      # 잔 굴곡은 지우되 전보다 덜 뭉갬
    m = ob.modifiers.new("sm", "SMOOTH")
    m.factor, m.iterations = 0.6, 7
    B.apply_mod(ob, m)
    B.remesh(ob, 0.011)
    # 좌우 대칭 (운영자 2026-11-18 "얼굴 대칭은 맞게"): 얼굴 가운데(코)를 x=0으로 옮겨 +x 반을 거울 복사 → 대칭 Decimate
    me = ob.data
    for v in me.vertices:
        v.co.x -= J.FACE_X
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:], direction="X", dist=0.002)
    bm.to_mesh(me)
    bm.free()
    n = len(me.polygons) * 2
    dm = ob.modifiers.new("dec", "DECIMATE")
    dm.decimate_type, dm.ratio, dm.use_symmetry, dm.symmetry_axis = "COLLAPSE", min(1.0, FACES / max(n, 1)), True, "X"
    dm.use_collapse_triangulate = True
    B.apply_mod(ob, dm)
    for v in ob.data.vertices:
        v.co.x += J.FACE_X
    ob.data.update()
    B.shade_flat(ob)
    return ob


def classify(ob, src_bm, img):
    """면마다 참고 질감 색 → 머리/피부/옷 → 이웃 다수결 3번 → 팔레트 단색."""
    uv = src_bm.loops.layers.uv.active
    bvh = BVHTree.FromBMesh(src_bm)
    src_bm.faces.ensure_lookup_table()
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    me = ob.data
    lab = {}
    for p in me.polygons:
        c = p.center
        loc, _, idx, _ = bvh.find_nearest(c)
        f = src_bm.faces[idx]
        u = barycentric_transform(loc, *[l.vert.co for l in f.loops], *[Vector((*l[uv].uv, 0)) for l in f.loops])
        r, g, b = px[int((u.y % 1) * (h - 1)), int((u.x % 1) * (w - 1)), :3]   # 8비트 질감 = sRGB 값
        hh, s, v = colorsys.rgb_to_hsv(r, g, b)
        dxf = c.x - J.FACE_X
        hairline = 1.93 - 0.05 * math.exp(-((dxf - 0.12) / 0.2) ** 2)    # 이마선: 사진상 눈~정수리의 49% 지점, 넓은 이마
        if c.z < 1.0 or (c.z < 1.13 and abs(dxf) > 0.24):
            lab[p.index] = "jacket"
        elif c.z > hairline:                                  # 이마선 위 = 머리
            lab[p.index] = "hair"
        elif c.z > 1.5 and c.y > -0.12:                       # 뒤통수
            lab[p.index] = "hair"
        elif c.z > 1.6 and abs(dxf) > 0.3 and c.y > -0.38:   # 귀 위 옆머리 (관자놀이까지)
            lab[p.index] = "hair"
        else:
            lab[p.index] = "skin"
    # 이웃 다수결 (한두 면짜리 얼룩 없애기)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    for _ in range(3):
        new = dict(lab)
        for f in bm.faces:
            nb = [lab[o.index] for e in f.edges for o in e.link_faces if o.index != f.index]
            if nb:
                best = max(set(nb), key=nb.count)
                if nb.count(best) >= 2 and best != lab[f.index] and not (lab[f.index] == "jacket" or best == "jacket"):
                    new[f.index] = best
        lab = new
    bm.free()
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    rng = random.Random(3)
    cols = {k: B.hex2rgb(v) for k, v in PAL.items()}
    for p in me.polygons:
        key = lab[p.index]
        c = p.center
        if key == "jacket" and c.y < -0.25 and c.z > 0.55 and abs(c.x - J.FACE_X) < 0.06 + (c.z - 0.55) * 0.22:
            key = "tee"
        k = 1 + rng.uniform(-0.05, 0.05)
        col = cols[key]
        if key == "hair":   # 운영자 2026-11-18 "머리 색 제대로": 은회색, 위는 밝고 옆·아래는 짙게 + 뒤로 넘긴 짙은 결
            t = min(1.0, max(0.0, (c.z - 1.55) / 0.55))
            dark, light = B.hex2rgb("#5F5F5E"), B.hex2rgb("#ADADA8")
            col = [dark[i] + (light[i] - dark[i]) * t for i in range(3)]
            if math.sin((c.x - J.FACE_X) * 34 + c.y * 9) > 0.55:
                col = [v * 0.62 for v in col]
        for li in p.loop_indices:
            attr.data[li].color = (col[0] * k, col[1] * k, col[2] * k, 1)
    ob.data.materials.append(B.material("jensen_mat", vcol=True, rough=0.8))


def jensen_eyes(face, body):
    """젠슨 황 눈: 가로로 길고 가늘게, 바깥 끝이 살짝 처지게 + 짙은 눈썹(윗테 바로 아래)."""
    brow_m = J.mat("jensen_brow", "#3B3A38", 0.7)
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    for sd, sx in (("L", -1), ("R", 1)):
        e = bpy.data.objects[f"jensen_real_eye_{sd}"]
        e.scale = (1.3, 1, 0.85)                              # 눈 폭 0.34io (사진)
        e.rotation_euler = (0, math.radians(7 * sx), 0)      # 바깥 끝이 아래로
        hl = bpy.data.objects[f"jensen_real_eyehl_{sd}"]
        hl.location.z -= 0.004
        b = J.box(f"jensen_brow_{sd}", 0.1, 0.014, 0.017, 0.004)
        bx, bz = e.location.x - sx * 0.004, e.location.z + 0.35 * IO   # 눈썹 = 눈 위 0.29io (윗테 바로 위), 이마 표면에 붙임
        b.scale = (1.25, 1, 1)
        b.location = (bx, J.front_y(bvh, bx, bz) - 0.004, bz)
        b.rotation_euler = (0, math.radians(5 * sx), 0)
        b.data.materials.append(brow_m)
        b.parent = face


def add_lips(body, face, w=MOUTH_HW, up=0.024, lo=0.038):
    """얼굴 표면에 딱 붙는 매끈한 윗입술·아랫입술 (원래 사진 비율, 자연스러운 색). 가운데 입술선은 두 조각 사이 가는 틈."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)
    n = 14
    gap = 0.004

    def outline(top):
        pts = []
        for k in range(n + 1):
            t = -1 + 2 * k / n
            span = 1 - t * t
            if top:
                bow = 1 - 0.35 * math.exp(-(t / 0.18) ** 2)      # 큐피드 활
                pts.append((t * w, gap + up * span * bow - 0.012 * t * t))
            else:
                pts.append((t * w, -gap - lo * span ** 0.7 - 0.012 * t * t))
        base = [(t * w * 0.98, (gap if top else -gap) - 0.012 * t * t) for t in [1 - 2 * k / n for k in range(1, n)]]
        return pts + base

    for name, top, hexc in (("jensen_lip_upper", True, "#A75D5A"), ("jensen_lip_lower", False, "#B96A65")):
        ol = outline(top)
        bm = bmesh.new()
        vs = []
        for x, dz in ol:
            X, Z = J.FACE_X + x, J.MOUTH_Z + dz
            hit = bvh.ray_cast(Vector((X, -3, Z)), Vector((0, 1, 0)))
            Y = (hit[0].y if hit[0] else -0.45) - 0.003
            vs.append(bm.verts.new((X, Y, Z)))
        bm.faces.new(vs)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        ob = B.bm_to_obj(bm, name)
        B.shade_flat(ob)
        ob.data.materials.append(J.mat(name + "_m", hexc, 0.55))
        ob.parent = face
    # 입술 사이 선
    line = []
    for k in range(13):
        t = -0.95 + 1.9 * k / 12
        X = J.FACE_X + t * w
        hit = bvh.ray_cast(Vector((X, -3, J.MOUTH_Z)), Vector((0, 1, 0)))
        line.append((X, (hit[0].y if hit[0] else -0.45) - 0.002, J.MOUTH_Z - 0.012 * t * t))
    lt = B.arc_tube("jensen_lip_line", line, 0.0035, ring=5)
    lt.data.materials.append(J.mat("jensen_lip_line_m", "#5E2626", 0.5))
    lt.parent = face


def main():
    sc = B.setup_scene()
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.data.use_shadow = False
            if o.name == "key":
                o.data.energy = 900
    L.SRC = SRC
    src_bm, img = L.load_src()
    L.normalize(src_bm)
    body = build_shape(src_bm)
    classify(body, src_bm, img)
    face = J.add_face_parts(body)
    jensen_eyes(face, body)
    add_lips(body, face)
    J.stylize(body, face)
    for o in face.children:   # 이 판에서는 덧붙인 입선 없음 (입술은 면에 칠함)
        if o.name.startswith("jensen_real_mouth_smile"):
            bpy.data.objects.remove(o)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    face.select_set(True)
    for c in face.children_recursive:
        c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(B.OUT, "jensen.glb"), export_format="GLB", use_selection=True,
                              export_vertex_color="ACTIVE")
    fz = 1.72
    B.camera(sc, (0.0, -4.4, fz + 0.1), (J.FACE_X, 0, fz - 0.1), lens=50, focus=(J.FACE_X, -0.6, fz), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, "jensen_front.png"), 1080, 1350)
    B.camera(sc, (2.4, -3.7, fz + 0.2), (J.FACE_X, 0, fz - 0.15), lens=50, focus=(J.FACE_X, -0.5, fz), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, "jensen_q34.png"), 1080, 1350)
    print("faces", len(body.data.polygons))


main()
