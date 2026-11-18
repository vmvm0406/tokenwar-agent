// 사무실 책상 장면 (운영자 2026-11-18): 사람은 책상 앞에 앉고, AI 캐릭터는 책상 위에.
// 레퍼런스(@canwebuildthis)처럼 큰 동작 없이 컷 바꾸기 + 표정 + 작은 몸짓. render.py가 twInit(script) → twFrame(t).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const W = 1080, H = 1920;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, u) => a + (b - a) * u;
const ease = (u) => { u = clamp(u); return u * u * (3 - 2 * u); };
const bump = (t, t0, d) => (t < t0 || t > t0 + d) ? 0 : Math.sin(Math.PI * (t - t0) / d);   // 0→1→0

// ---------- 표정 (build.py EMOTIONS와 같음. 기본 neutral = 무표정) ----------
const EMO = {
  neutral: ['eye_open', 'brow_neutral', 'mouth_rest'],
  smile: ['eye_open', 'brow_neutral', 'mouth_smile'],
  happy: ['eye_happy', 'brow_neutral', 'mouth_open', 'blush'],
  surprised: ['eye_wide', 'brow_neutral', 'mouth_o'],
  sad: ['eye_open', 'brow_sad', 'mouth_frown'],
  angry: ['eye_open', 'brow_angry', 'mouth_flat'],
  embarrassed: ['eye_closed', 'brow_neutral', 'mouth_wavy', 'blush', 'sweat'],
  sleepy: ['eye_closed', 'brow_neutral', 'mouth_flat'],
};
const EMO_OVERRIDE = { jensen: { smile: ['eye_open', 'brow_neutral', 'mouth_grin'], happy: ['eye_happy', 'brow_neutral', 'mouth_grin', 'blush'] } };
const PARTS = ['eye_open', 'eye_wide', 'eye_happy', 'eye_closed', 'brow_angry', 'brow_sad', 'brow_neutral', 'blush', 'sweat',
  'mouth_smile', 'mouth_frown', 'mouth_flat', 'mouth_rest', 'mouth_open', 'mouth_o', 'mouth_wavy', 'mouth_grin'];
const MOUTHS = PARTS.filter((p) => p.startsWith('mouth_'));

function facePartsOf(root, key) {
  const parts = {};
  root.traverse((o) => {
    if (!o.name || !o.name.startsWith(key + '_') || o.name.includes('_eyehl_')) return;
    const rest = o.name.slice(key.length + 1);
    const p = PARTS.find((q) => rest === q || rest.startsWith(q + '_'));
    if (p) (parts[p] = parts[p] || []).push(o);
  });
  return parts;
}
// emo + 말하는 중(open 0..1) + 눈 깜빡임 → 부품 켜고 끄기
function setFace(c, emo, open, blinking) {
  const on = new Set((EMO_OVERRIDE[c.key] || {})[emo] || EMO[emo] || EMO.neutral);
  if (open > 0.35) { MOUTHS.forEach((m) => on.delete(m)); on.add(c.key === 'jensen' ? 'mouth_grin' : 'mouth_open'); }
  if (blinking && on.has('eye_open')) { on.delete('eye_open'); on.add('eye_closed'); }
  for (const p in c.parts) c.parts[p].forEach((o) => { o.visible = on.has(p); });
}

