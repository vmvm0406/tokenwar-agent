// three.js 3D 캐릭터 대화 릴스 시제품 (2026-11-17).
// 모든 움직임은 시각 t의 함수(실시간 아님) → render.py가 twFrame(t)를 프레임마다 부른다.
// 캐릭터는 그림 없이 코드로 만든 절차적 모델: 클로드 = 주황 햇살(버스트) 머리 점토 인형,
// 제미나이 = 파랑→보라 4갈래 반짝이 별, 진행자 = 고양이 귀 연두 젤리 슬라임. 비공식 팬 캐릭터.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

const W = 1080, H = 1920;
const T0 = 1.2;          // 대사 시작
const DUR = 7.0;
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

// ---------- 조립 ----------
let renderer, composer, bokeh, scene, camera, slime, claude, gemini, blobs, W_DAEGYEOL, W_CLAUDE, W_GEMINI, W_END;
let OPT = { dof: true, trans: true, shadows: true, msaa: 4, scale: 1 };
window.twInit = async (line, opt) => {
  OPT = Object.assign(OPT, opt || {});
  const RW = Math.round(W * OPT.scale / 2) * 2, RH = Math.round(H * OPT.scale / 2) * 2;
  LINE = line; buildPhrases();
  W_DAEGYEOL = wordWindow('대결'); W_CLAUDE = wordWindow('클로드'); W_GEMINI = wordWindow('제미나이'); W_END = T0 + LINE.ends.at(-1);
  await document.fonts.load('44px "Black Han Sans"', '토큰전쟁'); await document.fonts.load('700 50px Wanted', '가A'); await document.fonts.load('600 24px Wanted', '가A');
  renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1); renderer.setSize(RW, RH);
  renderer.shadowMap.enabled = OPT.shadows; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x2a1f19);
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.55;
  const key = new THREE.DirectionalLight(0xffd6a8, 2.6); key.position.set(-2.5, 4, 3); key.castShadow = true;
  Object.assign(key.shadow.camera, { left: -2.5, right: 2.5, top: 2.5, bottom: -2.5, near: 0.5, far: 12 });
  key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 6; scene.add(key);
  const rim = new THREE.DirectionalLight(0x9fc8ff, 1.4); rim.position.set(2.5, 2.5, -3); scene.add(rim);
  scene.add(new THREE.HemisphereLight(0xffe8d0, 0x3a2418, 0.5));
  buildDesk(scene);
  slime = makeSlime(); slime.root.position.set(0, 0, 0.45); scene.add(slime.root);
  claude = makeClaude(); claude.root.position.set(-0.66, 0, -0.35); claude.root.scale.setScalar(0.95); scene.add(claude.root);
  gemini = makeGemini(); gemini.root.position.set(0.68, 0, -0.35); gemini.root.scale.setScalar(0.92); scene.add(gemini.root);
  [slime, claude, gemini].forEach((c) => c.root.traverse((o) => { if (o.isMesh) o.castShadow = true; }));
  blobs = [[slime, blob(scene, 0.55)], [claude, blob(scene, 0.45)], [gemini, blob(scene, 0.45)]];
  camera = new THREE.PerspectiveCamera(42, W / H, 0.1, 40);
  const rt = new THREE.WebGLRenderTarget(RW, RH, { type: THREE.HalfFloatType, samples: OPT.msaa });
  composer = new EffectComposer(renderer, rt); composer.setPixelRatio(1); composer.setSize(RW, RH);
  composer.addPass(new RenderPass(scene, camera));
  bokeh = new BokehPass(scene, camera, { focus: 5, aperture: 0.003, maxblur: 0.012 }); bokeh.enabled = OPT.dof; composer.addPass(bokeh);
  if (!OPT.trans) slime.root.traverse((o) => { if (o.material && o.material.transmission) { o.material.transmission = 0; o.material.transparent = true; o.material.opacity = 0.88; } });
  composer.addPass(new OutputPass());
  const gl = renderer.getContext(), dbg = gl.getExtension('WEBGL_debug_renderer_info');
  return { renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), webgl2: renderer.capabilities.isWebGL2 };
};

const CAM = [   // [시각, 위치, 바라보는 곳, 초점 대상, 조리개]
  [0.0, [0, 1.5, 5.4], [0, 0.32, 0], 'slime', 0.0018],
  [1.0, [0, 1.47, 5.2], [0, 0.32, 0], 'slime', 0.0018],
  [2.5, [0.05, 1.05, 3.3], [0, 0.2, 0.45], 'slime', 0.004],
  [4.5, [-0.05, 1.03, 3.15], [0, 0.2, 0.45], 'slime', 0.004],
  [5.5, [0.2, 1.35, 4.7], [0, 0.34, -0.2], 'pair', 0.0026],
  [7.0, [0.25, 1.32, 4.5], [0, 0.34, -0.2], 'pair', 0.0026],
];
function camAt(t) {
  let i = 0; while (i < CAM.length - 2 && t > CAM[i + 1][0]) i++;
  const [ta, pa, la, fa, aa] = CAM[i], [tb, pb, lb, fb, ab] = CAM[i + 1];
  const u = ease((t - ta) / (tb - ta));
  return { pos: pa.map((v, k) => lerp(v, pb[k], u)), look: la.map((v, k) => lerp(v, lb[k], u)), focusOn: u < 0.5 ? fa : fb, ap: lerp(aa, ab, u) };
}

