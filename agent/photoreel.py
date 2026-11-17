"""사진 내레이션 릴스 (post type "video" + "photo_reel", 2026-11-17 운영자 "사진은 무조건 넣어", "tts 써보자").

장면마다 사진 한 장이 화면을 꽉 채우고(천천히 확대), 그 위에 숫자·비교 같은 정리 글(overlay)과
내레이션 자막(cap)을 얹는다. 한국어 내레이션(ElevenLabs, agent/tts.py)이 장면 길이를 정한다:
장면 길이 = 그 장면 목소리 길이 + 틈. 글·그래프만 있는 장면은 없다 (모든 장면에 img 필수).

화면 (1080x1920, 인스타 안전 영역 안):
    0~500px      검은 띠 + 제목 2줄 (post.title, 처음부터 끝까지)
    500px~       사진 (cover로 꽉 채움, focus 쪽을 중심으로 천천히 확대. 장면이 바뀌면 살짝 당겨지며 등장)
    560~1000px   overlay: big(큰 숫자, 숫자가 0부터 올라감) / steps(날짜·값이 한 줄씩) / bars(두세 막대 비교)
    ~1140px      자막(cap, 내레이션을 짧게 옮긴 글, 검은 상자, 오른쪽 아래 버튼 줄 위)
    사진 위 왼쪽  작은 출처 글씨(credit)
소리: 내레이션 + 실제 음원 조각(music.src, 말하는 동안 덕킹) + 장면 전환 효과음 → 끝 화면(end_cta) → -14 LUFS.

post.json:
  "photo_reel": {
    "voice": {"engine": "elevenlabs", "voice": "deok", "settings": {}},   # 선택. 기본 deok, tts.py ELEVEN_SETTINGS
    "gap": 0.22,                       # 선택. 목소리 끝과 다음 장면 사이 (초)
    "scenes": [
      {"beat": "hook" | "delay1" | "rehook" | "delay2" | "answer",
       "img": "img/a.jpg", "focus": [0.5, 0.3], "zoom": [1.0, 1.08],   # 사진, 보여 줄 중심(가로·세로 0~1), 확대 시작·끝
       "credit": "사진: ... (CC BY 2.0)",
       "vo": "내레이션 (숫자·영어는 tts_ko_norm이 읽는 한글로 바꿔 보냄)",  "cap": "화면 자막\\n2줄까지", "hl": "자막 녹색 강조(선택)",
       "overlay_at": "top" | "low",     # 선택. low면 정리 글을 자막 바로 위로 (사진 위쪽 얼굴을 가리지 않게)
       "overlay": {"type": "big", "big": "1,290조 원", "sub": "한 줄", "size": 130(선택, 기본 150)} |
                  {"type": "steps", "items": [["2025.3", "615억 달러"], ...], "punch": "15배 넘게"} |
                  {"type": "bars", "items": [{"label": "앤트로픽", "value": 1290, "display": "1,290조 원", "on": true}], "note": "한 줄"},
       "fill": true}                    # 선택. 상장일 확정 숫자로 다시 만드는 장면 (ipo 블록, 아래)
    ]
  }
  글자 안의 {cap_usd} {cap_krw} {cap_krw_jo} {cmp_krw} {cmp_krw_jo} {price} {open} {range} {price_ko} {open_ko} {krw_rate}는 post "ipo" 블록에서 계산한다
  (상장 릴스용, 없으면 쓰지 않는다). ipo.status가 "final"이면 장면의 vo_final·cap_final·overlay_final을 먼저 쓴다.
  ipo.compare({"name", "krw_jo"})가 있으면 공모가 기준 시가총액(원)이 그보다 커야 렌더링한다 (비교 문장이 거짓이 되지 않게).

목소리 파일: voice/01.wav ... (44.1kHz 모노, 이 컴퓨터에서 만든다. GitHub Actions에는 TTS가 없어 저장소의 파일을 쓴다).
    py -3.12 agent/photoreel.py <게시물 폴더> --voice [--force] [--asr]   # 목소리 만들기(바뀐 글만) + 받아쓰기 확인
    py -3.12 agent/photoreel.py <게시물 폴더>                            # 계획(장면 시각)만 보기
렌더링은 render.py가 부른다.
"""
import asyncio
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
_SAFE = _CFG.get("reel_safe", {})
SAFE_TOP = _SAFE.get("top", 285)
SAFE_BOTTOM = _SAFE.get("bottom", 1250)
SIDE = _SAFE.get("side", 65)
RAIL_LEFT = _SAFE.get("rail_left", 850)
RAIL_TOP = _SAFE.get("rail_top", 1150)