// ---------- 소품 (로우폴리, 면 명암) ----------
const mat = (c, r = 0.75) => new THREE.MeshStandardMaterial({ color: c, roughness: r, flatShading: true });
function box(scene, w, h, d, c, x, y, z, r = 0.75) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(c, r));
  m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; scene.add(m); return m;
}
function buildOffice(scene, deskY) {
  box(scene, 12, 0.02, 12, 0x2b2119, 0, -0.01, 0);                              // 바닥
  box(scene, 12, 6, 0.1, 0x3a2c22, 0, 3, -2.2);                                  // 뒷벽
  box(scene, 2.6, 1.5, 0.06, 0x0e1626, -0.2, 2.0, -2.13, 0.3);                    // 창 (밤)
  const bulbM = new THREE.MeshStandardMaterial({ color: 0xffb35a, emissive: 0xffa040, emissiveIntensity: 6 });
  for (let k = 0; k < 22; k++) {                                                 // 창밖 불빛·꼬마전구 (빛망울용)
    const s = new THREE.Mesh(new THREE.IcosahedronGeometry(0.03 + 0.03 * ((k * 37) % 7) / 7, 0), bulbM);
    s.position.set(-1.5 + 2.6 * ((k * 53) % 22) / 22, 1.35 + 1.4 * ((k * 29) % 13) / 13, -2.08); scene.add(s);
  }
  // 책상
  box(scene, 2.6, 0.07, 1.15, 0x8a5a3c, 0, deskY - 0.035, 0.05, 0.6);
  box(scene, 0.08, deskY - 0.07, 1.0, 0x6b4430, -1.2, (deskY - 0.07) / 2, 0.05);
  box(scene, 0.08, deskY - 0.07, 1.0, 0x6b4430, 1.2, (deskY - 0.07) / 2, 0.05);
  box(scene, 2.44, deskY - 0.12, 0.04, 0x704732, 0, (deskY - 0.07) / 2 + 0.02, 0.6);   // 앞 가림판 (책상 밑 다리 안 보이게)
  // 모니터 (옆으로 비켜서 얼굴을 안 가림)
  const mon = new THREE.Group();
  const scr = box(mon, 0.86, 0.52, 0.04, 0x1a1c22, 0, 0.42, 0, 0.4);
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.46), new THREE.MeshStandardMaterial({ color: 0x0b1a12, emissive: 0x00ff66, emissiveIntensity: 0.18 }));
  glow.position.set(0, 0.42, 0.021); mon.add(glow);
  box(mon, 0.08, 0.16, 0.06, 0x24262c, 0, 0.1, -0.02); box(mon, 0.3, 0.02, 0.2, 0x24262c, 0, 0.01, 0);
  mon.position.set(0.82, deskY, -0.22); mon.rotation.y = -0.55; scene.add(mon);
  box(scene, 0.62, 0.025, 0.2, 0x2c2f36, -0.05, deskY + 0.012, -0.12, 0.5);      // 키보드
  const mug = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.045, 0.11, 8), mat(0xe8e2d6, 0.5));
  mug.position.set(-0.85, deskY + 0.055, -0.1); mug.castShadow = true; scene.add(mug);
  box(scene, 0.12, 0.004, 0.12, 0x00ff66, -0.6, deskY + 0.002, 0.3, 0.9).rotation.y = 0.3;   // 포스트잇 (초록)
  box(scene, 0.3, 0.05, 0.22, 0x3d6b52, 1.0, deskY + 0.025, 0.28).rotation.y = -0.2;          // 책
  return { mon };
}

// ---------- 캐릭터 ----------
const loader = new GLTFLoader();
const load = (url) => new Promise((res, rej) => loader.load(url, (g) => res(g.scene), undefined, rej));
const _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _v = new THREE.Vector3(), _v2 = new THREE.Vector3();

// 뼈를 세계 방향 dir로 겨누기 (축 부호를 몰라도 되게): 뼈의 로컬 +Y(블렌더 뼈 방향)가 dir이 되도록 회전
function aim(bone, _child, dir, u = 1) {
  bone.updateWorldMatrix(true, false);
  const cur = new THREE.Vector3(0, 1, 0).applyQuaternion(bone.getWorldQuaternion(new THREE.Quaternion())).normalize();
  const rw = new THREE.Quaternion().setFromUnitVectors(cur, dir.clone().normalize());
  if (u < 1) rw.slerp(new THREE.Quaternion(), 1 - u);
  turnW(bone, rw);
}
// 세계 회전 rw를 뼈의 로컬 회전에 반영
function turnW(bone, rw) {
  bone.parent.updateWorldMatrix(true, false);
  bone.parent.getWorldQuaternion(_q);
  const inv = _q.clone().invert();
  bone.quaternion.premultiply(inv.multiply(rw).multiply(_q));
  bone.updateWorldMatrix(false, true);
}
const rotW = (bone, axis, ang) => turnW(bone, new THREE.Quaternion().setFromAxisAngle(axis, ang));
const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1);