function pose(c, h, breath, ph, t) {
  const s = 1 + 0.022 * Math.sin(2 * Math.PI * 1.05 * t + ph) + h.sq;
  c.sq.scale.set(1 / Math.sqrt(s), s, 1 / Math.sqrt(s));
  c.root.position.y = h.y;
}

window.twFrame = (t) => {
  const inW = (w, pad = 0) => t >= w[0] - pad && t <= w[1] + pad;
  // 슬라임 (진행자)
  const open = mouthOpen(t);
  let sh = hop(t, W_DAEGYEOL[0] - 0.02, 0.14, 0.3);
  sh = addHop(sh, { y: 0, sq: open * 0.045 });
  pose(slime, sh, 0.022, 0, t);
  slime.head.rotation.z = 0.16 * ease((t - (W_END - 0.5)) / 0.35) * (1 - ease((t - W_END - 0.9) / 0.4));
  slime.root.rotation.y = 0.35 * Math.sin(Math.PI * clamp((t - W_CLAUDE[0] + 0.1) / 0.5)) * -1 + 0.35 * Math.sin(Math.PI * clamp((t - W_GEMINI[0] + 0.1) / 0.55))
    + (t > W_END + 0.3 ? 0 : 0);
  setFace(slime.face, { blinkS: blink(t, [0.7, 2.95, 5.6]), happy: inW(W_DAEGYEOL, 0.15), open });
  // 클로드
  let ch = addHop(hop(t, W_CLAUDE[0], 0.16), hop(t, 5.35, 0.12, 0.28));
  pose(claude, ch, 0.022, 1.3, t);
  const look = (a, b) => ease((t - a) / 0.35) * (1 - ease((t - b) / 0.35));
  claude.root.rotation.y = 0.45 * look(1.3, 4.9) + 0.75 * ease((t - 4.9) / 0.4);
  claude.arms[1].rotation.z = 0.45 + (inW(W_CLAUDE, 0.25) ? -2.3 + 0.35 * Math.sin(t * 22) : 0) * ease((t - W_CLAUDE[0] + 0.25) / 0.15);
  claude.arms[0].rotation.z = -0.45 - 0.5 * ease((t - 5.2) / 0.2) * (1 - ease((t - 5.9) / 0.2));
  setFace(claude.face, { blinkS: blink(t, [1.1, 3.6, 6.3]), happy: inW(W_CLAUDE, 0.2) });
  // 제미나이
  let gh = addHop(hop(t, W_GEMINI[0], 0.18), hop(t, 5.6, 0.12, 0.28));
  pose(gemini, gh, 0.022, 2.6, t);
  gemini.root.rotation.y = -0.45 * look(1.3, 4.9) - 0.75 * ease((t - 4.9) / 0.4);
  gemini.head.rotation.z = 0.12 * Math.sin(Math.PI * clamp((t - 2.0) / 0.8));
  gemini.spark.rotation.z = t * 0.8 + 6.0 * ease((t - W_GEMINI[0]) / 0.7);
  gemini.spark.position.y = 0.5 + 0.03 * Math.sin(t * 3.1);
  gemini.arms.forEach((a, i) => { a.rotation.z = (i ? 1 : -1) * (0.6 + (inW(W_GEMINI, 0.2) ? 1.4 : 0) * ease((t - W_GEMINI[0] + 0.2) / 0.15)); });
  setFace(gemini.face, { blinkS: blink(t, [0.4, 2.2, 4.7, 6.6]), happy: inW(W_GEMINI, 0.2) });
  // 접지 그림자
  for (const [c, b] of blobs) { const k = 1 - clamp(c.root.position.y / 0.3) * 0.5; b.position.x = c.root.position.x; b.position.z = c.root.position.z + 0.02; b.scale.setScalar(k); b.material.opacity = 0.55 * k; }
  // 카메라·초점
  const cam = camAt(t);
  camera.position.set(...cam.pos); camera.lookAt(...cam.look); camera.updateMatrixWorld();
  const tgt = cam.focusOn === 'slime' ? new THREE.Vector3(0, 0.45, 0.6) : new THREE.Vector3(0, 0.5, -0.35);
  bokeh.uniforms.focus.value = camera.position.distanceTo(tgt);
  bokeh.uniforms.aperture.value = cam.ap; bokeh.uniforms.maxblur.value = 0.012;
  composer.render();
  g2.drawImage(renderer.domElement, 0, 0, W, H);   // 낮은 해상도로 그렸으면 키움 (글자는 원래 해상도로 겹침)
  overlay(t);
  return out.toDataURL('image/jpeg', 0.92);
};
window.twReady = true;
