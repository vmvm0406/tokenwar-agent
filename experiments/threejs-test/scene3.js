// v3 (2026-11-17): 사람 주인공 '나'(20대 여성 직장인, 비닐 피규어풍) + 클로드·제미나이·챗GPT. 슬라임 없음(운영자 결정).
// scene.js(v2)의 공통 부분(노이즈·점토·얼굴·클로드·제미나이·책상·자막)을 복사해 쓰고, 아래쪽에 사람·챗GPT·장면·카메라가 새로 있다.
// 모든 움직임은 시각 t의 함수 → render.py --v3가 twFrame(t)를 프레임마다 부른다. 비공식 팬 캐릭터.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

const W = 1080, H = 1920;
const T0 = 0.5;          // 대사 시작
const DUR = 7.5;
let LINE = null;          // ElevenLabs 글자 시각 {text, chars, starts, ends}

// ---------- 결정적 난수·노이즈 ----------
let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
const hash = (x, y, z) => { const h = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return h - Math.floor(h); };
const sm = (a) => a * a * (3 - 2 * a);
function noise3(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = sm(x - xi), yf = sm(y - yi), zf = sm(z - zi);
  const l = (a, b, t) => a + (b - a) * t;
  const c = (i, j, k) => hash(xi + i, yi + j, zi + k);
  return l(l(l(c(0,0,0), c(1,0,0), xf), l(c(0,1,0), c(1,1,0), xf), yf),
           l(l(c(0,0,1), c(1,0,1), xf), l(c(0,1,1), c(1,1,1), xf), yf), zf);
}
// 점토 느낌: 법선 방향으로 작은 노이즈 (손으로 빚은 울퉁불퉁함)
function clay(geo, amp = 0.006, freq = 9, s = 0) {
  geo.deleteAttribute('uv');
  geo = mergeVertices(geo);
  geo.computeVertexNormals();
  const p = geo.attributes.position, n = geo.attributes.normal;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const d = amp * ((noise3(x * freq + s, y * freq, z * freq) - 0.5) * 2 + 0.5 * (noise3(x * freq * 3, y * freq * 3 + s, z * freq * 3) - 0.5));
    p.setXYZ(i, x + n.getX(i) * d, y + n.getY(i) * d, z + n.getZ(i) * d);
  }
  geo.computeVertexNormals();
  return geo;
}

// ---------- 시간 함수 ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const lerp = (a, b, t) => a + (b - a) * t;
function blink(t, times) {
  let s = 1;
  for (const b of times) { const d = Math.abs(t - b); if (d < 0.09) s = Math.min(s, 0.08 + 0.92 * (d / 0.09) ** 2); }
  return s;
}
// 점프: 웅크림(0.12초) → 공중(늘어남) → 착지 찌그러짐
function hop(t, t0, h = 0.18, air = 0.34) {
  const pre = 0.12, u = (t - t0) / air;
  if (t < t0 - pre) return { y: 0, sq: 0 };
  if (t < t0) return { y: 0, sq: -0.13 * Math.sin(Math.PI / 2 * (t - (t0 - pre)) / pre) };
  if (u < 1) return { y: h * Math.sin(Math.PI * u), sq: 0.12 * (1 - u) - 0.04 };
  const l = (t - t0 - air) / 0.22;
  if (l < 1) return { y: 0, sq: -0.16 * Math.sin(Math.PI * l) * (1 - l * 0.5) };
  return { y: 0, sq: 0 };
}
const addHop = (a, b) => ({ y: a.y + b.y, sq: a.sq + b.sq });

// ---------- 재질 ----------
const clayMat = (c, sheen = 0xffffff) => new THREE.MeshPhysicalMaterial({
  color: c, roughness: 0.62, sheen: 0.6, sheenRoughness: 0.7, sheenColor: new THREE.Color(sheen), clearcoat: 0.08, clearcoatRoughness: 0.6 });
const eyeMat = new THREE.MeshPhysicalMaterial({ color: 0x0b0b0e, roughness: 0.18, clearcoat: 1, clearcoatRoughness: 0.05 });
const mouthMat = new THREE.MeshPhysicalMaterial({ color: 0x141012, roughness: 0.4 });
const innerMat = new THREE.MeshStandardMaterial({ color: 0x3a0d12, roughness: 0.8 });

function lathe(profile, seg = 48) { return new THREE.LatheGeometry(profile.map(([x, y]) => new THREE.Vector2(x, y)), seg); }
// 아래가 납작하고 위가 둥근 젤리곰·점토 몸통 윤곽
function gumdrop(R, bottom, top, pw = 0.55, n = 36) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const th = -Math.PI / 2 + Math.PI * i / n;
    const x = R * Math.pow(Math.max(0, Math.cos(th)), pw);
    const y = th < 0 ? bottom + bottom * Math.sin(th) : bottom + top * Math.sin(th);
    pts.push([Math.max(x, 1e-4), y]);
  }
  pts[0][0] = 1e-4; pts[n][0] = 1e-4;
  return pts;
}
function capsule(r, len, mat) { return new THREE.Mesh(clay(new THREE.CapsuleGeometry(r, len, 8, 16), 0.004, 14), mat); }