async function loadHuman(key, file, height) {
  const root = await load(`/assets/characters/${file}.glb`);
  const bones = {};
  // GLTFLoader가 이름의 '.'을 지움 (thigh.L → thighL) → 원래 이름으로도 부를 수 있게
  root.traverse((o) => { if (o.isBone) { bones[o.name] = o; bones[o.name.replace(/([LR])$/, '.$1')] = o; } if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  const box3 = new THREE.Box3().setFromObject(root), h = box3.max.y - box3.min.y;
  root.scale.setScalar(height / h);
  const c = { key, root, bones, parts: facePartsOf(root, key), human: true };
  return c;
}
// 앉은 자세 (기본 자세를 세계 방향으로 겨눠 만듦) → 각 뼈의 기본 회전 저장
function sitPose(c) {
  const B = c.bones;
  for (const s of ['L', 'R']) {
    const sx = s === 'L' ? 1 : -1;   // 캐릭터 왼쪽 = 세계 +X (정면이 +Z일 때)
    aim(B[`thigh.${s}`], null, new THREE.Vector3(0.04 * sx, -0.1, 1));          // 허벅지 앞으로
    aim(B[`shin.${s}`], null, new THREE.Vector3(0, -1, 0.08));                  // 정강이 아래로 (무릎 굽힘)
    aim(B[`upper_arm.${s}`], null, new THREE.Vector3(0.12 * sx, -0.8, 0.55));   // 팔꿈치 몸 옆
    aim(B[`lower_arm.${s}`], null, new THREE.Vector3(-0.15 * sx, 0.05, 1));     // 아래팔 책상 위로
  }
}
function fixShins() {}
async function loadAI(key, height) {
  const outer = new THREE.Group();
  const g = await load(`/assets/characters/${key}.glb`);
  g.traverse((o) => { if (o.isMesh) { o.castShadow = true; } });
  const b = new THREE.Box3().setFromObject(g);
  const s = height / (b.max.y - b.min.y);
  g.scale.setScalar(s); g.position.y = -b.min.y * s;
  const sq = new THREE.Group(); sq.add(g); outer.add(sq);
  return { key, root: outer, sq, parts: facePartsOf(g, key), human: false };
}

// ---------- 조립 ----------
let renderer, composer, bokeh, scene, camera, cast = {}, S, POS = {}, deskY = 0.74, out, g2;
window.twInit = async (script) => {
  S = script;
  await document.fonts.load('700 50px Wanted', '가A');
  renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1); renderer.setSize(W, H);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x1d1611);
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.55;
  const key = new THREE.DirectionalLight(0xffd6a8, 2.4); key.position.set(-2.2, 3.6, 3.0); key.castShadow = true;
  Object.assign(key.shadow.camera, { left: -2, right: 2, top: 2.5, bottom: -1, near: 0.5, far: 12 });
  key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; scene.add(key);
  const rim = new THREE.DirectionalLight(0x9fc8ff, 1.2); rim.position.set(2.4, 2.6, -3); scene.add(rim);
  const monLight = new THREE.PointLight(0x66ffaa, 0.15, 2); monLight.position.set(0.7, 1.2, -0.05); scene.add(monLight);
  scene.add(new THREE.HemisphereLight(0xffe8d0, 0x3a2418, 0.45));

  // 사람: 키 1.55(큰 머리 비율), 앉힘
  for (const p of S.cast.filter((p) => p.human)) {
    const c = await loadHuman(p.key, p.file || p.key, 1.55);
    sitPose(c); fixShins(c);
    c.base = {}; for (const n in c.bones) c.base[n] = c.bones[n].quaternion.clone();
    scene.add(c.root);
    cast[p.key] = c;
  }
  // 사람 위치: 엉덩이가 의자 높이(0.46)에 오게, 책상 뒤
  const hum = Object.values(cast).find((c) => c.human);
  if (hum) {
    hum.root.position.set(0, 0, -0.62);
    hum.root.updateMatrixWorld(true);
    const hipY = hum.bones.hips.getWorldPosition(new THREE.Vector3()).y;
    hum.root.position.y += 0.46 - hipY;
    hum.root.updateMatrixWorld(true);
    deskY = hum.bones.spine.getWorldPosition(new THREE.Vector3()).y + 0.06;      // 책상은 배꼽 위쯤
    box(scene, 0.6, 0.06, 0.55, 0x3b3f48, 0, 0.43, -0.62);                     // 의자
    box(scene, 0.6, 0.7, 0.06, 0x3b3f48, 0, 0.8, -0.95);
    POS[hum.key] = { x: 0, face: hum.bones.head.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(0, 0.16, 0.12)) };
  }
  buildOffice(scene, deskY);
  // AI: 책상 위 (높이 0.34)
  for (const p of S.cast.filter((p) => !p.human)) {
    const c = await loadAI(p.key, p.size || 0.34);
    c.root.position.set(p.x, deskY, p.z ?? 0.2);
    c.baseYaw = p.yaw || 0;
    scene.add(c.root); cast[p.key] = c;
    POS[p.key] = { x: p.x, size: p.size || 0.34, face: new THREE.Vector3(p.x, deskY + (p.size || 0.34) * 0.55, (p.z ?? 0.2) + 0.1) };
  }
  camera = new THREE.PerspectiveCamera(36, W / H, 0.05, 40);
  const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 });
  composer = new EffectComposer(renderer, rt); composer.setPixelRatio(1); composer.setSize(W, H);
  composer.addPass(new RenderPass(scene, camera));
  bokeh = new BokehPass(scene, camera, { focus: 2, aperture: 0.004, maxblur: 0.012 }); composer.addPass(bokeh);
  composer.addPass(new OutputPass());
  out = document.createElement('canvas'); out.width = W; out.height = H; g2 = out.getContext('2d');
  const gl = renderer.getContext(), dbg = gl.getExtension('WEBGL_debug_renderer_info');
  return { renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : '', deskY, cast: Object.keys(cast) };
};

