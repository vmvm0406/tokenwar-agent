"""사진 → 3D(AI)로 만든 모델을 우리 로우폴리 화풍으로 (운영자 2026-11-18 "실물을 그대로 로우폴리화").

입력 glb(질감 있는 고해상도) → 합치기 → 복셀 리메시(구멍 메움) → Decimate(큼직한 삼각형) → 평면 셰이딩
→ 면마다 원래 질감에서 색 하나를 뽑음(가장 가까운 원래 면의 UV → 질감 픽셀) → glb + 미리보기.

실행:
  & "C:\\Program Files\\Blender Foundation\\Blender 5.3\\blender.exe" --background --python experiments/lowpoly-chars/lowpoly_from_glb.py -- <입력.glb> <이름> [면수=3000] [--quick]
결과: out/<이름>_lp.glb, out/<이름>_lp_front.png, out/<이름>_lp_q34.png
"""
import bpy, bmesh, os, sys, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
SRC, NAME = a[0], a[1]
FACES = int(a[2]) if len(a) > 2 and a[2].isdigit() else 3000


def load_src():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SRC)
    meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    bm = bmesh.new()
    img = None
    dg = bpy.context.evaluated_depsgraph_get()
    for o in meshes:
        me = o.evaluated_get(dg).to_mesh()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        o.evaluated_get(dg).to_mesh_clear()
        for slot in o.material_slots:
            if slot.material and slot.material.use_nodes:
                for n in slot.material.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image and img is None:
                        img = n.image
    for o in [o for o in bpy.data.objects if o not in before]:
        bpy.data.objects.remove(o)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm, img


def normalize(bm):
    """키 2.2(우리 캐릭터 크기), 바닥 z=0, 가운데 x=y=0."""
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    s = 2.2 / (max(zs) - min(zs))
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
    for v in bm.verts:
        v.co = (v.co - c) * s


def sample_colors(lp, src_bm, img):
    """로우폴리 면마다: 가장 가까운 원래 삼각형 → 무게중심 좌표로 UV → 질감 픽셀 색 (sRGB→선형은 이미지가 처리)."""
    uv = src_bm.loops.layers.uv.active
    bvh = BVHTree.FromBMesh(src_bm)
    src_bm.faces.ensure_lookup_table()
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    attr = lp.data.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    for p in lp.data.polygons:
        loc, nrm, idx, dist = bvh.find_nearest(p.center)
        col = (0.5, 0.5, 0.5)
        if idx is not None and uv is not None:
            f = src_bm.faces[idx]
            tri = [l.vert.co for l in f.loops]
            uvs = [Vector((*l[uv].uv, 0)) for l in f.loops]
            u = barycentric_transform(loc, *tri, *uvs)
            x = int((u.x % 1.0) * (w - 1)); y = int((u.y % 1.0) * (h - 1))
            c3 = px[y, x, :3]
            if img.colorspace_settings.name.lower().startswith("srgb"):  # 8비트 질감은 sRGB 값 → 선형으로
                c3 = np.where(c3 <= 0.04045, c3 / 12.92, ((c3 + 0.055) / 1.055) ** 2.4)
            col = tuple(float(v) for v in c3)
        for li in p.loop_indices:
            attr.data[li].color = (*col, 1.0)


def main():
    sc = B.setup_scene()
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.data.use_shadow = False
    src_bm, img = load_src()
    normalize(src_bm)
    me = bpy.data.meshes.new(NAME + "_src")
    src_bm.to_mesh(me)
    lp = B.link(bpy.data.objects.new(NAME + "_lp", me.copy()))
    B.remesh(lp, 0.012)
    B.decimate(lp, FACES)
    B.shade_flat(lp)
    if img is not None:
        sample_colors(lp, src_bm, img)
    lp.data.materials.append(B.material(NAME + "_mat", vcol=True, rough=0.7))
    print("faces", len(lp.data.polygons), "texture", img.name if img else None)
    bpy.ops.object.select_all(action="DESELECT")
    lp.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(B.OUT, f"{NAME}_lp.glb"), export_format="GLB", use_selection=True, export_vertex_color="ACTIVE")
    zs = [v.co.z for v in lp.data.vertices]
    top = max(zs)
    B.camera(sc, (0, -4.2, top * 0.72), (0, 0, top * 0.68), lens=50, focus=(0, -0.3, top * 0.7), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, f"{NAME}_lp_front.png"), 1080, 1350)
    B.camera(sc, (2.2, -3.6, top * 0.75), (0, 0, top * 0.68), lens=50, focus=(0, -0.3, top * 0.7), fstop=2.4)
    B.render(sc, os.path.join(B.OUT, f"{NAME}_lp_q34.png"), 1080, 1350)


main()