// 얼굴: 눈 2 + 웃는 입 + 벌린 입 + 행복한 눈(^ ^)
// surf(x, y) → {z, rx, ry}: 몸 표면의 앞쪽 z와 기울기. 있으면 눈·입을 표면 위로 살짝 돋게(데칼 아님) 붙이고 표면 방향으로 돌린다.
// 얼굴 부품은 불투명 + 몸(투과 젤리)보다 나중에 그림(renderOrder) → 어느 각도·프레임에서도 젤리 안으로 묻히지 않음.
function face(group, { ex, ey, ez, er, my, mz, mr, surf = null }) {
  const eyes = [], happy = [];
  const place = (o, x, y, z, lift) => {
    if (surf) { const s = surf(x, y); o.position.set(x, y, s.z + lift); o.rotation.x = s.rx; o.rotation.y = s.ry; }
    else o.position.set(x, y, z);
    o.renderOrder = 3; group.add(o);
  };
  for (const sx of [-1, 1]) {
    const e = new THREE.Mesh(new THREE.SphereGeometry(er, 24, 16), eyeMat);
    e.scale.set(1, 1.15, 0.55); place(e, sx * ex, ey, ez, er * 0.12); eyes.push(e);
    const h = new THREE.Mesh(new THREE.TorusGeometry(er * 0.9, er * 0.3, 8, 20, Math.PI), eyeMat);
    place(h, sx * ex, ey - er * 0.3, ez, er * 0.3); h.visible = false; happy.push(h);
  }
  const smile = new THREE.Mesh(new THREE.TorusGeometry(mr, mr * (surf ? 0.3 : 0.24), 10, 24, Math.PI * 0.8), mouthMat);
  place(smile, 0, my + mr * 0.5, mz, mr * 0.3);
  smile.rotation.z = Math.PI + Math.PI * 0.1;
  const open = new THREE.Mesh(new THREE.SphereGeometry(mr * 1.25, 20, 14), innerMat);
  place(open, 0, my, mz - 0.005, surf ? mr * 0.15 : 0); open.visible = false;
  return { eyes, happy, smile, open, eyeScale: 1.15 };
}
function setFace(f, { blinkS = 1, happy = false, open = 0 }) {
  f.eyes.forEach((e) => { e.visible = !happy; e.scale.y = f.eyeScale * blinkS; });
  f.happy.forEach((h) => { h.visible = happy; });
  f.smile.visible = open < 0.12; f.open.visible = open >= 0.12;
  f.open.scale.set(1, 0.35 + open * 0.95, 0.45);
}

// ---------- 캐릭터 ----------
function makeSlime() {
  const root = new THREE.Group(), sq = new THREE.Group(); root.add(sq);
  const jelly = new THREE.MeshPhysicalMaterial({
    color: 0xd8ff86, transmission: 0.78, thickness: 0.6, roughness: 0.06, ior: 1.33, clearcoat: 1, clearcoatRoughness: 0.03,
    attenuationColor: new THREE.Color(0xb6f25a), attenuationDistance: 2.2, specularIntensity: 1, emissive: new THREE.Color(0x3d6a08), emissiveIntensity: 0.55,
    sheen: 0.4, sheenColor: new THREE.Color(0xeaffc0) });
  const body = new THREE.Mesh(lathe(gumdrop(0.42, 0.17, 0.6, 0.5), 64), jelly);
  body.castShadow = true; sq.add(body);
  for (const sx of [-1, 1]) {
    const ear = new THREE.Mesh(lathe([[1e-4, 0], [0.13, 0], [0.12, 0.06], [0.07, 0.15], [0.02, 0.2], [1e-4, 0.205]], 32), jelly);
    ear.position.set(sx * 0.21, 0.62, -0.02); ear.rotation.z = -sx * 0.42; ear.scale.z = 0.7; ear.castShadow = true; sq.add(ear);
  }
  // 안쪽 기포 (투과 재질 안에서 보이도록 불투명)
  const bub = new THREE.MeshStandardMaterial({ color: 0xf4ffe0, roughness: 0.2, emissive: 0x334411 });
  [[-0.2, 0.22, 0.1, 0.03], [0.17, 0.15, 0.12, 0.022], [0.06, 0.55, -0.05, 0.018], [-0.08, 0.1, -0.15, 0.025]].forEach(([x, y, z, r]) => {
    const b = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 10), bub); b.position.set(x, y, z); sq.add(b);
  });
  const head = new THREE.Group(); sq.add(head);
  // 몸 윤곽(gumdrop 0.42/0.17/0.6/0.5)에서 높이 y의 반지름 → 앞 표면 z
  const rAt = (y) => { const sn = clamp((y - 0.17) / 0.6, -1, 1); return 0.42 * Math.pow(Math.max(0, Math.sqrt(1 - sn * sn)), 0.5); };
  const surf = (x, y) => {
    const r = rAt(y), z = Math.sqrt(Math.max(1e-6, r * r - x * x));
    const dr = (rAt(y + 0.01) - rAt(y - 0.01)) / 0.02;
    return { z, ry: Math.asin(clamp(x / r, -1, 1)), rx: Math.atan(dr) };
  };
  const f = face(head, { ex: 0.12, ey: 0.46, er: 0.042, my: 0.36, mr: 0.045, surf });
  return { root, sq, head, face: f };
}

// 클로드: 햇살(버스트) 모양 머리 + 둥근 몸통·팔·다리. 주황 테라코타 점토.
function makeClaude() {
  const m = clayMat(0xd2693f, 0xffb08a);
  const root = new THREE.Group(), sq = new THREE.Group(); root.add(sq);
  for (const sx of [-1, 1]) {
    const leg = capsule(0.065, 0.08, m); leg.position.set(sx * 0.1, 0.1, 0); sq.add(leg);
    const foot = new THREE.Mesh(clay(new THREE.SphereGeometry(0.075, 24, 16), 0.004, 14, sx), m);
    foot.scale.set(1, 0.6, 1.25); foot.position.set(sx * 0.1, 0.035, 0.03); sq.add(foot);
  }
  const body = new THREE.Mesh(clay(lathe(gumdrop(0.27, 0.1, 0.32, 0.6)), 0.007, 8, 1), m);
  body.position.y = 0.1; body.castShadow = true; sq.add(body);
  const arms = [];
  for (const sx of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(sx * 0.24, 0.36, 0); sq.add(pivot);
    const a = capsule(0.055, 0.12, m); a.position.set(sx * 0.05, -0.08, 0); pivot.add(a); pivot.rotation.z = sx * 0.45; arms.push(pivot);
  }
  const head = new THREE.Group(); head.position.y = 0.62; sq.add(head);
  const core = new THREE.Mesh(clay(new THREE.SphereGeometry(0.3, 48, 32), 0.008, 7, 2), m);
  core.scale.set(1.12, 0.92, 0.82); core.castShadow = true; head.add(core);
  // 햇살 갈래: 둥근 끝의 굵은 갈래 12개 (머리 둘레 전체)
  for (let k = 0; k < 12; k++) {
    const a = Math.PI / 2 + k * Math.PI * 2 / 12 + 0.13;
    const ray = new THREE.Mesh(clay(new THREE.CapsuleGeometry(0.075, 0.07, 6, 14), 0.006, 10, k), m);
    const rr = 0.33;
    ray.position.set(Math.cos(a) * rr * 1.12, Math.sin(a) * rr * 0.95, -0.03);
    ray.rotation.z = a - Math.PI / 2; ray.scale.set(1, 1, 0.7); ray.castShadow = true; head.add(ray);
  }
  const f = face(head, { ex: 0.1, ey: 0.02, ez: 0.245, er: 0.034, my: -0.07, mz: 0.248, mr: 0.035 });
  return { root, sq, head, face: f, arms };
}