// ---------- 시간 → 상태 ----------
const linesOf = (who) => S.lines.filter((l) => l.who === who);
function speaking(who, t) {   // 말하는 중이면 입 벌림 정도 0..1 (오디오 크기)
  for (const l of linesOf(who)) {
    if (t < l.t || t > l.t + l.dur) continue;
    const i = Math.floor((t - l.t) * S.fps);
    return clamp((l.env[i] || 0) / 0.6);
  }
  return 0;
}
function stateOf(who, t) {   // 지금 표정: 가장 최근에 시작한 대사·이벤트의 emo
  let emo = 'neutral';
  for (const e of [...S.lines, ...S.events].filter((e) => e.who === who && e.emo).sort((a, b) => a.t - b.t)) if (t >= e.t - 0.1) emo = e.emo;
  return emo;
}
const evs = (who, name) => S.events.filter((e) => e.who === who && e.do === name);
function blinkAt(who, t) {
  const seed = who.length * 0.37;
  const ph = (t + seed * 3.1) % 3.7;
  return ph < 0.12;
}
function lookYaw(who, t) {   // 말하는 사람 쪽을 봄 (자기가 말할 땐 카메라 쪽)
  let target = null;
  for (const e of S.events.filter((e) => e.who === who && e.do === 'look').sort((a, b) => a.t - b.t)) if (t >= e.t) target = e.at;
  if (!target || target === 'camera') return 0;
  const me = POS[who], o = POS[target];
  if (!me || !o) return 0;
  if (!cast[who].human) {   // AI는 얼굴이 카메라에서 사라지지 않게 그쪽으로 살짝만 돈다
    const dx = o.face.x - me.face.x;
    return Math.sign(dx || 1) * Math.min(0.5, 0.25 + Math.abs(dx) * 0.4) - (cast[who].baseYaw || 0) * 0.5;
  }
  return Math.atan2(o.face.x - me.face.x, Math.max(0.25, o.face.z - me.face.z + 0.6)) * 0.9;
}