BAND = 500            # 위 검은 띠 (제목)
CAP_BOTTOM = 1135     # 자막 아래 끝 (오른쪽 아래 버튼 줄 rail_top 위)
VO_LEAD = 0.08        # 장면 시작 뒤 목소리 시작
GAP = 0.22
MIN_SCENE = 1.6
CHARS_PER_SEC = 9.0   # 목소리 파일이 없을 때 길이 어림 (경고)
VOICE_DIR = "voice"
BEATS = ("hook", "delay1", "rehook", "delay2", "answer")
DISCLAIMER_RE = re.compile(r"투자\s*권유|투자\s*조언|매수\s*추천|매도\s*추천|사라|오를 것|기회입니다")


# ---------------- 숫자 ----------------
def ko_num(n):
    """정수·소수 한 자리 → 한글 읽기 (74 → 칠십사, 80.5 → 팔십 점 오). 내레이션 글의 숫자를 한글로."""
    digits = "영일이삼사오육칠팔구"
    s = f"{n}".rstrip("0").rstrip(".") if isinstance(n, float) else str(int(n))
    if "." in s:
        a, b = s.split(".")
        return ko_num(int(a)) + " 점 " + "".join(digits[int(c)] for c in b)
    v = int(s)
    if v == 0:
        return "영"
    units = [(10 ** 12, "조"), (10 ** 8, "억"), (10 ** 4, "만")]
    out = ""
    for u, name in units:
        if v >= u:
            q, v = divmod(v, u)
            out += ("" if q == 1 and name == "만" else _ko4(q)) + name + " "
    return (out + _ko4(v)).strip() if v else out.strip()


def _ko4(v):
    digits = "영일이삼사오육칠팔구"
    out = ""
    for u, name in ((1000, "천"), (100, "백"), (10, "십")):
        q, v = divmod(v, u)
        if q:
            out += ("" if q == 1 else digits[q]) + name
    return out + (digits[v] if v else "")


def ipo_vars(post):
    """post.ipo → 글자 틀 값. ipo가 없으면 {}."""
    ipo = post.get("ipo") or {}
    if not ipo.get("price") or not ipo.get("shares_outstanding_after"):
        return {}
    shares, price = float(ipo["shares_outstanding_after"]), float(ipo["price"])
    krw = float(ipo.get("krw_rate") or 0)
    usd_100m = shares * price / 1e8
    v = {"price": f"{price:g}", "price_ko": ko_num(price), "cap_usd_100m": usd_100m,
         "cap_usd": f"{round(usd_100m / 10) * 10:,.0f}억 달러",
         "range": "~".join(f"{x:g}" for x in ipo.get("price_range") or []),
         "open": f"{float(ipo['open']):g}" if ipo.get("open") is not None else "",
         "open_ko": ko_num(float(ipo["open"])) if ipo.get("open") is not None else ""}
    if krw:
        jo = shares * price * krw / 1e12
        v.update(cap_krw_jo=jo, cap_krw=f"{round(jo / 10) * 10:,.0f}조 원", krw_rate=f"{krw:,.1f}".rstrip("0").rstrip("."))
    cmp_ = ipo.get("compare") or {}
    if cmp_.get("krw_jo"):
        v.update(cmp_krw_jo=float(cmp_["krw_jo"]), cmp_krw=f"{round(float(cmp_['krw_jo']) / 10) * 10:,.0f}조 원")
    return v


def fmt(text, vars_):
    if not isinstance(text, str) or "{" not in text:
        return text
    return text.format(**{k: v for k, v in vars_.items()})


def pick(scene, key, final):
    return scene.get(key + "_final", scene.get(key)) if final else scene.get(key)