// 제미나이: 오목한 4갈래 반짝이 별 몸통(파랑→보라 그라데이션) + 짧은 팔다리 + 작은 반짝이
// 오목한 4갈래 반짝이: 아스트로이드(|x|^q+|y|^q=R^q, q<1) + 원을 조금 섞어 끝을 둥글게
function sparkleShape(Rout, Rin, n = 4, pw = 3.0, steps = 240) {
  const s = new THREE.Shape(), mix = Rin / Rout;
  for (let i = 0; i <= steps; i++) {
    const th = Math.PI * 2 * i / steps, c = Math.cos(th), sn = Math.sin(th);
    const ax = Math.sign(c) * Math.abs(c) ** pw, ay = Math.sign(sn) * Math.abs(sn) ** pw;
    const x = Rout * ((1 - mix) * ax + mix * c), y = Rout * 1.08 * ((1 - mix) * ay + mix * sn);
    i ? s.lineTo(x, y) : s.moveTo(x, y);
  }
  return s;
}
function gradient(geo, top, bottom) {
  geo.computeBoundingBox();
  const { min, max } = geo.boundingBox, p = geo.attributes.position, c = [];
  const a = new THREE.Color(top), b = new THREE.Color(bottom), t = new THREE.Color();
  for (let i = 0; i < p.count; i++) { t.copy(b).lerp(a, (p.getY(i) - min.y) / (max.y - min.y)); c.push(t.r, t.g, t.b); }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(c, 3));
}
function makeGemini() {
  const root = new THREE.Group(), sq = new THREE.Group(); root.add(sq);
  const limb = clayMat(0x7a5cf0, 0xc9b8ff);
  for (const sx of [-1, 1]) {
    const leg = capsule(0.06, 0.08, limb); leg.position.set(sx * 0.1, 0.09, 0); sq.add(leg);
    const foot = new THREE.Mesh(clay(new THREE.SphereGeometry(0.07, 24, 16), 0.004, 14, sx), limb);
    foot.scale.set(1, 0.6, 1.25); foot.position.set(sx * 0.1, 0.033, 0.03); sq.add(foot);
  }
  let g = new THREE.ExtrudeGeometry(sparkleShape(0.46, 0.1, 4, 3.4), { depth: 0.16, bevelEnabled: true, bevelThickness: 0.11, bevelSize: 0.09, bevelSegments: 8, curveSegments: 1 });
  g.center(); g = clay(g, 0.006, 8, 3); gradient(g, 0x4f9dff, 0x8a4dff);
  const starMat = clayMat(0xffffff, 0xd6e4ff); starMat.vertexColors = true;
  const head = new THREE.Group(); head.position.y = 0.6; sq.add(head);
  const star = new THREE.Mesh(g, starMat); star.castShadow = true; head.add(star);
  const arms = [];
  for (const sx of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(sx * 0.2, -0.12, 0.02); head.add(pivot);
    const a = capsule(0.05, 0.1, limb); a.position.set(sx * 0.05, -0.06, 0); pivot.add(a); pivot.rotation.z = sx * 0.6; arms.push(pivot);
  }
  const f = face(head, { ex: 0.085, ey: 0.03, ez: 0.19, er: 0.032, my: -0.06, mz: 0.192, mr: 0.033 });
  let sg = new THREE.ExtrudeGeometry(sparkleShape(0.13, 0.03, 4, 3.6), { depth: 0.03, bevelEnabled: true, bevelThickness: 0.025, bevelSize: 0.02, bevelSegments: 4, curveSegments: 1 });
  sg.center(); sg = clay(sg, 0.002, 20, 5);
  const spark = new THREE.Mesh(sg, clayMat(0x6d58ff, 0xb9a8ff)); spark.position.set(0.42, 0.5, 0); head.add(spark);
  return { root, sq, head, face: f, arms, spark };
}