function animAI(c, t) {
  const who = c.key, open = speaking(who, t);
  let y = 0, sy = 1 + 0.025 * Math.sin(2 * Math.PI * 0.9 * t + who.length) + 0.06 * open;   // 숨쉬기 + 말하기 출렁
  let rx = 0, ry = c.baseYaw + lookYaw(who, t), rz = 0, jx = 0;
  for (const e of evs(who, 'hop')) { const b = bump(t, e.t, 0.38); y += 0.09 * b; sy += 0.12 * b - 0.1 * bump(t, e.t + 0.38, 0.12); }
  for (const e of evs(who, 'nod')) rx += 0.22 * Math.sin(Math.PI * 2 * clamp((t - e.t) / 0.5)) * (t > e.t && t < e.t + 1.0 ? 1 : 0);
  for (const e of evs(who, 'shake')) ry += 0.3 * Math.sin(Math.PI * 4 * clamp((t - e.t) / 0.8)) * (t > e.t && t < e.t + 0.8 ? 1 : 0);
  for (const e of evs(who, 'tilt')) rz += 0.22 * ease((t - e.t) / 0.25) * (1 - ease((t - e.t - (e.d || 1.2)) / 0.3));
  for (const e of evs(who, 'tremble')) if (t > e.t && t < e.t + (e.d || 1)) jx += 0.0022 * Math.sin(t * 55);   // 운영자: 부들거림 작게
  c.root.position.y = deskY + y;
  c.sq.scale.set(1 / Math.sqrt(sy), sy, 1 / Math.sqrt(sy));
  c.root.rotation.set(rx, ry, rz);
  c.sq.position.x = jx;
  setFace(c, stateOf(who, t), open, blinkAt(who, t));
}
function animHuman(c, t) {
  const B = c.bones, who = c.key, open = speaking(who, t);
  for (const n in B) B[n].quaternion.copy(c.base[n]);
  c.root.updateMatrixWorld(true);
  rotW(B.spine, X, 0.03 * Math.sin(2 * Math.PI * 0.3 * t));                    // 숨쉬기
  rotW(B.head, Y, lookYaw(who, t));
  rotW(B.head, X, -0.04 * open * Math.sin(t * 9));                             // 말할 때 살짝 끄덕끄덕
  for (const e of evs(who, 'nod')) if (t > e.t && t < e.t + 1) rotW(B.head, X, 0.25 * Math.sin(Math.PI * 2 * (t - e.t) / 0.5));
  for (const e of evs(who, 'sigh')) { const b = bump(t, e.t, 1.4); rotW(B.spine, X, 0.18 * b); rotW(B.head, X, 0.2 * b); }
  for (const e of evs(who, 'facepalm')) {                                       // 이마 짚기: 오른손을 이마로
    const u = ease((t - e.t) / 0.35) * (1 - ease((t - e.t - (e.d || 1.6)) / 0.4));
    if (u <= 0) continue;
    rotW(B.head, X, 0.22 * u);
    const head = B.head.getWorldPosition(new THREE.Vector3());
    const forehead = head.clone().add(new THREE.Vector3(-0.02, 0.17, 0.2));
    const sh = B['upper_arm.R'].getWorldPosition(new THREE.Vector3());
    const elbow = sh.clone().lerp(forehead, 0.5).add(new THREE.Vector3(-0.12, -0.14, 0.12));
    aim(B['upper_arm.R'], null, elbow.sub(sh), u);
    const el = B['lower_arm.R'].getWorldPosition(new THREE.Vector3());
    aim(B['lower_arm.R'], null, forehead.clone().sub(el), u);
  }
  for (const e of evs(who, 'type')) if (t > e.t && t < e.t + (e.d || 2)) {   // 타자
    rotW(B['lower_arm.L'], X, 0.06 * Math.sin(t * 22)); rotW(B['lower_arm.R'], X, 0.06 * Math.sin(t * 22 + 1.7));
  }
  c.root.updateMatrixWorld(true);
  setFace(c, stateOf(who, t), open, blinkAt(who, t));
}