def resolved(post):
    """장면 목록 (상장일 확정이면 *_final, 글자 틀 채움)."""
    R = post["photo_reel"]
    final = (post.get("ipo") or {}).get("status") == "final"
    vs = ipo_vars(post)
    out = []
    for i, s in enumerate(R["scenes"], 1):
        ov = json.loads(json.dumps(pick(s, "overlay", final) or {}, ensure_ascii=False))

        def deep(x):
            if isinstance(x, str):
                return fmt(x, vs)
            if isinstance(x, list):
                return [deep(y) for y in x]
            if isinstance(x, dict):
                return {k: (vs.get(y[1:-1]) if isinstance(y, str) and re.fullmatch(r"\{(cap_krw_jo|cap_usd_100m|cmp_krw_jo)\}", y) else deep(y))
                        for k, y in x.items()}
            return x
        out.append({"n": i, "beat": s.get("beat"), "img": s["img"], "focus": s.get("focus", [0.5, 0.4]),
                    "zoom": s.get("zoom", [1.0, 1.07]), "credit": s.get("credit", ""),
                    "vo": fmt(pick(s, "vo", final), vs), "cap": fmt(pick(s, "cap", final), vs),
                    "hl": fmt(pick(s, "hl", final), vs), "overlay": deep(ov), "fill": bool(s.get("fill")),
                    "overlay_at": s.get("overlay_at", "top")})
    return out


# ---------------- 목소리 ----------------
def _wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def voice_file(folder, n):
    return Path(folder) / VOICE_DIR / f"{n:02d}.wav"