// ---------- 책상 장면 ----------
function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
function buildDesk(scene) {
  const wood = canvasTex(1024, 512, (g, w, h) => {
    g.fillStyle = '#8d5c3a'; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 140; i++) {
      const y = rnd() * h, a = 0.04 + rnd() * 0.08;
      g.strokeStyle = rnd() < 0.5 ? `rgba(60,30,15,${a})` : `rgba(200,140,90,${a})`; g.lineWidth = 1 + rnd() * 4;
      g.beginPath(); for (let x = 0; x <= w; x += 16) g.lineTo(x, y + Math.sin(x / 90 + y) * 6); g.stroke();
    }
  });
  const desk = new THREE.Mesh(new RoundedBoxGeometry(6, 0.14, 3.2, 4, 0.05), new THREE.MeshPhysicalMaterial({ map: wood, roughness: 0.55, clearcoat: 0.25, clearcoatRoughness: 0.4 }));
  desk.position.set(0, -0.07, 0.2); desk.receiveShadow = true; scene.add(desk);
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(14, 8), new THREE.MeshStandardMaterial({ color: 0x3b2c23, roughness: 0.95 }));
  wall.position.set(0, 2, -2.6); wall.receiveShadow = true; scene.add(wall);
  // 벽 꼬마전구 (흐림 → 보케)
  for (let i = 0; i < 26; i++) {
    const x = -3.4 + i * 0.27, y = 2.3 - 0.35 * Math.sin(Math.PI * ((i % 13) / 12)) + (i >= 13 ? -0.15 : 0);
    const warm = i % 7 === 3 ? new THREE.Color(0x00ff66).multiplyScalar(2.2) : new THREE.Color(0xffc46b).multiplyScalar(3.2);
    const b = new THREE.Mesh(new THREE.SphereGeometry(0.035, 12, 8), new THREE.MeshBasicMaterial({ color: warm }));
    b.position.set(x, y, -2.5); scene.add(b);
  }
  // 모니터
  const scr = canvasTex(1024, 600, (g, w, h) => {
    g.fillStyle = '#050806'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#00ff66'; g.font = 'bold 54px Wanted, sans-serif'; g.fillText('TOKEN WAR', 60, 110);
    for (let i = 0; i < 9; i++) { const bh = 60 + 330 * Math.abs(Math.sin(i * 1.7)); g.globalAlpha = 0.35 + 0.07 * i; g.fillRect(70 + i * 100, h - 60 - bh, 62, bh); }
    g.globalAlpha = 1;
  });
  const mon = new THREE.Group(); mon.position.set(-0.55, 0, -1.25); mon.rotation.y = 0.22; scene.add(mon);
  const darkPlastic = new THREE.MeshPhysicalMaterial({ color: 0x1b1c1f, roughness: 0.45, clearcoat: 0.3 });
  const frame = new THREE.Mesh(new RoundedBoxGeometry(1.7, 1.02, 0.07, 4, 0.03), darkPlastic); frame.position.y = 1.08; frame.castShadow = true; mon.add(frame);
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.92), new THREE.MeshBasicMaterial({ map: scr, toneMapped: true }));
  screen.position.set(0, 1.08, 0.037); mon.add(screen);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.05, 0.55, 16), darkPlastic); neck.position.y = 0.3; mon.add(neck);
  const foot = new THREE.Mesh(new RoundedBoxGeometry(0.5, 0.03, 0.3, 2, 0.012), darkPlastic); foot.position.y = 0.015; mon.add(foot);
  const glow = new THREE.PointLight(0x00ff66, 0.6, 2.2, 2); glow.position.set(-0.4, 1.0, -0.9); scene.add(glow);
  // 머그컵
  const mug = new THREE.Group(); mug.position.set(1.45, 0, 0.1); scene.add(mug);
  const cer = new THREE.MeshPhysicalMaterial({ color: 0xeee6da, roughness: 0.25, clearcoat: 0.6 });
  const prof = [[1e-4, 0], [0.16, 0], [0.17, 0.01], [0.17, 0.34], [0.155, 0.34], [0.155, 0.02], [1e-4, 0.02]];
  const cup = new THREE.Mesh(lathe(prof, 48), cer); cup.castShadow = true; mug.add(cup);
  const band = new THREE.Mesh(new THREE.CylinderGeometry(0.1715, 0.1715, 0.05, 48, 1, true), new THREE.MeshPhysicalMaterial({ color: 0x00c853, roughness: 0.3, clearcoat: 0.6 }));
  band.position.y = 0.24; mug.add(band);
  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.075, 0.022, 12, 24, Math.PI * 1.2), cer);
  handle.position.set(0.17, 0.17, 0); handle.rotation.z = -Math.PI * 0.6; mug.add(handle);
  const coffee = new THREE.Mesh(new THREE.CircleGeometry(0.155, 32), new THREE.MeshPhysicalMaterial({ color: 0x2a160c, roughness: 0.1, clearcoat: 1 }));
  coffee.rotation.x = -Math.PI / 2; coffee.position.y = 0.3; mug.add(coffee);
  // 앞쪽 키보드 (전경 흐림)
  const kb = new THREE.Mesh(new RoundedBoxGeometry(1.5, 0.05, 0.5, 2, 0.02), new THREE.MeshPhysicalMaterial({ color: 0xd9d4cc, roughness: 0.5 }));
  kb.position.set(-0.2, 0.025, 1.45); kb.rotation.y = -0.08; kb.castShadow = true; scene.add(kb);
  const keys = new THREE.InstancedMesh(new RoundedBoxGeometry(0.09, 0.035, 0.09, 2, 0.012), new THREE.MeshPhysicalMaterial({ color: 0xf5f2ec, roughness: 0.45 }), 60);
  let k = 0; const m4 = new THREE.Matrix4();
  for (let r = 0; r < 4; r++) for (let c = 0; c < 15; c++) { m4.makeTranslation(-0.66 + c * 0.095, 0.06, -0.16 + r * 0.105); keys.setMatrixAt(k++, m4); }
  kb.add(keys); keys.position.y = -0.025;
}
// 발밑 접지 그림자 (부드러운 원형, 높이 뜨면 옅어짐)
const blobTex = canvasTex(128, 128, (g) => {
  const gr = g.createRadialGradient(64, 64, 4, 64, 64, 62); gr.addColorStop(0, 'rgba(0,0,0,0.75)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
});
function blob(scene, r) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(r * 2, r * 2), new THREE.MeshBasicMaterial({ map: blobTex, transparent: true, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.position.y = 0.002; scene.add(m); return m;
}

// ---------- 화면 글 (2D 겹치기) ----------
const out = document.createElement('canvas'); out.width = W; out.height = H; document.body.appendChild(out);
const g2 = out.getContext('2d');
function wrap(text, px, maxW) {
  g2.font = `700 ${px}px Wanted`;
  if (g2.measureText(text).width <= maxW) return [text];
  const i = text.indexOf(', ');
  return i > 0 ? [text.slice(0, i + 1), text.slice(i + 2)] : [text];
}
function overlay(t) {
  // 위 라벨 띠: 녹색 칸 + 시리즈 표시 (안전 영역 안)
  const y = 300;
  g2.fillStyle = 'rgba(0,0,0,0.82)'; g2.fillRect(65, y, 950, 76);
  g2.fillStyle = '#00FF66'; g2.fillRect(65, y, 214, 76);
  g2.fillStyle = '#000'; g2.font = '44px "Black Han Sans"'; g2.textBaseline = 'middle'; g2.fillText('토큰전쟁', 85, y + 40);
  g2.fillStyle = '#fff'; g2.font = '700 38px Wanted'; g2.fillText('AI 셋이 모이면', 302, y + 40);
  g2.fillStyle = 'rgba(255,255,255,0.55)'; g2.font = '600 24px Wanted'; g2.fillText('비공식 팬 캐릭터', 830, y + 41);
  // 자막 상자: 흰 네모 + 검은 글자 (말하는 동안)
  const sub = subtitleAt(t);
  if (sub) {
    const px = 50, lines = wrap(sub, px, 860), lh = px * 1.3;
    g2.font = `700 ${px}px Wanted`;
    const bw = Math.max(...lines.map((l) => g2.measureText(l).width)) + 56, bh = lines.length * lh + 30;
    const by = 1120 - bh;   // 아래 끝 1120: 오른쪽 아래 버튼 줄(y 1150~)보다 위
    g2.fillStyle = '#fff'; g2.fillRect(540 - bw / 2, by, bw, bh);
    g2.fillStyle = '#0a0a0a'; g2.textAlign = 'center';
    lines.forEach((l, i) => g2.fillText(l, 540, by + 15 + lh * (i + 0.5) + 2));
    g2.textAlign = 'left';
  }
}

// ---------- 대사 시각 ----------
let PH = [];   // [{text, t0, t1}]
function wordWindow(word) {
  const i = LINE.text.indexOf(word);
  return [T0 + LINE.starts[i], T0 + LINE.ends[i + word.length - 1]];
}
function buildPhrases() {
  const cut = LINE.text.indexOf('!') + 1;
  const a = LINE.text.slice(0, cut).trim(), b = LINE.text.slice(cut).trim();
  const bStart = T0 + LINE.starts[LINE.text.indexOf(b)];
  PH = [{ text: a, t0: T0 - 0.05, t1: bStart - 0.02 }, { text: b, t0: bStart - 0.02, t1: T0 + LINE.ends.at(-1) + 0.6 }];
}
function subtitleAt(t) { for (const p of PH) if (t >= p.t0 && t < p.t1) return p.text; return null; }
const isSyl = (ch) => /[가-힣A-Za-z]/.test(ch);
function mouthOpen(t) {
  const tt = t - T0; let o = 0;
  for (let i = 0; i < LINE.chars.length; i++) {
    if (!isSyl(LINE.chars[i])) continue;
    const s = LINE.starts[i], e = Math.max(LINE.ends[i], s + 0.06);
    if (tt >= s && tt <= e) o = Math.max(o, 0.25 + 0.75 * Math.sin(Math.PI * (tt - s) / (e - s)));
  }
  return o;
}


// ---------- v3 새 캐릭터 ----------
// 타원체 표면(반지름 R, 축 배율 a,b,c) 위 (x, y)의 앞쪽 z와 기울기 → face()의 surf
const ellSurf = (R, a, b, c, cy = 0) => (x, y) => {
  const u = x / (R * a), v = (y - cy) / (R * b), w = Math.sqrt(Math.max(0.02, 1 - u * u - v * v));
  return { z: R * c * w, ry: Math.atan2(u * c / a, w), rx: -Math.atan2(v * c / b, w) };
};

// '나': 20대 여성 직장인, 비닐 피규어풍. 큰 둥근 머리 + 단발 + 네이비 후드티 + 사원증 목걸이. 사실적인 얼굴 없음(점 눈·돋은 입).
function makeHuman() {
  const skin = clayMat(0xf2c8a4, 0xffe4d0); skin.roughness = 0.5; skin.clearcoat = 0.25; skin.clearcoatRoughness = 0.35;
  const hair = new THREE.MeshPhysicalMaterial({ color: 0x241815, roughness: 0.42, clearcoat: 0.15, clearcoatRoughness: 0.5, side: THREE.DoubleSide });
  const hood = clayMat(0x34466e, 0x8fa3d0), pants = clayMat(0xd2c2a5), shoe = clayMat(0xf4f2ee), white = clayMat(0xfafaf7);
  const green = new THREE.MeshPhysicalMaterial({ color: 0x00c853, roughness: 0.5 });
  const root = new THREE.Group(), sq = new THREE.Group(); root.add(sq);
  for (const sx of [-1, 1]) {
    const leg = capsule(0.068, 0.12, pants); leg.position.set(sx * 0.085, 0.14, 0); sq.add(leg);
    const sh = new THREE.Mesh(clay(new THREE.SphereGeometry(0.075, 24, 16), 0.003, 14, sx), shoe);
    sh.scale.set(1, 0.55, 1.45); sh.position.set(sx * 0.085, 0.04, 0.035); sq.add(sh);
  }
  const body = new THREE.Mesh(clay(lathe(gumdrop(0.24, 0.1, 0.32, 0.7)), 0.004, 9, 4), hood);
  body.position.y = 0.19; body.scale.z = 0.9; sq.add(body);
  const pocket = new THREE.Mesh(new RoundedBoxGeometry(0.24, 0.08, 0.03, 3, 0.012), hood); pocket.position.set(0, 0.3, 0.205); pocket.rotation.x = -0.15; sq.add(pocket);
  const collar = new THREE.Mesh(new THREE.TorusGeometry(0.13, 0.05, 14, 32), hood); collar.rotation.x = Math.PI / 2 - 0.2; collar.position.set(0, 0.58, -0.02); sq.add(collar);
  for (const sx of [-1, 1]) { const s = capsule(0.008, 0.08, white); s.position.set(sx * 0.05, 0.5, 0.18); sq.add(s); }
  // 사원증 목걸이 (녹색 줄 + 흰 카드)
  const strap = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.009, 8, 40, Math.PI), green);
  strap.rotation.z = Math.PI; strap.rotation.x = -0.35; strap.position.set(0, 0.6, 0.12); sq.add(strap);
  const card = new THREE.Mesh(new RoundedBoxGeometry(0.085, 0.11, 0.012, 2, 0.006), white); card.position.set(0, 0.43, 0.215); card.rotation.x = -0.12; sq.add(card);
  const band = new THREE.Mesh(new THREE.BoxGeometry(0.086, 0.022, 0.013), green); band.position.set(0, 0.465, 0.216); band.rotation.x = -0.12; sq.add(band);
  const arms = [];
  for (const sx of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(sx * 0.22, 0.54, 0); sq.add(pivot);
    const a = capsule(0.055, 0.17, hood); a.position.set(0, -0.12, 0); pivot.add(a);
    const hnd = new THREE.Mesh(clay(new THREE.SphereGeometry(0.05, 20, 14), 0.002, 14, sx), skin); hnd.position.set(0, -0.25, 0.01); pivot.add(hnd);
    pivot.rotation.z = sx * 0.18; arms.push(pivot);
  }
  const head = new THREE.Group(); head.position.y = 0.86; sq.add(head);
  const R = 0.27, A = 1.06, B = 1.0, C = 0.98;
  const skull = new THREE.Mesh(new THREE.SphereGeometry(R, 48, 32), skin); skull.scale.set(A, B, C); head.add(skull);
  for (const sx of [-1, 1]) { const ear = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 12), skin); ear.scale.set(0.5, 1, 0.8); ear.position.set(sx * 0.285, -0.03, 0); head.add(ear); }
  // 단발: 정수리 덮개 + 옆·뒤 단발(앞 140도는 비움) + 옆으로 넘긴 앞머리 + 녹색 머리핀
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.292, 48, 24, 0, Math.PI * 2, 0, Math.PI * 0.4), hair); cap.scale.set(1.07, 1.02, 1.0); head.add(cap);
  const bob = new THREE.Mesh(new THREE.SphereGeometry(0.3, 48, 32, Math.PI / 2 + 0.85, Math.PI * 2 - 1.7, 0, Math.PI * 0.78), hair); bob.scale.set(1.1, 1.0, 1.05); head.add(bob);
  // 앞머리: 이마를 덮는 띠 (눈썹 위까지), 한쪽으로 살짝 넘김
  const bangs = new THREE.Mesh(new THREE.SphereGeometry(0.3, 48, 16, Math.PI / 2 - 1.0, 2.0, 0, Math.PI * 0.36), hair);
  bangs.scale.set(1.07, 1.03, 1.02); bangs.rotation.z = 0.12; head.add(bangs);
  const clip = new THREE.Mesh(new RoundedBoxGeometry(0.09, 0.025, 0.02, 2, 0.008), new THREE.MeshPhysicalMaterial({ color: 0x00ff66, roughness: 0.3, clearcoat: 0.8 }));
  clip.position.set(0.19, 0.13, 0.22); clip.rotation.set(-0.5, 0.5, 0.5); head.add(clip);
  const surf = ellSurf(R, A, B, C);
  const f = face(head, { ex: 0.085, ey: -0.02, er: 0.028, my: -0.105, mr: 0.03, surf });
  const blushM = new THREE.MeshStandardMaterial({ color: 0xf29a95, roughness: 0.9 });
  for (const sx of [-1, 1]) {
    const bl = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 10), blushM); bl.scale.set(1.3, 0.75, 0.25);
    const s = surf(sx * 0.15, -0.075); bl.position.set(sx * 0.15, -0.075, s.z + 0.001); bl.rotation.set(s.rx, s.ry, 0); head.add(bl);
  }
  const brows = [];
  for (const sx of [-1, 1]) {
    const b = capsule(0.008, 0.04, hair); b.rotation.z = Math.PI / 2; const s = surf(sx * 0.09, 0.055);
    b.position.set(sx * 0.09, 0.055, s.z + 0.006); head.add(b); brows.push(b);
  }
  return { root, sq, head, face: f, arms, brows };
}

