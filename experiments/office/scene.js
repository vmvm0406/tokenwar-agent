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
  if (open > 0.35) { const grin = on.has('mouth_grin'); MOUTHS.forEach((m) => on.delete(m)); on.add(grin ? 'mouth_grin' : 'mouth_open'); }   // 말할 때 입: 웃는 표정이면 웃는 입 그대로
  if (blinking && on.has('eye_open')) { on.delete('eye_open'); on.add('eye_closed'); }
  for (const p in c.parts) c.parts[p].forEach((o) => { o.visible = on.has(p); });
}

const OFFICE = {};

// ---------- 화면 속 릴스 (폰·모니터·태블릿) ----------
// clips: {id: {n, fps, base, credit}} → 프레임 이미지 미리 불러 둠. screens 일정: {screen, clip|null, t}.
const CLIPIMG = {};
async function loadClips(clips) {
  const jobs = [];
  for (const id in clips) {
    const c = clips[id]; CLIPIMG[id] = [];
    for (let k = 1; k <= c.n; k++) {
      const im = new Image(); im.src = `${c.base}${String(k).padStart(4, '0')}.jpg`;
      CLIPIMG[id].push(im); jobs.push(im.decode().catch(() => 0));
    }
  }
  await Promise.all(jobs);
}
function makeScreen(w, h, landscape) {
  // 모니터는 크게 (카메라가 다가가 화면을 꽉 채워도 덜 흐리게, 리트냥이 2026-11-18). 비율은 화면 판(0.8x0.46)과 같게
  const cv = document.createElement('canvas'); cv.width = landscape ? 1920 : 360; cv.height = landscape ? 1104 : 640;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
  return { cv, g: cv.getContext('2d'), tex, mesh: m, landscape };
}
function clipFrame(id, dt, hold) {   // 시각 dt(초)의 프레임 (끝나면 반복, hold면 마지막 장면에서 멈춤)
  const c = S.clips[id], imgs = CLIPIMG[id];
  const k = Math.floor(Math.max(0, dt) * c.fps);
  return imgs[hold ? Math.min(k, imgs.length - 1) : k % imgs.length];
}
function cover(g, im, x, y, w, h) {   // 그림을 칸에 꽉 채우기 (비율 유지, 넘치는 쪽 잘라냄)
  const iw = im.naturalWidth || im.width, ih = im.naturalHeight || im.height;
  const s = Math.max(w / iw, h / ih), sw = w / s, sh = h / s;
  g.drawImage(im, (iw - sw) / 2, (ih - sh) / 2, sw, sh, x, y, w, h);
}
// 그림이 그려지는 화면 (리트냥이 2026-11-18 "클로드가 그리는 게 티 나게"): reveal {d} 동안
// 흰 종이 → 연필 밑그림(흑백)이 왼쪽부터 → 색이 칠해짐, 그리는 자리에 연필. 글자 없음.
function drawReveal(g, s, im, t, off, W2, H2) {
  const u = clamp((t - s.t) / (s.reveal.d || 2)), y0 = off * H2;
  g.fillStyle = '#f3efe6'; g.fillRect(0, y0, W2, H2);
  const a = clamp(u / 0.62), b = clamp((u - 0.45) / 0.55);     // 밑그림 진행, 색칠 진행
  const rows = 4, rh = H2 / rows;
  const band = (p, filter) => {                                  // 줄마다 왼→오른쪽으로 (사람이 칠하듯)
    if (p <= 0) return;
    g.save(); g.beginPath();
    const done = p * rows;
    for (let r = 0; r < rows; r++) { const f = clamp(done - r); if (f > 0) g.rect(0, y0 + r * rh, W2 * f, rh + 1); }
    g.clip(); g.filter = filter; cover(g, im, 0, y0, W2, H2); g.restore();
  };
  band(a, 'grayscale(1) contrast(1.5) brightness(1.08)');
  band(b, 'none');
  if (u < 1) {                                                    // 연필 (지금 그리는 자리)
    const p = b > 0 ? b : a, done = p * rows, r = Math.min(rows - 1, Math.floor(done));
    const x = W2 * clamp(done - r), y = y0 + r * rh + rh * (0.5 + 0.35 * Math.sin(t * 23));
    g.save(); g.translate(x, y); g.rotate(-0.75);
    const L = H2 * 0.34, Wd = L * 0.13;
    g.fillStyle = '#f2c230'; g.fillRect(0, -Wd / 2, L, Wd);        // 몸통
    g.fillStyle = '#e9b48a'; g.beginPath(); g.moveTo(0, -Wd / 2); g.lineTo(-Wd * 1.3, 0); g.lineTo(0, Wd / 2); g.fill();   // 깎은 나무
    g.fillStyle = '#222'; g.beginPath(); g.moveTo(-Wd * 0.85, -Wd * 0.17); g.lineTo(-Wd * 1.3, 0); g.lineTo(-Wd * 0.85, Wd * 0.17); g.fill();   // 심
    g.fillStyle = '#e88a9a'; g.fillRect(L, -Wd / 2, Wd * 0.9, Wd);  // 지우개
    g.restore();
  }
}
const SWIPE = 0.35;
function drawScreen(sc, name, t) {
  const list = S.screens.filter((s) => s.screen === name && s.t <= t);
  const cur = list[list.length - 1], prev = list[list.length - 2];
  const g = sc.g, W2 = sc.cv.width, H2 = sc.cv.height;
  g.fillStyle = '#05070a'; g.fillRect(0, 0, W2, H2);
  // 화면 일정 선택 필드 (리트냥이 2026-11-18): bg(바탕 그림 clip id), rect [x,y,w,h](0~1, 바탕 위 액자 칸), grow {dt, d}(액자 칸이 화면 전체로 커짐), hold(마지막 장면에서 멈춤), from(클립 시작 초), noborder(액자 테두리 안 그림: 바탕 그림에 액자가 있을 때)
  const put = (s, off) => {   // 세로 릴스를 화면에 (모니터는 가운데 세로로, 양옆 어둡게 = 인스타 웹). 가로 영상(land)은 꽉 채움
    if (!s) return;
    if (s.bg && s.reveal) { drawReveal(g, s, clipFrame(s.bg, 0), t, off, W2, H2); }
    else if (s.bg) cover(g, clipFrame(s.bg, 0), 0, off * H2, W2, H2);
    if (!s.clip && !s.rect) return;
    let [rx, ry, rw, rh] = s.rect || [0, 0, 1, 1];
    if (s.rect && s.grow) {
      const u = ease((t - s.t - (s.grow.dt || 0)) / (s.grow.d || 1));
      rx = lerp(rx, 0, u); ry = lerp(ry, 0, u); rw = lerp(rw, 1, u); rh = lerp(rh, 1, u);
    }
    const X = rx * W2, Y = ry * H2 + off * H2, WW = rw * W2, HH = rh * H2;
    if (s.rect && !s.noborder) { const b = Math.max(4, WW * 0.03); g.fillStyle = '#efe9dc'; g.fillRect(X - b, Y - b, WW + 2 * b, HH + 2 * b); g.fillStyle = '#0a0a0a'; g.fillRect(X, Y, WW, HH); }
    if (!s.clip) return;
    const im = clipFrame(s.clip, t - s.t + (s.from || 0), s.hold);
    if (S.clips[s.clip].land || s.rect) cover(g, im, X, Y, WW, HH);
    else if (sc.landscape) { const h = H2, w = h * 9 / 16; g.drawImage(im, (W2 - w) / 2, off * H2, w, h); }
    else g.drawImage(im, 0, off * H2, W2, H2);
  };
  const shown = (s) => s && (s.clip || s.bg);
  if (shown(cur) && shown(prev) && !cur.cut && t - cur.t < SWIPE) {   // 위로 넘기기
    const u = ease((t - cur.t) / SWIPE);
    put(prev, -u); put(cur, 1 - u);
  } else put(cur, 0);
  sc.tex.needsUpdate = true;
  // 지금 이 화면에 나오는 영상 id (출처 표시는 twFrame에서: 화면이 카메라에 보일 때만, 처음 1.6초)
  return cur && cur.clip ? cur.clip : null;
}
// 화면(모니터·폰·태블릿)이 지금 카메라에 충분히 크게 보이는지 (리트냥이 2026-11-18 "영상이 안 보일 때 출처가 뜨면 이상해")
function screenVisible(sc) {
  const m = sc.mesh, pa = m.geometry.parameters, v = new THREE.Vector3();
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (const [a, b] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    v.set(a * pa.width / 2, b * pa.height / 2, 0).applyMatrix4(m.matrixWorld).project(camera);
    if (v.z > 1) return false;
    x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y);
  }
  const cx = (Math.max(x0, -1) + Math.min(x1, 1)) / 2, cy = (Math.max(y0, -1) + Math.min(y1, 1)) / 2;
  const w = Math.min(x1, 1) - Math.max(x0, -1);
  return w > 0.36 && Math.abs(cx) < 0.85 && Math.abs(cy) < 0.9;   // 화면 가로의 18% 이상, 화면 안쪽
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
  mon.position.set(0.66, deskY, -0.2); mon.rotation.y = -0.5; scene.add(mon);
  void scr;
  OFFICE.mon = mon; OFFICE.monGlow = glow;
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
  root.traverse((o) => {
    if (o.isBone) { bones[o.name] = o; bones[o.name.replace(/([LR])$/, '.$1')] = o; }
    if (o.isMesh) {
      o.castShadow = true; o.receiveShadow = true;
      // 얼굴 그림(텍스처)이 있는 재질은 꼭짓점 색을 곱하지 않음 (블렌더는 텍스처만 씀 → 곱하면 얼굴이 주황·어둡게 나옴)
      for (const m of [].concat(o.material)) if (m && m.map) { m.vertexColors = false; m.needsUpdate = true; }
    }
  });
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
const SCR = {}, PHONE = { g: null, pos: new THREE.Vector3(), mode: 'none' }, POP = { g: null }, REMOTE = {}, CREDIT_SEEN = {};
// 젠슨 폰 위치: face(얼굴 앞, 화면이 젠슨 쪽) / show(at 쪽으로 내밂, 화면이 그쪽) / down(책상에 엎어 둠)
function phonePose(mode, at) {
  const hu = Object.values(cast).find((c) => c.human);
  const face = POS[hu.key].face;
  if (mode === 'face') { const p = face.clone().add(new THREE.Vector3(-0.03, -0.24, 0.46)); return { p, look: face.clone() }; }   // 얼굴에 묻히지 않게 앞·아래로
  if (mode === 'show') { const T = POS[at].face; const p = face.clone().lerp(T, 0.66).add(new THREE.Vector3(0, 0.06, 0)); return { p, look: T.clone() }; }
  const p = new THREE.Vector3(-0.32, deskY + 0.006, -0.2); return { p, look: p.clone().add(new THREE.Vector3(0, 1, 0.001)) };
}
function updatePhone(t) {
  const ev = S.events.filter((e) => e.do === 'phone' && e.t <= t).sort((a, b) => a.t - b.t);
  if (!ev.length) { PHONE.g.visible = false; PHONE.mode = 'none'; return; }
  PHONE.g.visible = true;
  const cur = ev[ev.length - 1], prev = ev[ev.length - 2];
  const B = phonePose(cur.mode, cur.at), A = prev ? phonePose(prev.mode, prev.at) : B;
  const u = prev ? ease((t - cur.t) / 0.45) : 1;
  PHONE.g.position.copy(A.p).lerp(B.p, u);
  const look = A.look.clone().lerp(B.look, u);
  PHONE.g.lookAt(look);
  PHONE.g.updateMatrixWorld(true);
  POS.phone = { x: PHONE.g.position.x, face: PHONE.g.position.clone() };
  PHONE.mode = cur.mode; PHONE.hold = cur.mode === 'down' ? 1 - u : (prev && prev.mode === 'down' ? u : 1);
}
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
    c.baseYaw = p.yaw || 0; c.baseX = p.x; c.size = p.size || 0.34;
    scene.add(c.root); cast[p.key] = c;
    POS[p.key] = { x: p.x, size: p.size || 0.34, face: new THREE.Vector3(p.x, deskY + (p.size || 0.34) * 0.55, (p.z ?? 0.2) + 0.1) };
  }
  // 화면 속 릴스·소품
  if (S.clips) await loadClips(S.clips);
  SCR.monitor = makeScreen(0.8, 0.46, true);
  SCR.monitor.mesh.position.copy(OFFICE.monGlow.position).add(new THREE.Vector3(0, 0, 0.002));
  OFFICE.mon.add(SCR.monitor.mesh); OFFICE.monGlow.visible = false;
  OFFICE.mon.updateMatrixWorld(true);
  POS.monitor = { x: 0, face: SCR.monitor.mesh.getWorldPosition(new THREE.Vector3()) };
  // 폰 (젠슨 손)
  PHONE.g = new THREE.Group();
  const pb = new THREE.Mesh(new THREE.BoxGeometry(0.082, 0.165, 0.009), mat(0x15161a, 0.35)); PHONE.g.add(pb);
  SCR.phone = makeScreen(0.074, 0.1316, false); SCR.phone.mesh.position.z = 0.0052; PHONE.g.add(SCR.phone.mesh);
  scene.add(PHONE.g);
  // 지피티 태블릿 + 팝콘
  const gp = S.cast.find((p) => p.key === 'chatgpt');
  if (gp && S.props && S.props.tablet) {
    const tb = new THREE.Group();
    tb.add(new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.2, 0.01), mat(0x1b1c20, 0.4)));
    SCR.tablet = makeScreen(0.112, 0.199 * 0.92, false); SCR.tablet.mesh.position.z = 0.0058; tb.add(SCR.tablet.mesh);
    const stand = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.012, 0.08), mat(0x2b2d33)); stand.position.set(0, -0.1, -0.03); tb.add(stand);
    tb.position.set(gp.x + 0.22, deskY + 0.11, (gp.z ?? 0.2) + 0.06);
    tb.lookAt(new THREE.Vector3(gp.x - 0.25, deskY + 0.12, 1.6)); tb.rotateX(-0.12);
    scene.add(tb); tb.updateMatrixWorld(true);
    POS.tablet = { x: tb.position.x, face: tb.position.clone() };
  }
  if (gp && S.props && S.props.popcorn) {
    // 팝콘 통 (한 덩어리로 움직임: 지피티가 머리에 이고 들어와 옆에 내려놓음)
    POP.g = new THREE.Group();
    const stripes = document.createElement('canvas'); stripes.width = 64; stripes.height = 8;
    const sg = stripes.getContext('2d'); for (let k = 0; k < 8; k++) { sg.fillStyle = k % 2 ? '#f4efe6' : '#d8302c'; sg.fillRect(k * 8, 0, 8, 8); }
    const stx = new THREE.CanvasTexture(stripes); stx.colorSpace = THREE.SRGBColorSpace;
    const bucket = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.038, 0.1, 16, 1, true), new THREE.MeshStandardMaterial({ map: stx, roughness: 0.6, side: THREE.DoubleSide }));
    bucket.position.set(0, 0.05, 0); bucket.castShadow = true; POP.g.add(bucket);
    const pc = new THREE.MeshStandardMaterial({ color: 0xfff1c8, roughness: 0.9, flatShading: true });
    for (let k = 0; k < 16; k++) {
      const a = k * 2.39, r = 0.012 + 0.03 * ((k * 7) % 5) / 5;
      const p = new THREE.Mesh(new THREE.IcosahedronGeometry(0.013, 0), pc);
      p.position.set(r * Math.cos(a), 0.1 + 0.012 * ((k * 3) % 4) / 3, r * Math.sin(a));
      POP.g.add(p);
    }
    POP.rest = new THREE.Vector3(gp.x - 0.17, deskY, (gp.z ?? 0.2) + 0.1);
    POP.g.position.copy(POP.rest); scene.add(POP.g);
    POP.spill = [];
    for (let k = 0; k < 14; k++) { const sp = new THREE.Mesh(new THREE.IcosahedronGeometry(0.013, 0), pc); sp.visible = false; scene.add(sp); POP.spill.push(sp); }
  }
  if (S.props && S.props.remote) {   // 리모컨 (리트냥이 2026-11-18: 클로드가 끄덕이다 실수로 버튼을 누름). props.remote {x, z, yaw}
    const r = S.props.remote, g = new THREE.Group();
    g.add(Object.assign(new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.018, 0.15), mat(0x1c1d22, 0.45)), { castShadow: true }));
    for (let k = 0; k < 6; k++) {   // 작은 회색 버튼들
      const b = new THREE.Mesh(new THREE.CylinderGeometry(0.0065, 0.0065, 0.006, 10), mat(0x8a8d96, 0.5));
      b.position.set(-0.014 + 0.028 * (k % 2), 0.011, -0.002 + 0.022 * Math.floor(k / 2)); g.add(b);
    }
    REMOTE.btnMat = new THREE.MeshStandardMaterial({ color: 0xd8262b, emissive: 0xff2020, emissiveIntensity: 0.0, roughness: 0.4 });
    REMOTE.btn = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.008, 16), REMOTE.btnMat);
    REMOTE.btn.position.set(0, 0.012, -0.045); g.add(REMOTE.btn);
    g.position.set(r.x, deskY + 0.009, r.z); g.rotation.y = r.yaw || 0;
    scene.add(g); g.updateMatrixWorld(true);
    REMOTE.g = g; POS.remote = { x: r.x, face: REMOTE.btn.getWorldPosition(new THREE.Vector3()) };
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
  for (const e of evs(who, 'work')) if (t > e.t && t < e.t + (e.d || 2)) {   // 바쁘게 작업 (모니터 쪽으로 기울어 꼼지락, 리트냥이 2026-11-18)
    const k = ease((t - e.t) / 0.25) * (1 - ease((t - e.t - (e.d || 2) + 0.25) / 0.25));
    rx += 0.16 * k; rz += 0.07 * k * Math.sin(t * 15); y += 0.012 * k * Math.abs(Math.sin(t * 11));
  }
  // 크게 끄덕이다 앞의 리모컨 버튼을 눌러 버림 (리트냥이 2026-11-18): 0.35초 숙였다가 버튼에 닿은 채 0.25초 멈칫 → 천천히 일어남
  for (const e of evs(who, 'press')) {
    const r = t - e.t; if (r < 0 || r > 1.2) continue;
    const k = r < 0.35 ? ease(r / 0.35) : r < 0.6 ? 1 : 1 - ease((r - 0.6) / 0.6);
    rx += (e.amt || 0.75) * k; sy -= 0.06 * k;
  }
  // 화들짝 (놀람): 위로 튀며 뒤로 젖힘 → 잠깐 굳어 떨림 → 천천히 돌아옴
  for (const e of evs(who, 'startle')) {
    const r = t - e.t; if (r < 0 || r > 1.6) continue;
    y += 0.1 * bump(t, e.t, 0.32); sy += 0.16 * bump(t, e.t, 0.22) - 0.08 * bump(t, e.t + 0.3, 0.14);
    const k = r < 0.15 ? ease(r / 0.15) : 1 - ease((r - 0.9) / 0.7);
    rx -= 0.28 * k; if (r > 0.3 && r < 0.9) jx += 0.004 * Math.sin(t * 60);
  }
  for (const e of evs(who, 'tremble')) if (t > e.t && t < e.t + (e.d || 1)) jx += 0.0022 * Math.sin(t * 55);   // 운영자: 부들거림 작게
  let chew = 0;
  for (const e of evs(who, 'munch')) if (t > e.t && t < e.t + (e.d || 3)) {   // 팝콘 냠냠 (말 안 할 때 입 오물오물 + 통통)
    chew = Math.sin(t * 13) > 0.2 ? 0.6 : 0; sy += 0.03 * Math.abs(Math.sin(t * 6.5));
  }
  // 이동 (운영자 2026-11-18: 지피티가 눈치 보며 슬금슬금 들어왔다가 나가서 팝콘 이고 다시 옴)
  // move 이벤트: {x: 목표(숫자 또는 "home"/"off"), d, style: sneak(살금살금·두리번)|hop(통통)}. 첫 move 전에는 첫 move의 출발점.
  let x = c.baseX;
  const mv = evs(who, 'move').sort((a, b) => a.t - b.t);
  if (mv.length) {
    const X0 = (v) => v === 'home' ? c.baseX : v === 'off' ? 0.9 : v;   // off = 화면 바로 밖 (멀면 들어오는 모습이 안 보임)
    x = X0(mv[0].from ?? 'off');
    for (const e of mv) {
      if (t < e.t) break;
      const d = e.d || 1.2, u = clamp((t - e.t) / d), to = X0(e.x), from = x;
      x = lerp(from, to, e.style === 'sneak' ? u : ease(u));
      if (u < 1) {
        if (e.style === 'sneak') { y += 0.012 * Math.abs(Math.sin(Math.PI * (t - e.t) / 0.22)); rz += 0.06 * Math.sin(t * 9); ry += 0.45 * Math.sin(t * 2.6); }
        else { y += 0.06 * Math.abs(Math.sin(Math.PI * (t - e.t) / 0.32)); }
        ry += (to > from ? 0.6 : -0.6) * Math.sin(Math.PI * u) * 0.5;
      }
    }
  }
  if (POP.g) {   // 팝콘: carry(머리에 이기) → put(옆에 내려놓기), carry 전에는 숨김
    const ca = evs(who, 'carry')[0], pt = evs(who, 'put')[0];
    POP.g.visible = !!ca && t >= ca.t;
    if (ca && t >= ca.t) {
      const v = pt ? ease((t - pt.t) / 0.35) : 0;
      const head = new THREE.Vector3(x, deskY + y + c.size * 0.98, c.root.position.z);
      POP.g.position.copy(head).lerp(POP.rest, v);
      if (v > 0 && v < 1) POP.g.position.y += 0.08 * Math.sin(Math.PI * v);
      POP.g.rotation.set(0, 0, 0);
      // 젠슨이 팝콘 통을 던짐 (운영자 2026-11-18): 통이 젠슨 손으로 → 포물선으로 지피티 머리에 거꾸로 씌워짐 + 팝콘이 쏟아짐
      const th = S.events.find((e) => e.do === 'throw');
      if (th && t >= th.t) {
        const hu = Object.values(cast).find((q) => q.human), hand = POS[hu.key].face.clone().add(new THREE.Vector3(0.1, -0.32, 0.3));
        const capPos = new THREE.Vector3(x, deskY + y + c.size * 1.02, c.root.position.z);
        const a1 = ease((t - th.t) / 0.25), a2 = clamp((t - th.t - 0.3) / 0.35);
        if (t < th.t + 0.3) POP.g.position.copy(POP.rest).lerp(hand, a1);
        else {
          POP.g.position.copy(hand).lerp(capPos, a2);
          POP.g.position.y += 0.18 * Math.sin(Math.PI * a2);
          POP.g.rotation.x = Math.PI * a2;                       // 날아가며 뒤집힘
          if (a2 >= 1) POP.g.position.y += 0.1;                  // 거꾸로 씌워진 통 (가장자리가 머리에 걸침)
        }
        POP.hand = t < th.t + 0.3 ? POP.g.position.clone() : null;
        for (const [k, s] of (POP.spill || []).entries()) {        // 쏟아진 팝콘: 머리에서 튀어 책상으로
          const tt = t - th.t - 0.62;
          s.visible = tt > 0;
          if (tt <= 0) continue;
          const vx = Math.cos(k * 2.4) * 0.35, vz = Math.sin(k * 2.4) * 0.2 + 0.1, vy = 0.5 + 0.3 * ((k * 7) % 5) / 5;
          s.position.set(capPos.x + vx * tt, Math.max(deskY + 0.01, capPos.y + vy * tt - 4.9 * tt * tt), capPos.z + vz * tt);
        }
      }
    }
  }
  c.root.position.x = x;
  c.root.position.y = deskY + y;
  c.sq.scale.set(1 / Math.sqrt(sy), sy, 1 / Math.sqrt(sy));
  c.root.rotation.set(rx, ry, rz);
  c.sq.position.x = jx;
  setFace(c, stateOf(who, t), Math.max(open, open > 0.05 ? 0 : chew), blinkAt(who, t));
}
function animHuman(c, t) {
  const B = c.bones, who = c.key, open = speaking(who, t);
  for (const n in B) B[n].quaternion.copy(c.base[n]);
  c.root.updateMatrixWorld(true);
  rotW(B.spine, X, 0.03 * Math.sin(2 * Math.PI * 0.3 * t));                    // 숨쉬기
  rotW(B.head, Y, lookYaw(who, t));
  rotW(B.head, X, -0.04 * open * Math.sin(t * 9));                             // 말할 때 살짝 끄덕끄덕
  for (const e of evs(who, 'nod')) if (t > e.t && t < e.t + 1) rotW(B.head, X, 0.25 * Math.sin(Math.PI * 2 * (t - e.t) / 0.5));
  for (const e of evs(who, 'startle')) {   // 사람 화들짝: 몸·고개를 뒤로 젖힘
    const r = t - e.t; if (r < 0 || r > 1.8) continue;
    const k = r < 0.18 ? ease(r / 0.18) : 1 - ease((r - 1.0) / 0.8);
    rotW(B.spine, X, -0.16 * k); rotW(B.head, X, -0.22 * k);
  }
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
  for (const e of evs(who, 'throw')) {                                          // 팝콘 던지기: 통 쪽으로 뻗었다가 위로 휙
    const r = t - e.t;
    if (r < 0 || r > 1.1 || !POP.rest) continue;
    const u = r < 0.3 ? ease(r / 0.3) : 1 - ease((r - 0.55) / 0.5);
    const tgt = r < 0.3 ? POP.rest.clone().add(new THREE.Vector3(0, 0.12, 0)) : POP.rest.clone().add(new THREE.Vector3(0.1, 0.55, 0.2));
    const sh = B['upper_arm.R'].getWorldPosition(new THREE.Vector3());
    aim(B['upper_arm.R'], null, tgt.clone().sub(sh), u);
    const el = B['lower_arm.R'].getWorldPosition(new THREE.Vector3());
    aim(B['lower_arm.R'], null, tgt.clone().sub(el), u);
  }
  if (PHONE.g && PHONE.mode !== 'none' && PHONE.hold > 0.01) {                 // 오른손으로 폰 들기
    const u = PHONE.hold, ph = PHONE.g.position.clone();
    const sh = B['upper_arm.R'].getWorldPosition(new THREE.Vector3());
    const elbow = sh.clone().lerp(ph, 0.5).add(new THREE.Vector3(-0.1, -0.16, -0.02));
    aim(B['upper_arm.R'], null, elbow.sub(sh), u);
    const el = B['lower_arm.R'].getWorldPosition(new THREE.Vector3());
    aim(B['lower_arm.R'], null, ph.sub(el), u);
    if (PHONE.mode === 'face') rotW(B.head, X, 0.08 * u);                       // 폰 내려다보기
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
  if (kind === 'phone') {   // 폰 화면은 2D로 덮음(phoneOverlay). 뒤는 젠슨 가까이(흐리게)
    const hu = Object.values(cast).find((c) => c.human), f = POS[hu.key].face;
    return { pos: f.clone().add(new THREE.Vector3(0.1, 0.06, 2.7)), look: f.clone().add(new THREE.Vector3(0, -0.06, 0)), focus: f.clone().add(new THREE.Vector3(0, 0, 1.2)), ap: 0.02, phone: u };
  }
  if (kind === 'prop') {   // 소품 가까이 (prop:remote): 앞 위에서 내려다봄, 0.07 = 다가가기
    const f = POS[a].face.clone();
    look = f.clone().add(new THREE.Vector3(0, 0.03, -0.02));
    pos = f.clone().add(new THREE.Vector3(0.04, 0.2, 0.42));
    pos.lerp(look, 0.12 * ease(u));
    return { pos, look, focus: f, ap: 0.02 };
  }
  if (kind === 'mon') {   // 모니터 정면으로 다가가기 (리트냥이 2026-11-18): z0→z1 (1 = 모니터 가로가 화면 가로에 꼭 맞음, 약 3.1 = 세로까지 꽉 채움),
    // zd(초, 확대에 걸리는 시간, 기본 컷 길이), ox/oy(모니터 안 겨냥 위치 -0.5~0.5). 카메라와 화면 사이 물건(캐릭터)은 가까운 자르기 면으로 안 보이게
    const m = SCR.monitor.mesh, c = m.getWorldPosition(new THREE.Vector3()), q = m.getWorldQuaternion(new THREE.Quaternion());
    const n = new THREE.Vector3(0, 0, 1).applyQuaternion(q), right = new THREE.Vector3(1, 0, 0).applyQuaternion(q), up = new THREE.Vector3(0, 1, 0).applyQuaternion(q);
    const hf = Math.atan(Math.tan(THREE.MathUtils.degToRad(18)) * W / H), fitW = 0.4 / Math.tan(hf);
    const uz = ease(clamp((t - s.t) / (s.zd || Math.max(0.5, nextT - s.t))));
    const z = Math.exp(lerp(Math.log(s.z0 || 1), Math.log(s.z1 || s.z0 || 1), uz)), d = fitW / z;
    look = c.clone().addScaledVector(right, (s.ox || 0) * 0.8).addScaledVector(up, (s.oy || 0) * 0.46);
    pos = look.clone().addScaledVector(n, d);
    return { pos, look, focus: look.clone(), ap: 0.0004, near: Math.max(0.05, d - 0.1) };
  }
  if (kind === 'wide') {
    // 선택: dx(오른쪽으로 옮김, 모니터까지 넣기), back(뒤로 물러남 배수) — 리트냥이 2026-11-18
    const dx = s.dx || 0, bk = s.back || 1;
    look = new THREE.Vector3(dx, deskY + 0.5, -0.15);
    pos = new THREE.Vector3(0.05 + dx, deskY + 0.5 + 0.35 * bk, -0.15 + 3.4 * bk);
    focus = look.clone(); ap = 0.0012;
  } else if (kind === 'close') {
    const f = POS[a].face.clone(), human = cast[a].human, sz = POS[a].size || 0.4;
    look = f.clone().add(new THREE.Vector3(0, human ? -0.06 : -0.04, 0));
    const d = human ? 2.7 : sz * 3.4;   // AI가 화면 높이의 절반쯤 / 사람은 얼굴+어깨
    pos = f.clone().add(new THREE.Vector3(human ? 0.1 : 0.06 * d, human ? 0.06 : 0.12 * d, d));
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
  const l = S.lines.find((l) => !l.overlay && t >= l.t - 0.05 && t <= l.t + l.dur + 0.15);
  if (!l || !l.sub) return;
  g2.font = '700 50px Wanted';
  let text = l.sub;   // 호흡에 맞게 나눈 조각 중 지금 것
  if (l.subs && l.subs.length > 1) { const r = t - l.t; text = (l.subs.find((s) => r < s.t1) || l.subs[l.subs.length - 1]).text; }
  text = text.replace(/…/g, '...');   // '…'는 글자 가운데 높이에 찍혀서 마침표 셋으로 (운영자 2026-11-18)
  const rows = wrap(text, 780), lh = 66, pad = 26;
  const w = Math.max(...rows.map((r) => g2.measureText(r).width)) + pad * 2, h = rows.length * lh + pad * 1.4;
  const x = (W - w) / 2, y = 360;
  g2.fillStyle = 'rgba(0,0,0,0.62)'; g2.beginPath(); g2.roundRect(x, y, w, h, 14); g2.fill();
  g2.fillStyle = '#fff'; g2.textAlign = 'center'; g2.textBaseline = 'middle';
  rows.forEach((r, i) => g2.fillText(r, W / 2, y + pad * 0.7 + lh * (i + 0.5)));
  if (l.note) {   // 작은 설명 (예: 어떤 스킬인지)
    g2.font = '700 30px Wanted'; g2.fillStyle = 'rgba(0,0,0,0.55)';
    const nw = g2.measureText(l.note).width + 28; g2.fillRect((W - nw) / 2, y + h + 14, nw, 46);
    g2.fillStyle = '#00FF66'; g2.fillText(l.note, W / 2, y + h + 37);
  }
}

// 카드: tag(왼쪽 위 작은 글자) / time("3시간 뒤" 화면 전체) / end(마지막 안내)
function cards(t) {
  for (const c of S.cards || []) {
    if (t < c.t || t > c.t + (c.d || 1)) continue;
    const u = Math.min(1, (t - c.t) / 0.15, (c.t + (c.d || 1) - t) / 0.15);
    g2.save(); g2.globalAlpha = clamp(u); g2.textAlign = 'center'; g2.textBaseline = 'middle';
    if (c.kind === 'tag') {
      g2.font = '700 34px Wanted'; g2.textAlign = 'left';
      g2.fillStyle = 'rgba(0,0,0,0.55)'; g2.fillRect(64, 296, g2.measureText(c.text).width + 32, 54);
      g2.fillStyle = '#00FF66'; g2.fillText(c.text, 80, 324);
    } else if (c.kind === 'title') {   // 훅 제목 (위쪽, 초록 큰 글자, 리트냥이 2026-11-18)
      g2.font = '700 62px Wanted';
      const rows = wrap(c.text, 900), lh = 80, w = Math.max(...rows.map((r) => g2.measureText(r).width)) + 56;
      g2.fillStyle = 'rgba(0,0,0,0.82)'; g2.fillRect((W - w) / 2, 300, w, rows.length * lh + 34);
      g2.fillStyle = '#00FF66'; rows.forEach((r, i) => g2.fillText(r, W / 2, 300 + 17 + lh * (i + 0.5)));
    } else if (c.kind === 'sub') {     // 화면 속 영상의 말 자막 (대사 자막과 같은 자리·모양)
      g2.font = '700 50px Wanted';
      const rows = wrap(c.text, 780), lh = 66, pad = 26, w = Math.max(...rows.map((r) => g2.measureText(r).width)) + pad * 2, h = rows.length * lh + pad * 1.4;
      const y = c.y || 360;
      g2.fillStyle = 'rgba(0,0,0,0.62)'; g2.beginPath(); g2.roundRect((W - w) / 2, y, w, h, 14); g2.fill();
      g2.fillStyle = '#fff'; rows.forEach((r, i) => g2.fillText(r, W / 2, y + pad * 0.7 + lh * (i + 0.5)));
    } else if (c.kind === 'time') {
      g2.fillStyle = 'rgba(0,0,0,0.88)'; g2.fillRect(0, 0, W, H);
      g2.font = '700 96px Wanted'; g2.fillStyle = '#fff'; g2.fillText(c.text, W / 2, H / 2 - 40);
    } else {   // 끝: 화면 전환 → 빈 검은 화면에 안내 (운영자 2026-11-18)
      g2.globalAlpha = 1; g2.fillStyle = `rgba(0,0,0,${clamp(u * 1.2)})`; g2.fillRect(0, 0, W, H);
      g2.globalAlpha = clamp(u);
      const [head, ...rest] = c.text.split('|');
      g2.font = '700 64px Wanted'; g2.fillStyle = '#00FF66';
      const hr = wrap(head, 880); hr.forEach((r, i) => g2.fillText(r, W / 2, 820 + i * 84));
      g2.font = '700 46px Wanted'; g2.fillStyle = '#ffffff';
      rest.forEach((r, i) => g2.fillText(r, W / 2, 820 + hr.length * 84 + 40 + i * 64));
    }
    g2.restore();
  }
}

window.twFrame = (t) => {
  if (PHONE.g) updatePhone(t);
  for (const k in cast) (cast[k].human ? animHuman : animAI)(cast[k], t);
  if (REMOTE.btn) {   // 리모컨 빨간 버튼: 눌린 동안 들어가고 빛남
    const on = S.events.some((e) => e.do === 'press' && t >= e.t + 0.3 && t < e.t + 0.62);
    REMOTE.btn.position.y = on ? 0.008 : 0.012; REMOTE.btnMat.emissiveIntensity = on ? 2.2 : 0.0;
  }
  const cam = camFor(shotAt(t), t);
  camera.position.copy(cam.pos); camera.lookAt(cam.look); camera.updateMatrixWorld();
  const near = cam.near || 0.05;
  if (camera.near !== near) { camera.near = near; camera.updateProjectionMatrix(); if (bokeh.uniforms.nearClip) bokeh.uniforms.nearClip.value = near; }
  let credit = null;
  for (const name in SCR) {
    const clip = drawScreen(SCR[name], name, t);
    if (!clip || credit) continue;
    const vis = (name === 'phone' && cam.phone !== undefined) || screenVisible(SCR[name]);
    const seen = CREDIT_SEEN[clip] || { d: 0, t: -1 };
    if (vis && seen.d < 1.6) { credit = S.clips[clip].credit; if (seen.t !== t) { seen.d += 1 / S.fps; seen.t = t; } }
    CREDIT_SEEN[clip] = seen;
  }
  bokeh.uniforms.focus.value = camera.position.distanceTo(cam.focus);
  bokeh.uniforms.aperture.value = cam.ap; bokeh.uniforms.maxblur.value = 0.014;
  composer.render();
  g2.drawImage(renderer.domElement, 0, 0, W, H);
  if (cam.phone !== undefined && SCR.phone) {   // 첫 장면: 젠슨 폰 화면 클로즈업 → 천천히 물러남
    const s = lerp(1.08, 0.74, ease(cam.phone)), pw = W * s, ph = pw * 16 / 9, bz = 26 * s;
    const x = (W - pw) / 2, y = (H - ph) / 2 + 40 * ease(cam.phone);
    g2.save(); g2.fillStyle = '#0d0e11'; g2.beginPath(); g2.roundRect(x - bz, y - bz * 2.4, pw + bz * 2, ph + bz * 4.8, 70 * s); g2.fill();
    g2.beginPath(); g2.roundRect(x, y, pw, ph, 44 * s); g2.clip(); g2.drawImage(SCR.phone.cv, x, y, pw, ph); g2.restore();
  }
  caption(t);
  if (credit) {   // 화면 속 릴스 출처
    g2.font = '700 26px Wanted'; g2.textAlign = 'left'; g2.textBaseline = 'middle';
    g2.fillStyle = 'rgba(0,0,0,0.5)'; const tx = `영상 출처: ${credit}`; g2.fillRect(64, 1196, g2.measureText(tx).width + 24, 40);
    g2.fillStyle = 'rgba(255,255,255,0.9)'; g2.fillText(tx, 76, 1216);
  }
  cards(t);
  return out.toDataURL('image/jpeg', 0.92);
};
window.twReady = true;