def _vo_key(text, vcfg):
    return hashlib.sha256(json.dumps([text, vcfg], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def make_voices(post, folder, force=False):
    """바뀐 장면만 ElevenLabs로 다시 만든다 (같은 글은 tts.py 캐시라 다시 과금되지 않음). voice/voice.json에 글 해시."""
    import tts
    folder = Path(folder)
    vcfg = dict((post["photo_reel"].get("voice") or {}))
    vid = tts.eleven_voice_id(vcfg.get("voice", "deok"))
    meta_p = folder / VOICE_DIR / "voice.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    for s in resolved(post):
        f = voice_file(folder, s["n"])
        key = _vo_key(s["vo"], vcfg)
        if f.exists() and meta.get(f.name) == key and not force:
            continue
        x = tts.trim(tts.synth_eleven(s["vo"], tts.KO_SR, vid, vcfg.get("settings"), float(vcfg.get("speed", 1.0)),
                                      normalize=vcfg.get("normalize", True), words=vcfg.get("words")), sr=tts.KO_SR)
        tts.save(f, x, sr=tts.KO_SR)
        meta[f.name] = key
        print(f"  목소리 {f.name}: {len(x) / tts.KO_SR:.2f}초  {s['vo']}")
    meta_p.parent.mkdir(parents=True, exist_ok=True)
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def _norm(t):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", t or "")


def asr_check(post, folder, model="small"):
    """받아쓰기(tts_ko_norm.verify_audio, faster-whisper)로 목소리가 대본대로 읽혔는지. 다른 줄은 대본을 고쳐 다시 만든다."""
    from tts_ko_norm import print_verify, verify_audio
    words = (post["photo_reel"].get("voice") or {}).get("words")
    bad = []
    for s in resolved(post):
        r = verify_audio(voice_file(folder, s["n"]), s["vo"], words, model=model)
        print(f"  {s['n']:02d} 대본: {s['vo']}")
        print_verify(r)
        if not r["ok"]:
            bad.append(s["n"])
    return bad


# ---------------- 계획 ----------------
def plan(post, folder, need_voice=True):
    folder = Path(folder)
    R = post["photo_reel"]
    gap = float(R.get("gap", GAP))
    t = 0.0
    scenes, problems = [], []
    for s in resolved(post):
        f = voice_file(folder, s["n"])
        if f.exists():
            vl = _wav_len(f)
        else:
            vl = len(_norm(s["vo"])) / CHARS_PER_SEC
            (problems if need_voice else []).append(f"목소리 파일 없음: {VOICE_DIR}/{f.name} (py -3.12 agent/photoreel.py <폴더> --voice)")
        d = max(MIN_SCENE, VO_LEAD + vl + gap)
        scenes.append(dict(s, t0=round(t, 3), dur=round(d, 3), vo_len=round(vl, 3),
                           voice=str(f.relative_to(folder)).replace("\\", "/") if f.exists() else None))
        t += d
    return {"scenes": scenes, "total": round(t, 3), "problems": problems}


def beats(p):
    out, seen = [], set()
    for s in p["scenes"]:
        if s["beat"] and s["beat"] not in seen:
            seen.add(s["beat"])
            out.append(f"{s['beat']} {s['t0']:.1f}초")
    return out


# ---------------- 화면 ----------------
def _img_uri(folder, rel):
    p = Path(folder) / rel
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


def page_html(post, p, folder, cfg):
    b = cfg["brand"]
    fonts = (ROOT / "assets" / "fonts").as_uri()
    title = post["title"]
    hl = post.get("highlight") or ""

    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def mark(s, h):
        s = esc(s).replace("\n", "<br>")
        return s.replace(esc(h), f'<span class="hl">{esc(h)}</span>', 1) if h else s
    imgs = {s["img"]: _img_uri(folder, s["img"]) for s in p["scenes"]}
    data = {"scenes": [{k: s[k] for k in ("t0", "dur", "img", "focus", "zoom", "credit", "overlay", "overlay_at")} |
                       {"cap": mark(s["cap"], s["hl"])} for s in p["scenes"]], "imgs": imgs}
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>
@import url('{fonts}/black-han-sans/index.css');
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-ExtraBold.otf');font-weight:800}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-Bold.otf');font-weight:700}}
@font-face{{font-family:'Wanted';src:url('{fonts}/WantedSans-SemiBold.otf');font-weight:600}}
*{{box-sizing:border-box}} html,body{{margin:0;background:{b['bg']}}}
#f{{width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{b['bg']};color:{b['text']};word-break:keep-all}}
#ph{{position:absolute;left:0;top:{BAND}px;width:{W}px;height:{H - BAND}px;overflow:hidden}}
#ph img{{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}}
#shade{{position:absolute;inset:0;background:rgba(0,0,0,.22)}}
#band{{position:absolute;left:0;top:0;width:{W}px;height:{BAND}px;background:{b['bg']}}}
#title{{position:absolute;left:{SIDE + 10}px;right:{SIDE + 10}px;top:{SAFE_TOP + 22}px;font-family:'Black Han Sans';font-size:76px;line-height:1.17;letter-spacing:-.01em}}
.hl{{color:{b['accent']}}}
#credit{{position:absolute;left:{SIDE}px;top:{BAND + 14}px;font:600 22px Wanted;color:#d7ddd9;background:rgba(0,0,0,.62);padding:4px 10px}}
#ov{{position:absolute;left:{SIDE}px;right:{SIDE}px;top:{BAND + 70}px}}
.big{{display:inline-block;font-family:'Black Han Sans';font-size:150px;line-height:1;color:{b['accent']};background:{b['bg']};padding:18px 26px 10px;letter-spacing:-.02em}}
.sub{{display:inline-block;margin-top:14px;font:700 38px Wanted;background:{b['bg']};padding:10px 18px}}
.row{{display:flex;align-items:baseline;gap:20px;background:{b['bg']};padding:6px 20px;margin-bottom:8px;width:max-content}}
.row .d{{font:700 32px Wanted;color:{b['muted']};min-width:140px}}
.row .v{{font-family:'Black Han Sans';font-size:54px}}
.row.on .v{{color:{b['accent']}}}
.punch{{display:inline-block;font-family:'Black Han Sans';font-size:80px;color:{b['bg']};background:{b['accent']};padding:10px 22px 2px;margin-top:4px}}
.bar{{margin-bottom:14px}}
.bar .lab{{display:inline-block;font:800 36px Wanted;background:{b['bg']};padding:6px 14px}}
.bar .track{{height:72px;margin-top:6px;position:relative}}
.bar .fill{{position:absolute;left:0;top:0;bottom:0;background:#cfd6d2}}
.bar.on .fill{{background:{b['accent']}}}
.bar .val{{position:absolute;top:6px;font-family:'Black Han Sans';font-size:54px;color:{b['bg']};padding-left:16px;white-space:nowrap}}
.note{{display:inline-block;font:600 28px Wanted;color:#d7ddd9;background:rgba(0,0,0,.7);padding:6px 12px}}
#cap{{position:absolute;left:{SIDE}px;right:{SIDE}px;bottom:{H - CAP_BOTTOM}px;text-align:center}}
#cap span.box{{display:inline;font:800 54px/1.42 Wanted;background:{b['bg']};padding:6px 16px;box-decoration-break:clone;-webkit-box-decoration-break:clone}}
</style></head><body><div id="f">
<div id="ph"><img id="im"><div id="shade"></div></div>
<div id="band"><div id="title">{mark(title, hl)}</div></div>
<div id="credit"></div><div id="ov"></div><div id="cap"></div></div>
<script>
const D = {json.dumps(data, ensure_ascii=False)};
const PW = {W}, PH = {H - BAND};
const im = document.getElementById('im'), ov = document.getElementById('ov'), cap = document.getElementById('cap'), cr = document.getElementById('credit');
const nat = {{}};
let cur = -1;
function ease(x){{x=Math.min(1,Math.max(0,x));return 1-Math.pow(1-x,3)}}
function countText(s, k){{  // 문자열 안 첫 숫자를 0 → 값으로
  const m = s.match(/[0-9][0-9,]*(\\.[0-9]+)?/); if(!m || k>=1) return s;
  const raw = m[0], dec = (m[1]||'').length ? m[1].length-1 : 0, v = parseFloat(raw.replace(/,/g,''));
  let x = v*k; let t = dec ? x.toFixed(dec) : Math.round(x).toString();
  if(raw.includes(',')) t = Number(t).toLocaleString('en-US', {{minimumFractionDigits:dec, maximumFractionDigits:dec}});
  return s.replace(raw, t);
}}
function esc(s){{return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')}}
function build(sc){{
  const o = sc.overlay || {{}}; let h = '';
  if(o.type==='big'){{ h = `<div><span class="big" id="bigv"${{o.size?` style="font-size:${{o.size}}px"`:''}}></span></div>` + (o.sub?`<div><span class="sub">${{esc(o.sub)}}</span></div>`:''); }}
  else if(o.type==='steps'){{ h = (o.items||[]).map((it,i)=>`<div class="row${{i==o.items.length-1?' on':''}}" id="st${{i}}"><span class="d">${{esc(it[0])}}</span><span class="v">${{esc(it[1])}}</span></div>`).join('') + (o.punch?`<div><span class="punch" id="pu">${{esc(o.punch)}}</span></div>`:''); }}
  else if(o.type==='bars'){{ h = (o.items||[]).map((it,i)=>`<div class="bar${{it.on?' on':''}}"><span class="lab">${{esc(it.label)}}</span><div class="track"><div class="fill" id="bf${{i}}"></div><span class="val" id="bv${{i}}">${{esc(it.display)}}</span></div></div>`).join('') + (o.note?`<div><span class="note">${{esc(o.note)}}</span></div>`:''); }}
  ov.innerHTML = h;
  cap.innerHTML = sc.cap ? `<span class="box">${{sc.cap}}</span>` : '';
  cr.textContent = sc.credit || ''; cr.style.display = sc.credit ? 'block' : 'none';
  im.src = D.imgs[sc.img];
  ov.style.top = '{BAND + 70}px';
}}
function place(sc){{  // overlay_at low: 정리 글 아래 끝을 자막 위 24px에 (자막 위치는 움직임 전 기준)
  if(sc.overlay_at !== 'low') return;
  const capTop = sc.cap ? {CAP_BOTTOM} - cap.offsetHeight : {CAP_BOTTOM};
  ov.style.top = (capTop - 24 - ov.offsetHeight) + 'px';
}}
async function init(){{
  for(const [k,u] of Object.entries(D.imgs)){{ const i = new Image(); i.src = u; await i.decode(); nat[k] = [i.naturalWidth, i.naturalHeight]; }}
}}
function problems(){{
  const out = [];
  D.scenes.forEach((sc,i)=>{{ build(sc); frameIn(sc, sc.dur*0.95, true);
    const r = ov.getBoundingClientRect(); for(const el of ov.querySelectorAll('.big,.sub,.row,.punch,.lab,.note,.val')){{
      const b = el.getBoundingClientRect(); if(b.right > {W - SIDE} + 1) out.push(`장면 ${{i+1}} 정리 글이 오른쪽 안전 영역을 넘음: ${{el.textContent}}`);
      const capTop = sc.cap ? cap.getBoundingClientRect().top : {CAP_BOTTOM};
      if(b.bottom > capTop - 14) out.push(`장면 ${{i+1}} 정리 글이 자막과 겹침: ${{el.textContent}}`); }}
    const cb = cap.getBoundingClientRect(); if(sc.cap && cb.height > 2*54*1.42 + 30) out.push(`장면 ${{i+1}} 자막이 2줄을 넘음`);
    for(const el of cap.querySelectorAll('.box')){{ for(const rc of el.getClientRects()){{ if(rc.right > {RAIL_LEFT} && rc.bottom > {RAIL_TOP}) out.push(`장면 ${{i+1}} 자막이 오른쪽 아래 버튼 줄과 겹침`); }} }}
    const tb = document.getElementById('title').getBoundingClientRect(); if(tb.bottom > {BAND - 8}) out.push('제목이 위 띠를 넘음');
  }});
  cur = -1; return out;
}}
function frameIn(sc, lt, still){{
  const [nw, nh] = nat[sc.img]; const base = Math.max(PW/nw, PH/nh);
  const z0 = sc.zoom[0], z1 = sc.zoom[1];
  const punch = 1 + 0.07*(1-ease(lt/0.32));
  const z = base * (z0 + (z1-z0)*Math.min(1, lt/sc.dur)) * punch;
  const w = nw*z, h = nh*z;
  const x = Math.min(0, Math.max(PW - w, PW/2 - sc.focus[0]*w)), y = Math.min(0, Math.max(PH - h, PH/2 - sc.focus[1]*h));
  im.style.transform = `translate(${{x}}px,${{y}}px) scale(${{z}})`;
  im.style.width = nw+'px'; im.style.height = nh+'px';
  const o = sc.overlay || {{}};
  const k = still ? 1 : ease((lt-0.12)/0.7);
  if(o.type==='big'){{ const el = document.getElementById('bigv'); el.textContent = o.count===false ? o.big : countText(o.big, k);
    const pk = still ? 1 : ease(lt/0.2); el.style.transform = `scale(${{0.82+0.18*pk}})`; el.style.transformOrigin = 'left bottom'; }}
  if(o.type==='steps'){{ const n = (o.items||[]).length, span = Math.max(0.5, Math.min(sc.dur*0.62, n*0.8));
    (o.items||[]).forEach((it,i)=>{{ const a = still ? 1 : ease((lt - 0.1 - i*span/n)/0.25); const el = document.getElementById('st'+i);
      el.style.opacity = a; el.style.transform = `translateX(${{-40*(1-a)}}px)`; }});
    const pu = document.getElementById('pu'); if(pu){{ const a = still ? 1 : ease((lt - 0.15 - span)/0.2); pu.style.opacity = a; pu.style.transform = `scale(${{0.7+0.3*a}})`; pu.style.transformOrigin='left center'; }} }}
  if(o.type==='bars'){{ const its = o.items||[]; const mx = Math.max(...its.map(i=>i.value)); const full = PW - 2*{SIDE};
    its.forEach((it,i)=>{{ const a = still ? 1 : ease((lt - 0.15 - i*0.35)/0.8); const w = full*0.78*it.value/mx*a;
      document.getElementById('bf'+i).style.width = w+'px'; const v = document.getElementById('bv'+i);
      v.style.left = '0px'; v.style.opacity = a > 0.6 ? 1 : 0; }}); }}
  const ca = still ? 1 : ease((lt-0.05)/0.22); cap.style.opacity = ca; cap.style.transform = `translateY(${{22*(1-ca)}}px)`;
  place(sc);
}}
function frame(t){{
  let i = D.scenes.findIndex(s => t >= s.t0 && t < s.t0 + s.dur); if(i < 0) i = D.scenes.length - 1;
  const sc = D.scenes[i]; if(i !== cur){{ build(sc); cur = i; }}
  frameIn(sc, t - sc.t0, false);
}}
</script></body></html>"""


async def _shoot(html_file, times, out_dir, stills=None):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await pw.chromium.launch(executable_path=exe) if exe else await pw.chromium.launch()
        pg = await browser.new_page(viewport={"width": W, "height": H})
        await pg.goto(html_file.as_uri())
        await pg.evaluate("""async () => { await document.fonts.load('96px "Black Han Sans"', '가A1');
            for (const w of [600, 700, 800]) await document.fonts.load(w + ' 30px Wanted', '가A1');
            await document.fonts.ready; }""")
        await pg.evaluate("init()")
        problems = await pg.evaluate("problems()")
        el = await pg.query_selector("#f")
        if not problems:
            for k, t in enumerate(times):
                await pg.evaluate(f"frame({t:.5f})")
                await el.screenshot(path=str(out_dir / f"f{k:05d}.jpg"), type="jpeg", quality=92)
        await browser.close()
    return problems


def sfx_track(p, total):
    from music_gen import make_hook_sfx
    sc = p["scenes"]
    imp = [0.0] + [s["t0"] for s in sc if s["beat"] in ("rehook", "answer") and s["t0"] > 0 and
                   (sc.index(s) == 0 or sc[sc.index(s) - 1]["beat"] != s["beat"])]
    wh = [s["t0"] for s in sc[1:] if s["t0"] not in imp]
    return make_hook_sfx(total, impacts=imp, hits=[], whooshes=wh, riser_to=None, drop=None)


def make_photo_reel(post, folder, cfg):
    """reel.mp4 (본편 + 끝 화면, -14 LUFS), frames/*.jpg. 전체 길이(초)."""
    folder = Path(folder)
    e, _ = check_photo_reel(post, folder)
    p = plan(post, folder)
    if e or p["problems"]:
        raise ValueError("\n".join(e + p["problems"]))
    work = folder / "_photo"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    html_file = work / "reel.html"
    html_file.write_text(page_html(post, p, folder, cfg), encoding="utf-8")
    main = p["total"]
    nfr = int(round(main * FPS))
    problems = asyncio.run(_shoot(html_file, [k / FPS for k in range(nfr)], work))
    if problems:
        shutil.rmtree(work)
        raise ValueError("\n".join(problems))
    silent = work / "silent.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(work / "f%05d.jpg"),
                    "-vf", f"scale={W}:{H},setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-r", str(FPS), str(silent)], check=True)
    from listreel import mix_audio
    pm = post.get("music") or {}
    if pm.get("src") and (folder / pm["src"]).exists():
        music = folder / pm["src"]
    else:
        from music_gen import make_hook_music
        music = work / "music.wav"
        make_hook_music(music, 120, main)
    voices = [(s["t0"] + VO_LEAD, folder / s["voice"]) for s in p["scenes"] if s["voice"]]
    sfx, _info = sfx_track(p, main)
    mixed = work / "mix.wav"
    info = mix_audio(music, voices, main, mixed, sfx)
    out = folder / "reel.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mixed),
                    "-map", "0:v:0", "-map", "1:a:0", "-t", f"{main:.3f}", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    dur = main
    from video import dm_cta, append_cta_card
    cta = dm_cta(post)
    if cta:
        dur = append_cta_card(out, cta, cfg, work, dur)
    from loudness import normalize
    normalize(out)
    frames = folder / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    for k, s in enumerate(p["scenes"], 1):
        t = s["t0"] + s["dur"] * 0.8
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(out),
                        "-frames:v", "1", "-q:v", "2", str(frames / f"{k:02d}.jpg")], check=True)
    shutil.rmtree(work)
    print("장면: " + " | ".join(f"{s['n']:02d} {s['beat']} {s['t0']:.1f}~{s['t0'] + s['dur']:.1f}초 {Path(s['img']).name}"
                               for s in p["scenes"]))
    print("박자: " + " → ".join(beats(p)))
    if info.get("voices"):
        print(f"소리: 목소리 {info['voices']}줄, 말하는 동안 목소리가 음악보다 {info['diff_in_speech_db']:.1f}dB 큼")
    return dur


# ---------------- 검사 ----------------
def check_photo_reel(post, folder=None):
    errors, warnings = [], []
    R = post.get("photo_reel") or {}
    sc = R.get("scenes") or []
    if len(sc) < 3:
        errors.append("photo_reel.scenes는 3개 이상")
    for i, s in enumerate(sc, 1):
        if not s.get("img"):
            errors.append(f"photo_reel {i}번 장면에 img(사진) 없음: 모든 장면에 사진 (운영자 2026-11-17 '사진은 무조건')")
        elif folder and not (Path(folder) / s["img"]).exists():
            errors.append(f"photo_reel {i}번 장면 사진 파일 없음: {s['img']}")
        if s.get("img") and not s.get("credit"):
            errors.append(f"photo_reel {i}번 장면 credit(사진 출처·라이선스) 없음")
        if not s.get("vo") or not s.get("cap"):
            errors.append(f"photo_reel {i}번 장면 vo(내레이션)·cap(자막) 필요")
        if s.get("beat") and s["beat"] not in BEATS:
            errors.append(f"photo_reel {i}번 beat는 {BEATS} 중 하나")
        for k in ("vo", "cap", "vo_final", "cap_final"):
            if len((s.get(k) or "").replace("\n", "")) and len(_lines(s.get(k) or "")) > 2 and k.startswith("cap"):
                errors.append(f"photo_reel {i}번 {k}는 2줄 이하")
        texts = [s.get(k) for k in ("vo", "cap", "vo_final", "cap_final")] + [json.dumps(s.get("overlay") or {}, ensure_ascii=False),
                                                                              json.dumps(s.get("overlay_final") or {}, ensure_ascii=False)]
        for t in texts:
            m = DISCLAIMER_RE.search(t or "")
            if m:
                errors.append(f"photo_reel {i}번 장면 '{m.group(0)}': 면책·권유 문구 금지, 사실만 (STYLE_GUIDE 0 원칙 6)")
    got = [s.get("beat") for s in sc]
    for b in ("hook", "rehook", "answer"):
        if b not in got:
            warnings.append(f"photo_reel 5박자: '{b}' 장면이 없음 (STYLE_GUIDE 6장)")
    ipo = post.get("ipo") or {}
    vs = ipo_vars(post)
    cmp_ = ipo.get("compare") or {}
    if cmp_.get("krw_jo") and vs.get("cap_krw_jo") is not None and vs["cap_krw_jo"] <= float(cmp_["krw_jo"]):
        errors.append(f"공모가 기준 시가총액 {vs['cap_krw']}이 {cmp_.get('name')} {cmp_['krw_jo']}조 원보다 크지 않음: 비교 장면을 고칠 것")
    try:
        for s in resolved(post):
            for k in ("vo", "cap"):
                if "{" in (s.get(k) or ""):
                    errors.append(f"photo_reel {s['n']}번 {k} 글자 틀이 안 채워짐: {s[k]}")
    except (KeyError, ValueError) as e:
        errors.append(f"photo_reel 글자 틀 오류: {e} (ipo 블록 값 확인)")
    if folder:
        p = plan(post, folder, need_voice=False)
        if not 18 <= p["total"] <= 40:
            warnings.append(f"photo_reel 본편 {p['total']:.1f}초: 20~35초 권장")
        for s in p["scenes"]:
            if s["beat"] == "hook" and s["t0"] + s["dur"] > 4.0:
                warnings.append(f"후킹 장면이 {s['t0'] + s['dur']:.1f}초까지: 0~3초 안에 (STYLE_GUIDE 6장)")
                break
    return errors, warnings


def _lines(t):
    return [x for x in str(t).split("\n") if x.strip()]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--voice", action="store_true", help="목소리 만들기 (바뀐 장면만)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--asr", action="store_true", help="받아쓰기로 확인")
    a = ap.parse_args()
    folder = Path(a.folder)
    post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    if a.voice:
        make_voices(post, folder, a.force)
    if a.asr:
        bad = asr_check(post, folder)
        print("다시 만들 줄:", bad or "없음")
    e, w = check_photo_reel(post, folder)
    for x in w:
        print("경고:", x)
    for x in e:
        print("오류:", x)
    p = plan(post, folder, need_voice=False)
    for s in p["scenes"]:
        print(f"{s['n']:02d} {s['beat'] or '':7} {s['t0']:5.1f}~{s['t0'] + s['dur']:5.1f}초 목소리 {s['vo_len']:.2f}초  {s['img']}  {s['vo']}")
    print(f"본편 {p['total']:.1f}초  박자: {' → '.join(beats(p))}")


if __name__ == "__main__":
    main()