// 챗GPT: 고리 6개가 맞물린 매듭 꽃(로고 모티프) 머리 겸 몸 + 가운데 얼굴판, 흰 점토 + 짙은 회색 팔다리. 글자 로고 없음.
function makeGPT() {
  const white = clayMat(0xf1f0ec, 0xffffff), dark = clayMat(0x2c2c30, 0x9a9aa2);
  const root = new THREE.Group(), sq = new THREE.Group(); root.add(sq);
  for (const sx of [-1, 1]) {
    const leg = capsule(0.06, 0.08, dark); leg.position.set(sx * 0.1, 0.09, 0); sq.add(leg);
    const foot = new THREE.Mesh(clay(new THREE.SphereGeometry(0.07, 24, 16), 0.004, 14, sx), dark);
    foot.scale.set(1, 0.6, 1.25); foot.position.set(sx * 0.1, 0.033, 0.03); sq.add(foot);
  }
  const head = new THREE.Group(); head.position.y = 0.56; sq.add(head);
  const knot = new THREE.Group(); head.add(knot);   // 매듭 꽃만 따로 돈다 (얼굴은 그대로)
  const ringG = clay(new THREE.TorusGeometry(0.11, 0.05, 16, 48), 0.003, 12, 11);
  for (let k = 0; k < 6; k++) {
    const g = new THREE.Group(); g.rotation.z = k * Math.PI / 3; knot.add(g);
    const r = new THREE.Mesh(ringG, white); r.scale.set(1.6, 1, 1);
    r.position.set(0.05, 0.19, (k % 2 ? 0.025 : -0.025)); r.rotation.set(k % 2 ? 0.22 : -0.22, 0, 0.52); g.add(r);
  }
  const plate = new THREE.Mesh(clay(new THREE.SphereGeometry(0.16, 40, 28), 0.003, 10, 12), white); plate.scale.set(1, 1, 0.6); plate.position.z = 0.03; head.add(plate);
  const fg = new THREE.Group(); fg.position.z = 0.03; head.add(fg);
  const f = face(fg, { ex: 0.055, ey: 0.015, er: 0.024, my: -0.045, mr: 0.024, surf: ellSurf(0.16, 1, 1, 0.6) });
  const arms = [];
  for (const sx of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(sx * 0.25, -0.16, 0); head.add(pivot);
    const a = capsule(0.045, 0.1, dark); a.position.set(sx * 0.04, -0.06, 0); pivot.add(a); pivot.rotation.z = sx * 0.6; arms.push(pivot);
  }
  return { root, sq, head, face: f, arms, knot };
}