// ---------- 카메라 ----------
function shotAt(t) { let s = S.shots[0]; for (const x of S.shots) if (t >= x.t) s = x; return s; }
function camFor(s, t) {
  const [kind, a, b] = s.cam.split(':');
  const nextT = (S.shots.find((x) => x.t > s.t) || { t: S.dur }).t, u = clamp((t - s.t) / Math.max(0.5, nextT - s.t));
  let look, pos, focus, ap;
  if (kind === 'wide') {
    look = new THREE.Vector3(0, deskY + 0.5, -0.15);
    pos = new THREE.Vector3(0.05, deskY + 0.85, 3.25);
    focus = look.clone(); ap = 0.0012;
  } else if (kind === 'close') {
    const f = POS[a].face.clone(), human = cast[a].human, sz = POS[a].size || 0.4;
    look = f.clone().add(new THREE.Vector3(0, human ? -0.06 : -0.04, 0));
    const d = human ? 1.05 : sz * 3.4;   // AI가 화면 높이의 절반쯤
    pos = f.clone().add(new THREE.Vector3(human ? 0.08 : 0.06 * d, human ? 0.04 : 0.12 * d, d));
    focus = f; ap = human ? 0.008 : 0.016;   // 뒤(사람·벽)는 흐리게
  } else {   // two:a:b — 세로 화면에 둘이 다 들어오게 거리 계산 (가로 시야 약 20.7°)
    const fa = POS[a].face, fb = POS[b].face, m = fa.clone().add(fb).multiplyScalar(0.5);
    const span = Math.abs(fa.x - fb.x), sz = Math.max(POS[a].size || 0.4, POS[b].size || 0.4);
    const d = (span / 2 + sz * 0.65) / Math.tan(THREE.MathUtils.degToRad(10.3));
    look = m.clone().add(new THREE.Vector3(0, -0.04, 0));
    pos = m.clone().add(new THREE.Vector3(0.03, 0.1 * d, d));
    focus = m; ap = 0.003;
  }
  pos.lerp(look, 0.07 * ease(u));   // 천천히 다가가기
  return { pos, look, focus, ap };
}

// ---------- 자막 ----------
function wrap(text, maxW) {
  const out = []; let cur = '';
  for (const w of text.split(' ')) { const tryS = cur ? cur + ' ' + w : w; if (g2.measureText(tryS).width > maxW && cur) { out.push(cur); cur = w; } else cur = tryS; }
  if (cur) out.push(cur); return out;
}
function caption(t) {
  const l = S.lines.find((l) => t >= l.t - 0.05 && t <= l.t + l.dur + 0.15);
  if (!l || !l.sub) return;
  g2.font = '700 50px Wanted';
  const rows = wrap(l.sub, 780), lh = 66, pad = 26;
  const w = Math.max(...rows.map((r) => g2.measureText(r).width)) + pad * 2, h = rows.length * lh + pad * 1.4;
  const x = (W - w) / 2, y = 360;
  g2.fillStyle = 'rgba(0,0,0,0.62)'; g2.beginPath(); g2.roundRect(x, y, w, h, 14); g2.fill();
  g2.fillStyle = '#fff'; g2.textAlign = 'center'; g2.textBaseline = 'middle';
  rows.forEach((r, i) => g2.fillText(r, W / 2, y + pad * 0.7 + lh * (i + 0.5)));
}

window.twFrame = (t) => {
  for (const k in cast) (cast[k].human ? animHuman : animAI)(cast[k], t);
  const cam = camFor(shotAt(t), t);
  camera.position.copy(cam.pos); camera.lookAt(cam.look); camera.updateMatrixWorld();
  bokeh.uniforms.focus.value = camera.position.distanceTo(cam.focus);
  bokeh.uniforms.aperture.value = cam.ap; bokeh.uniforms.maxblur.value = 0.014;
  composer.render();
  g2.drawImage(renderer.domElement, 0, 0, W, H);
  caption(t);
  return out.toDataURL('image/jpeg', 0.92);
};
window.twReady = true;