// ---------- 조립 ----------
let renderer, composer, bokeh, scene, camera, me, claude, gemini, gpt, blobs, W_C, W_G, W_P, W_HAPPY, W_END;
let OPT = { dof: true, trans: true, shadows: true, msaa: 4, scale: 1 };
const POS = { me: [-0.36, 0, 0.35], claude: [0.08, 0, -0.5], gpt: [0.6, 0.2, -0.8], gemini: [1.08, 0, -0.45] };   // 챗GPT는 책 더미 위(y 0.2)
window.twInit = async (line, opt) => {
  OPT = Object.assign(OPT, opt || {});
  const RW = Math.round(W * OPT.scale / 2) * 2, RH = Math.round(H * OPT.scale / 2) * 2;
  LINE = line; buildPhrases();
  W_C = wordWindow('클로드'); W_G = wordWindow('제미나이'); W_P = wordWindow('지피티'); W_HAPPY = wordWindow('끝낼래'); W_END = T0 + LINE.ends.at(-1);
  await document.fonts.load('44px "Black Han Sans"', '토큰전쟁'); await document.fonts.load('700 50px Wanted', '가A'); await document.fonts.load('600 24px Wanted', '가A');
  renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1); renderer.setSize(RW, RH);
  renderer.shadowMap.enabled = OPT.shadows; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x2a1f19);
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.6;
  const key = new THREE.DirectionalLight(0xffd6a8, 2.6); key.position.set(-2.5, 4, 3); key.castShadow = true;
  Object.assign(key.shadow.camera, { left: -2.5, right: 2.5, top: 2.5, bottom: -2.5, near: 0.5, far: 12 });
  key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; scene.add(key);
  const rim = new THREE.DirectionalLight(0x9fc8ff, 1.4); rim.position.set(2.5, 2.5, -3); scene.add(rim);
  scene.add(new THREE.HemisphereLight(0xffe8d0, 0x3a2418, 0.5));
  buildDesk(scene);
  me = makeHuman(); me.root.position.set(...POS.me); scene.add(me.root);
  claude = makeClaude(); claude.root.position.set(...POS.claude); claude.root.scale.setScalar(0.92); scene.add(claude.root);
  const books = [[0.62, 0.1, 0x2f6f4f], [0.56, 0.1, 0xb8442f]];   // 책 2권 (챗GPT 받침)
  books.forEach(([w, h, c], i) => { const bk = new THREE.Mesh(new RoundedBoxGeometry(w, h, 0.42, 2, 0.015), clayMat(c)); bk.position.set(POS.gpt[0], h / 2 + i * h, POS.gpt[2]); bk.rotation.y = i ? 0.12 : -0.05; bk.castShadow = bk.receiveShadow = true; scene.add(bk); });
  gpt = makeGPT(); gpt.root.position.set(...POS.gpt); gpt.root.scale.setScalar(0.95); gpt.baseY = POS.gpt[1]; scene.add(gpt.root);
  gemini = makeGemini(); gemini.root.position.set(...POS.gemini); gemini.root.scale.setScalar(0.88); scene.add(gemini.root);
  [me, claude, gpt, gemini].forEach((c) => c.root.traverse((o) => { if (o.isMesh) o.castShadow = true; }));
  blobs = [[me, blob(scene, 0.42)], [claude, blob(scene, 0.42)], [gpt, blob(scene, 0.4)], [gemini, blob(scene, 0.4)]];
  camera = new THREE.PerspectiveCamera(42, W / H, 0.1, 40);
  const rt = new THREE.WebGLRenderTarget(RW, RH, { type: THREE.HalfFloatType, samples: OPT.msaa });
  composer = new EffectComposer(renderer, rt); composer.setPixelRatio(1); composer.setSize(RW, RH);
  composer.addPass(new RenderPass(scene, camera));
  bokeh = new BokehPass(scene, camera, { focus: 5, aperture: 0.003, maxblur: 0.012 }); bokeh.enabled = OPT.dof; composer.addPass(bokeh);
  composer.addPass(new OutputPass());
  const gl = renderer.getContext(), dbg = gl.getExtension('WEBGL_debug_renderer_info');
  return { renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), webgl2: renderer.capabilities.isWebGL2 };
};

const CAM = [   // [시각, 위치, 바라보는 곳, 초점 대상, 조리개]
  [0.0, [0.2, 1.6, 5.6], [0.22, 0.42, -0.2], 'ais', 0.0016],
  [2.3, [0.18, 1.55, 5.3], [0.22, 0.42, -0.2], 'ais', 0.0016],
  [3.1, [-0.12, 1.2, 2.6], [-0.35, 0.62, 0.35], 'me', 0.0042],
  [4.9, [-0.17, 1.18, 2.45], [-0.35, 0.62, 0.35], 'me', 0.0042],
  [5.7, [0.62, 1.4, 3.9], [0.6, 0.45, -0.6], 'ais', 0.0026],
  [7.5, [0.64, 1.37, 3.7], [0.6, 0.45, -0.6], 'ais', 0.0026],
];
function camAt(t) {
  let i = 0; while (i < CAM.length - 2 && t > CAM[i + 1][0]) i++;
  const [ta, pa, la, fa, aa] = CAM[i], [tb, pb, lb, fb, ab] = CAM[i + 1];
  const u = ease((t - ta) / (tb - ta));
  return { pos: pa.map((v, k) => lerp(v, pb[k], u)), look: la.map((v, k) => lerp(v, lb[k], u)), focusOn: u < 0.5 ? fa : fb, ap: lerp(aa, ab, u) };
}
function pose(c, h, ph, t) {
  const s = 1 + 0.02 * Math.sin(2 * Math.PI * 1.05 * t + ph) + h.sq;
  c.sq.scale.set(1 / Math.sqrt(s), s, 1 / Math.sqrt(s));
  c.root.position.y = h.y + (c.baseY || 0);
}
// 이름이 불린 AI: 점프 + 한 팔 들기 / 끝: 셋 다 '저요!' 손 들고 점프
function aiAct(c, w, endHop, ph, t, armIdx, turn) {
  const inW = t >= w[0] - 0.15 && t <= w[1] + 0.3;
  pose(c, addHop(hop(t, w[0], 0.16), hop(t, endHop, 0.13, 0.28)), ph, t);
  const up = Math.max(inW ? ease((t - w[0] + 0.15) / 0.15) : 0, ease((t - endHop + 0.25) / 0.15));
  const sx = armIdx ? 1 : -1;
  c.arms[armIdx].rotation.z = sx * (0.5 + 2.4 * up) + (up > 0.5 ? 0.2 * Math.sin(t * 20) * up : 0);
  c.root.rotation.y = turn * (1 - ease((t - endHop + 0.6) / 0.4));
}
// 값 a→b를 시각 t0부터 d초 동안 부드럽게
const tween = (t, t0, d, a, b) => lerp(a, b, ease((t - t0) / d));

window.twFrame = (t) => {
  const inW = (w, pad = 0) => t >= w[0] - pad && t <= w[1] + pad;
  // 나
  const open = mouthOpen(t);
  pose(me, addHop(hop(t, W_HAPPY[0] - 0.05, 0.08, 0.26), { y: 0, sq: open * 0.012 }), 0.4, t);
  // 이름 부를 때 그 AI 쪽으로 고개 → 클로즈업 동안 카메라 쪽 → 끝에 다시 AI 쪽 (모두 t만으로 정해짐)
  const toAI = (x) => Math.atan2(x - POS.me[0], 1.05);
  let yaw = 0.45;
  yaw = tween(t, W_C[0] - 0.2, 0.2, yaw, toAI(POS.claude[0]));
  yaw = tween(t, W_G[0] - 0.2, 0.2, yaw, toAI(POS.gemini[0]));
  yaw = tween(t, W_P[0] - 0.2, 0.2, yaw, toAI(POS.gpt[0]));
  yaw = tween(t, 2.5, 0.5, yaw, 0.12);
  yaw = tween(t, 5.1, 0.5, yaw, 0.6);
  me.head.rotation.y = yaw * 0.6; me.root.rotation.y = yaw * 0.4;
  me.head.rotation.z = -0.14 * ease((t - (W_END - 0.45)) / 0.3) * (1 - ease((t - W_END - 0.8) / 0.4));
  me.arms[1].rotation.z = 0.18 + 0.9 * Math.sin(Math.PI * clamp((t - W_C[0] + 0.1) / (W_P[1] - W_C[0] + 0.4)));   // 부르면서 오른손을 들었다 내림
  me.arms[0].rotation.z = -0.18 - 0.35 * ease((t - W_HAPPY[0]) / 0.2) * (1 - ease((t - W_END - 0.4) / 0.3));
  const happy = inW(W_HAPPY, 0.12);
  me.brows.forEach((b) => { b.position.y = 0.055 + (happy ? 0.012 : 0) + 0.008 * open; });
  setFace(me.face, { blinkS: blink(t, [0.3, 2.6, 4.95, 6.7]), happy, open });
  // AI 셋
  aiAct(claude, W_C, 5.75, 1.3, t, 1, 0.25);
  aiAct(gpt, W_P, 5.9, 2.0, t, 1, 0.05);
  aiAct(gemini, W_G, 6.05, 2.6, t, 0, -0.25);
  setFace(claude.face, { blinkS: blink(t, [1.6, 3.6, 6.9]), happy: inW(W_C, 0.2) || t > 5.6 });
  setFace(gpt.face, { blinkS: blink(t, [0.9, 3.0, 6.4]), happy: inW(W_P, 0.2) || t > 5.75 });
  setFace(gemini.face, { blinkS: blink(t, [0.5, 2.2, 4.4, 7.1]), happy: inW(W_G, 0.2) || t > 5.9 });
  gemini.spark.rotation.z = t * 0.8 + 6.0 * ease((t - W_G[0]) / 0.7);
  gemini.spark.position.y = 0.5 + 0.03 * Math.sin(t * 3.1);
  gpt.knot.rotation.z = -0.25 * t - 1.0 * ease((t - W_P[0]) / 0.6);   // 매듭 꽃이 천천히 돌다가 이름 불리면 한 번 더
  for (const [c, b] of blobs) { const k = 1 - clamp((c.root.position.y - (c.baseY || 0)) / 0.3) * 0.5; b.position.y = (c.baseY || 0) + 0.002; b.position.x = c.root.position.x; b.position.z = c.root.position.z + 0.02; b.scale.setScalar(k * c.root.scale.x); b.material.opacity = 0.55 * k; }
  const cam = camAt(t);
  camera.position.set(...cam.pos); camera.lookAt(...cam.look); camera.updateMatrixWorld();
  const tgt = cam.focusOn === 'me' ? new THREE.Vector3(POS.me[0], 0.85, POS.me[2] + 0.2) : new THREE.Vector3(0.6, 0.55, -0.6);
  bokeh.uniforms.focus.value = camera.position.distanceTo(tgt);
  bokeh.uniforms.aperture.value = cam.ap; bokeh.uniforms.maxblur.value = 0.012;
  composer.render();
  g2.drawImage(renderer.domElement, 0, 0, W, H);
  overlay(t);
  return out.toDataURL('image/jpeg', 0.92);
};

// 캐릭터 시트: '나'만 정면·3/4 (글자 없음)
window.twSheet = (yaw) => {
  [claude, gpt, gemini].forEach((c) => { c.root.visible = false; });
  me.root.rotation.y = 0; me.head.rotation.set(0, 0, 0); me.root.position.y = 0; me.sq.scale.set(1, 1, 1);
  me.arms[0].rotation.z = -0.18; me.arms[1].rotation.z = 0.18;
  setFace(me.face, { blinkS: 1, happy: false, open: 0 });
  const d = 2.3, c = new THREE.Vector3(POS.me[0], 0.62, POS.me[2]);
  camera.position.set(c.x + Math.sin(yaw) * d, 0.95, c.z + Math.cos(yaw) * d); camera.lookAt(c); camera.updateMatrixWorld();
  bokeh.uniforms.focus.value = d; bokeh.uniforms.aperture.value = 0.002;
  composer.render();
  g2.drawImage(renderer.domElement, 0, 0, W, H);
  return out.toDataURL('image/jpeg', 0.92);
};
window.twReady = true;
