"""post.json → 카드뉴스 JPEG / 릴스 MP4.

사용법:
    python agent/render.py posts/queue/<게시물 폴더>

결과:
    carousel: slides/01.jpg ... (1080x1350)
    reel:     frames/01.jpg ... (1080x1920), reel.mp4, cover.jpg

표지 유형(cover.layout): visual, icon, word, number, list
본문 유형(kind): body, steps, compare, stat
시각 요소(visual): image, monogram, chat, settings, terminal, bars, timeline, number
자세한 형식은 TEMPLATES.md 참고.

규칙 검사(checks.py)와 글자 넘침 검사를 통과하지 못하면 저장하지 않고 종료 코드 1로 끝난다.
"""
import asyncio
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from checks import CONFIG, check_post

ROOT = Path(__file__).resolve().parent.parent
FONTS = (ROOT / "assets" / "fonts").as_uri()
B = CONFIG["brand"]
SIZES = {"carousel": (1080, 1350), "reel": (1080, 1920)}


# ---------- 글자 처리 ----------

def esc(s):
    t = html.escape(str(s or ""))
    # "3만 5,578개", "1조 2,000억 원"처럼 숫자 덩어리가 줄바꿈으로 갈라지지 않게
    t = re.sub(r"(\d+(?:만|억|조))\s(?=\d)", "\\1\u00a0", t)
    t = re.sub(r"(\d[\d,.]*(?:만|억|조)?)\s(?=(?:원|달러|명|개|배|%|년|일|시간))", "\\1\u00a0", t)
    return t


def hl(text, word):
    t = esc(text)
    if word:
        w = esc(word)
        t = t.replace(w, f'<span class="hl">{w}</span>', 1)
    return t


def br(t):
    return t.replace("\n", "<br>")


# ---------- 스타일 ----------

CSS = """
@font-face{font-family:'Pretendard';src:url('FONTS/Pretendard-Regular.otf');font-weight:400}
@font-face{font-family:'Pretendard';src:url('FONTS/Pretendard-SemiBold.otf');font-weight:600}
@font-face{font-family:'Pretendard';src:url('FONTS/Pretendard-Bold.otf');font-weight:700}
@font-face{font-family:'Pretendard';src:url('FONTS/Pretendard-ExtraBold.otf');font-weight:800}
@font-face{font-family:'Pretendard';src:url('FONTS/Pretendard-Black.otf');font-weight:900}
@font-face{font-family:'JBM';src:url('FONTS/jetbrains-mono-latin-500-normal.woff2');font-weight:500}
@font-face{font-family:'JBM';src:url('FONTS/jetbrains-mono-latin-700-normal.woff2');font-weight:700}
@font-face{font-family:'JBM';src:url('FONTS/jetbrains-mono-latin-800-normal.woff2');font-weight:800}
*{box-sizing:border-box}
html,body{margin:0;background:#000}
.slide{width:Wpx;height:Hpx;background:BG;color:TEXT;font-family:'Pretendard',sans-serif;position:relative;overflow:hidden;
  word-break:keep-all;overflow-wrap:break-word;margin-bottom:20px}
.hl{color:ACCENT}
.mono{font-family:'JBM','Pretendard',monospace}
.dots{position:absolute;inset:0;background-image:radial-gradient(#1b2a21 1.6px,transparent 1.6px);background-size:36px 36px;opacity:.9}

/* 공통: 태그 상자, 브랜드 표시 */
.tag{display:inline-flex;align-items:center;gap:10px;padding:9px 20px 11px;background:ACCENT;border-radius:999px;
  font-size:26px;font-weight:800;color:BG;line-height:1;letter-spacing:-.01em}
.tag b{color:BG;font-weight:900}
.tag.urgent:before{content:'';width:12px;height:12px;border-radius:50%;background:BG}
.mark{position:absolute;left:0;right:0;bottom:MARKBpx;display:flex;flex-direction:column;align-items:center;gap:6px}
.mark .m1{font-family:'JBM',monospace;font-weight:800;font-size:32px;letter-spacing:.14em;color:ACCENT;display:flex;align-items:center;gap:10px}
.mark .m1 i{display:inline-block;width:11px;height:26px;background:ACCENT}
.mark .m2{font-size:18px;color:#7E8A83;letter-spacing:.2em;font-weight:600}

/* 표지 */
.vis{position:absolute;left:0;right:0;top:0;height:VISHpx;display:flex;align-items:center;justify-content:center;overflow:hidden}
.vis img.full{width:100%;height:100%;object-fit:cover}
.fade{position:absolute;left:0;right:0;top:FADETpx;height:420px;background:linear-gradient(to bottom,rgba(10,11,10,0),BG 78%)}
.ctext{position:absolute;left:PADXpx;right:PADXpx;bottom:CTEXTBpx;display:flex;flex-direction:column;gap:20px}
.ctitle{margin:0;font-size:CTITLEpx;font-weight:800;line-height:1.24;letter-spacing:-.035em;text-wrap:balance}
.csub{margin:0;font-size:CSUBpx;font-weight:600;color:#AEB8B2;letter-spacing:-.01em}
.csub b{color:TEXT;font-weight:700}

/* 시각 요소 */
.tile{width:340px;height:340px;border-radius:78px;background:#121a15;border:3px solid ACCENT;display:flex;align-items:center;justify-content:center;
  font-family:'JBM',monospace;font-weight:800;font-size:170px;color:ACCENT;box-shadow:0 30px 80px rgba(0,0,0,.6)}
.tile img{width:72%;height:72%;object-fit:contain}
.tiles{display:grid;grid-template-columns:repeat(3,200px);gap:34px}
.tiles .tile{width:200px;height:200px;border-radius:46px;font-size:88px}
.card{width:840px;background:#111813;border:2px solid #22332a;border-radius:36px;padding:40px;display:flex;flex-direction:column;gap:22px;
  box-shadow:0 30px 90px rgba(0,0,0,.55)}
.card .ct{font-size:30px;font-weight:800;color:TEXT;display:flex;justify-content:space-between;align-items:center}
.card .ct small{font-family:'JBM',monospace;font-size:20px;color:#7E8A83;font-weight:700;letter-spacing:.1em}
.opt{display:flex;align-items:center;gap:20px;padding:22px 26px;border-radius:20px;background:#0c120e;border:2px solid #1d2a22;font-size:31px;font-weight:600;color:#C9D1CC}
.opt i{width:30px;height:30px;border-radius:50%;border:3px solid #4a5a50;flex:none}
.opt.on{border-color:ACCENT;color:TEXT}.opt.on i{border-color:ACCENT;background:radial-gradient(ACCENT 45%,transparent 50%)}
.opt em{margin-left:auto;font-style:normal;font-size:22px;font-weight:800;color:BG;background:ACCENT;padding:6px 12px;border-radius:8px}
.bub{max-width:640px;padding:22px 28px;border-radius:28px;font-size:31px;line-height:1.45;font-weight:500}
.bub.user{align-self:flex-end;background:#1f2a24;color:TEXT;border-bottom-right-radius:8px}
.bub.ai{align-self:flex-start;background:#0c120e;border:2px solid #22332a;color:#DDE4E0;border-bottom-left-radius:8px}
.bub.ai b{color:ACCENT}
.term{width:860px;background:#050705;border:2px solid #1d2a22;border-radius:26px;overflow:hidden;box-shadow:0 30px 90px rgba(0,0,0,.6)}
.term .bar{height:58px;border-bottom:2px solid #1d2a22;display:flex;align-items:center;padding:0 26px;font-family:'JBM',monospace;font-size:20px;color:#7E8A83;letter-spacing:.08em}
.term pre{margin:0;padding:30px 34px;font-family:'JBM','Pretendard',monospace;font-size:28px;line-height:1.65;color:#C9D1CC;white-space:pre-wrap}
.term .ok{color:ACCENT}.term .dim{color:#6c7a72}
.bars{width:840px;display:flex;flex-direction:column;gap:26px}
.brow{display:flex;flex-direction:column;gap:10px}
.brow .bl{display:flex;justify-content:space-between;font-size:28px;font-weight:700;color:#C9D1CC}
.brow .bl span:last-child{font-family:'JBM',monospace}
.brow .bt{height:34px;border-radius:10px;background:#141c17;overflow:hidden}
.brow .bt i{display:block;height:100%;background:#3a4a40;border-radius:10px}
.brow.on .bl{color:TEXT}.brow.on .bt i{background:ACCENT}
.tl{width:820px;display:flex;flex-direction:column;gap:0}
.tli{display:grid;grid-template-columns:150px 40px 1fr;align-items:start;min-height:110px}
.tli .d{font-family:'JBM',monospace;font-weight:800;font-size:30px;color:#7E8A83;padding-top:4px}
.tli .dot{width:22px;height:22px;border-radius:50%;background:#3a4a40;margin-top:10px;position:relative}
.tli .dot:after{content:'';position:absolute;left:9px;top:28px;width:4px;height:84px;background:#22332a}
.tli:last-child .dot:after{display:none}
.tli .t{font-size:32px;font-weight:700;line-height:1.35;color:#C9D1CC}
.tli.on .d{color:ACCENT}.tli.on .dot{background:ACCENT}.tli.on .t{color:TEXT}
.bignum{display:flex;flex-direction:column;align-items:center;gap:10px}
.bignum .n{font-family:'Pretendard';font-weight:900;font-size:230px;line-height:1;color:ACCENT;letter-spacing:-.05em}
.bignum .n small{font-family:'Pretendard';font-size:90px;font-weight:900;margin-left:8px}
.bignum .c{font-size:32px;font-weight:700;color:#AEB8B2}
.wall{position:absolute;inset:-20px -60px;display:flex;flex-direction:column;justify-content:center;gap:26px;transform:rotate(0deg)}
.wall div{white-space:nowrap;font-size:40px;font-weight:700;color:#1f2b24;letter-spacing:-.01em}
.wall .on{color:ACCENT}
.word{position:relative;display:flex;flex-direction:column;align-items:center;gap:18px;padding:40px 60px;background:radial-gradient(BG 55%,rgba(10,11,10,0) 72%)}
.word .lab{font-family:'JBM',monospace;font-weight:800;font-size:26px;letter-spacing:.2em;color:ACCENT}
.word .w{font-size:170px;font-weight:900;letter-spacing:-.05em;line-height:1}
.word .wd{font-size:32px;font-weight:600;color:#AEB8B2}

/* 본문 장 */
.inner{position:absolute;left:PADXpx;right:PADXpx;top:INTOPpx;bottom:INBOTpx;display:flex;flex-direction:column;gap:30px;overflow:hidden}
.top{position:absolute;left:PADXpx;right:PADXpx;top:TOPYpx;display:flex;justify-content:space-between;align-items:center;font-family:'JBM',monospace;font-weight:700;font-size:22px;letter-spacing:.1em;color:#7E8A83}
.top .b{color:ACCENT;display:flex;align-items:center;gap:10px}.top .b i{display:inline-block;width:9px;height:22px;background:ACCENT}
.num{font-family:'JBM',monospace;font-weight:800;font-size:40px;color:ACCENT}
.heading{margin:0;font-size:HEADpx;font-weight:800;line-height:1.28;letter-spacing:-.03em;text-wrap:balance}
.body{margin:0;font-size:BODYpx;font-weight:500;line-height:1.62;color:#C9D1CC;letter-spacing:-.01em;text-wrap:pretty}
.point{border:3px solid ACCENT;background:rgba(0,255,102,.06);border-radius:22px;padding:24px 30px;display:flex;flex-direction:column;gap:8px}
.point .lbl{font-family:'JBM',monospace;font-weight:800;font-size:22px;letter-spacing:.16em;color:ACCENT}
.point .txt{font-size:POINTpx;font-weight:700;line-height:1.45;text-wrap:pretty}
.bvis{height:BVISpx;flex:none;border-radius:28px;background:#0d130f;border:2px solid #1a261f;position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center}
.bvis img{width:100%;height:100%;object-fit:cover}
.bvis .card,.bvis .term,.bvis .bars,.bvis .tl{transform:scale(.8)}
.steps{display:flex;flex-direction:column;gap:26px}
.step{display:grid;grid-template-columns:64px 1fr;gap:22px;align-items:start}
.step .k{width:60px;height:60px;border-radius:50%;background:ACCENT;color:BG;font-family:'JBM',monospace;font-weight:800;font-size:28px;display:flex;align-items:center;justify-content:center}
.step .st{font-size:STEPTpx;font-weight:800;line-height:1.3;margin-top:6px}
.step .sx{font-size:STEPXpx;font-weight:500;color:#AEB8B2;line-height:1.5;margin-top:6px}
.cmp{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}
.cmp .col{border-radius:24px;border:2px solid #22332a;padding:28px;display:flex;flex-direction:column;gap:14px;background:#0d130f}
.cmp .col.on{border-color:ACCENT;border-width:3px;background:rgba(0,255,102,.06)}
.cmp .cl{font-family:'JBM','Pretendard',monospace;font-size:24px;font-weight:800;letter-spacing:.06em;color:#7E8A83}
.cmp .col.on .cl{color:ACCENT}
.cmp .ci{font-size:CMPpx;font-weight:600;line-height:1.45;color:#DDE4E0}
.stat .n{font-family:'Pretendard';font-weight:900;font-size:180px;line-height:1;color:ACCENT;letter-spacing:-.05em}
.stat .n small{font-family:'Pretendard';font-size:76px;font-weight:900;margin-left:6px}
.stat .u{font-size:34px;font-weight:700;color:#AEB8B2;margin-top:8px}
.bot{position:absolute;left:PADXpx;right:PADXpx;bottom:BOTYpx;display:flex;align-items:center;gap:30px;font-family:'JBM',monospace;font-size:22px;color:#7E8A83}
.bot .pb{flex:1;height:8px;border-radius:3px;background:#1D2621;overflow:hidden}.bot .pb i{display:block;height:100%;background:ACCENT}

/* 인용 영상 장면 */
.clipbox{flex:none;margin:0 -PADXpx;height:CLIPHpx;background:#141c17;display:flex;align-items:center;justify-content:center;position:relative}
.clipbox .ph{font-family:'JBM','Pretendard',monospace;font-weight:800;font-size:34px;color:#4a5a50;letter-spacing:.08em}
.clipsrc{font-family:'JBM','Pretendard',monospace;font-size:24px;font-weight:700;color:#7E8A83;letter-spacing:.04em;margin-top:-8px}
.clipsrc b{color:ACCENT}

/* 마지막 장 */
.outro .inner{justify-content:center}
.slogan{margin:0;font-size:SLOGANpx;font-weight:900;line-height:1.2;letter-spacing:-.035em;white-space:pre-line}
.cta{align-self:flex-start;background:ACCENT;color:BG;font-weight:800;font-size:34px;padding:18px 32px;border-radius:999px}
.src{font-size:22px;line-height:1.55;color:#7E8A83}
"""

DIMS = {
    "carousel": dict(PADX=72, VISH=860, FADET=470, CTEXTB=170, MARKB=56, CTITLE=74, CSUB=30, TOPY=60,
                     INTOP=140, INBOT=150, BOTY=70, HEAD=66, BODY=40, POINT=36, BVIS=440, STEPT=38, STEPX=31,
                     CMP=32, SLOGAN=88, CLIPH=608),
    "reel": dict(PADX=80, VISH=1200, FADET=760, CTEXTB=430, MARKB=300, CTITLE=86, CSUB=34, TOPY=210,
                 INTOP=300, INBOT=420, BOTY=330, HEAD=78, BODY=46, POINT=42, BVIS=560, STEPT=44, STEPX=36,
                 CMP=36, SLOGAN=98, CLIPH=608),
}


REEL_EXTRA = ".vis>.card,.vis>.term,.vis>.bars,.vis>.tl,.vis>.bignum,.vis>.tile,.vis>.tiles{transform:scale(1.1)}"


def build_css(kind):
    w, h = SIZES[kind]
    c = CSS.replace("FONTS", FONTS)
    for k, v in sorted(DIMS[kind].items(), key=lambda kv: -len(kv[0])):
        c = c.replace(f"{k}px", f"{v}px")
    c = c.replace("width:Wpx", f"width:{w}px").replace("height:Hpx", f"height:{h}px")
    if kind == "reel":
        c += REEL_EXTRA
    for k, v in [("ACCENT", B["accent"]), ("BG", B["bg"]), ("TEXT", B["text"])]:
        c = c.replace(k, v)
    return c


# ---------- 시각 요소 ----------

def img_uri(folder, src):
    p = (folder / src).resolve()
    if not p.exists():
        raise FileNotFoundError(f"이미지 없음: {src}")
    return p.as_uri()


def visual_html(v, folder):
    t = v.get("type")
    if t == "image":
        return f'<img class="full" src="{img_uri(folder, v["src"])}" style="object-fit:{v.get("fit", "cover")}">'
    if t == "monogram":
        inner = f'<img src="{img_uri(folder, v["src"])}">' if v.get("src") else esc(v.get("text", "?"))
        return f'<div class="tile">{inner}</div>'
    if t == "tiles":
        cells = []
        for it in v["items"][:6]:
            inner = f'<img src="{img_uri(folder, it["src"])}">' if it.get("src") else esc(it.get("text", "?"))
            cells.append(f'<div class="tile">{inner}</div>')
        return f'<div class="tiles">{"".join(cells)}</div>'
    if t == "settings":
        rows = []
        for i, o in enumerate(v["options"]):
            on = i == v.get("selected")
            badge = f'<em>{esc(v.get("badge", "기본값"))}</em>' if on and v.get("badge", "기본값") else ""
            rows.append(f'<div class="opt{" on" if on else ""}"><i></i>{esc(o)}{badge}</div>')
        return (f'<div class="card"><div class="ct">{esc(v.get("title", ""))}<small>{esc(v.get("label", "SETTINGS"))}</small></div>'
                f'{"".join(rows)}</div>')
    if t == "chat":
        bubs = []
        for m in v["items"]:
            txt = hl(m["text"], m.get("highlight"))
            bubs.append(f'<div class="bub {"user" if m.get("role") == "user" else "ai"}">{br(txt)}</div>')
        return f'<div class="card" style="gap:18px">{"".join(bubs)}</div>'
    if t == "terminal":
        lines = []
        for ln in v["lines"]:
            e = esc(ln)
            if ln.startswith("✓"):
                e = f'<span class="ok">✓</span>{e[1:]}'
            elif ln.startswith("#"):
                e = f'<span class="dim">{e}</span>'
            elif ln.startswith("$"):
                e = f'<span class="ok">$</span>{e[1:]}'
            lines.append(e)
        return (f'<div class="term"><div class="bar">{esc(v.get("title", "terminal"))}</div>'
                f'<pre>{chr(10).join(lines)}</pre></div>')
    if t == "bars":
        mx = max(it["value"] for it in v["items"]) or 1
        unit = esc(v.get("unit", ""))
        rows = []
        for it in v["items"]:
            on = it.get("on")
            rows.append(f'<div class="brow{" on" if on else ""}"><div class="bl"><span>{esc(it["label"])}</span>'
                        f'<span>{esc(it.get("display", it["value"]))}{unit}</span></div>'
                        f'<div class="bt"><i style="width:{it["value"] / mx * 100:.1f}%"></i></div></div>')
        return f'<div class="bars">{"".join(rows)}</div>'
    if t == "timeline":
        rows = []
        for it in v["items"]:
            rows.append(f'<div class="tli{" on" if it.get("on") else ""}"><span class="d">{esc(it["date"])}</span>'
                        f'<span class="dot"></span><span class="t">{esc(it["text"])}</span></div>')
        return f'<div class="tl">{"".join(rows)}</div>'
    if t == "number":
        unit = f'<small>{esc(v["unit"])}</small>' if v.get("unit") else ""
        cap = f'<div class="c">{esc(v["caption"])}</div>' if v.get("caption") else ""
        return f'<div class="bignum"><div class="n">{esc(v["value"])}{unit}</div>{cap}</div>'
    raise ValueError(f"알 수 없는 visual type: {t}")


# ---------- 장 만들기 ----------

def tag_html(post, s):
    cls = "tag urgent" if post["series"] == "긴급" else "tag"
    a = esc(s.get("tag") or post["series"])
    b = s.get("tag_sub")
    return f'<span class="{cls}"><b>{a}</b>{" · " + esc(b) if b else ""}</span>'


def mark_html():
    return '<div class="mark"><div class="m1"><i></i>TOKEN WAR</div><div class="m2">AI 전황</div></div>'


def cover_html(post, s, folder):
    layout = s.get("layout", "visual")
    sub = ""
    if s.get("sub"):
        parts = s["sub"].split(" · ", 1)
        sub = (f'<p class="csub"><b>{esc(parts[0])}</b> · {esc(parts[1])}</p>' if len(parts) == 2
               else f'<p class="csub">{esc(s["sub"])}</p>')
    text = (f'<div class="ctext"><div>{tag_html(post, s)}</div>'
            f'<h1 class="ctitle">{br(hl(s.get("title", ""), s.get("highlight")))}</h1>{sub}</div>')
    if layout == "word":
        words = s.get("wall") or [s["word"]]
        rows = []
        for r in range(14):
            row = [esc(words[(r * 3 + k) % len(words)]) for k in range(8)]
            if r == 2:
                row[3] = f'<span class="on">{esc(s["word"])}</span>'
            rows.append(f'<div>{"  ·  ".join(row)}</div>')
        wall = f'<div class="wall">{"".join(rows)}</div>'
        word = (f'<div class="word"><span class="lab">{esc(s.get("label", "AI 용어"))}</span>'
                f'<span class="w">{esc(s["word"])}</span>'
                f'{"<span class=wd>" + esc(s["word_desc"]) + "</span>" if s.get("word_desc") else ""}</div>')
        vis = f'<div class="vis" style="height:100%">{wall}{word}</div>'
        return f'<div class="slide cover">{vis}{text if s.get("title") else ""}{mark_html()}</div>'
    v = s.get("visual") or {"type": "monogram", "text": s.get("title", "?")[0]}
    dots = '<div class="dots"></div>' if v.get("type") != "image" else ""
    vis = f'<div class="vis">{dots}{visual_html(v, folder)}</div>'
    return f'<div class="slide cover">{vis}<div class="fade"></div>{text}{mark_html()}</div>'


def frame(n, total, inner, extra_cls=""):
    top = (f'<div class="top"><span class="b"><i></i>TOKEN WAR</span><span>{n:02d} / {total:02d}</span></div>')
    bot = (f'<div class="bot"><span>{esc(CONFIG["handle"])}</span>'
           f'<div class="pb"><i style="width:{round(n / total * 100)}%"></i></div></div>')
    return f'<div class="slide {extra_cls}">{top}<div class="inner">{inner}</div>{bot}</div>'


def body_html(post, s, n, total, folder):
    kind = s["kind"]
    parts = []
    if s.get("visual"):
        v = s["visual"]
        dots = '<div class="dots"></div>' if v.get("type") != "image" else ""
        parts.append(f'<div class="bvis">{dots}{visual_html(v, folder)}</div>')
    if kind != "stat":
        parts.append(f'<div class="num">{n:02d}</div>')
    if kind == "stat":
        unit = f'<small>{esc(s["unit"])}</small>' if s.get("unit") else ""
        parts.append(f'<div class="stat"><div class="n">{esc(s["value"])}{unit}</div>'
                     f'<div class="u">{esc(s.get("label", ""))}</div></div>')
    if s.get("heading"):
        parts.append(f'<h2 class="heading">{br(hl(s["heading"], s.get("highlight")))}</h2>')
    if kind == "steps":
        items = "".join(
            f'<div class="step"><span class="k">{i}</span><div><div class="st">{esc(it["title"])}</div>'
            f'{"<div class=sx>" + esc(it["text"]) + "</div>" if it.get("text") else ""}</div></div>'
            for i, it in enumerate(s["items"], 1))
        parts.append(f'<div class="steps">{items}</div>')
    elif kind == "compare":
        cols = []
        for side in ("left", "right"):
            c = s[side]
            lis = "".join(f'<div class="ci">{esc(x)}</div>' for x in c["items"])
            cols.append(f'<div class="col{" on" if c.get("on") else ""}"><div class="cl">{esc(c["label"])}</div>{lis}</div>')
        parts.append(f'<div class="cmp">{"".join(cols)}</div>')
    if s.get("body"):
        parts.append(f'<p class="body">{br(esc(s["body"]))}</p>')
    if s.get("point"):
        parts.append(f'<div class="point"><span class="lbl">POINT</span><span class="txt">{br(esc(s["point"]))}</span></div>')
    justify = "flex-start" if s.get("visual") else "center"
    return frame(n, total, f'<div style="display:contents"></div>{"".join(parts)}').replace(
        '<div class="inner">', f'<div class="inner" style="justify-content:{justify}">', 1)


def clip_html(post, s, n, total):
    parts = [f'<div class="num">{n:02d}</div>']
    if s.get("heading"):
        parts.append(f'<h2 class="heading">{br(hl(s["heading"], s.get("highlight")))}</h2>')
    parts.append('<div class="clipbox"><span class="ph">▶ 인용 영상</span></div>')
    parts.append(f'<div class="clipsrc"><b>영상 출처</b> · {esc(s["source"])}</div>')
    if s.get("caption"):
        parts.append(f'<p class="body">{br(esc(s["caption"]))}</p>')
    return frame(n, total, "".join(parts))


def outro_html(post, n, total):
    srcs = " · ".join(esc(x["name"]) for x in post["sources"])
    date = post["date"].replace("-", ".")
    inner = (f'<h2 class="slogan">{hl(B["slogan"], B["slogan_highlight"])}</h2>'
             f'<div class="mark" style="position:static;align-items:flex-start"><div class="m1"><i></i>{esc(B["signature"])}</div></div>'
             f'<div class="cta">{esc(B["cta"])}</div>'
             f'<div class="src" style="margin-top:40px">출처: {srcs}<br>{date} 기준</div>')
    return frame(n, total, inner, "outro")


def build_page(post, folder):
    kind = post["type"]
    slides = post["slides"]
    total = len(slides) + 1
    parts = []
    for i, s in enumerate(slides, 1):
        if s["kind"] == "cover":
            parts.append(cover_html(post, s, folder))
        elif s["kind"] == "clip":
            parts.append(clip_html(post, s, i, total))
        else:
            parts.append(body_html(post, s, i, total, folder))
    parts.append(outro_html(post, total, total))
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{build_css(kind)}</style>'
            f'</head><body>{"".join(parts)}</body></html>')


# ---------- 촬영 ----------

async def shoot(page_html, out_dir, kind):
    from playwright.async_api import async_playwright

    w, h = SIZES[kind]
    tmp = out_dir / "_render.html"
    tmp.write_text(page_html, encoding="utf-8")
    async with async_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium")
        browser = await p.chromium.launch(executable_path=exe) if exe else await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        await pg.goto(tmp.as_uri())
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(400)
        # 글자 넘침·겹침 검사
        problems = await pg.evaluate(
            """() => [...document.querySelectorAll('.slide')].map((s, i) => {
                 const issues = [];
                 const inner = s.querySelector('.inner');
                 if (inner && inner.scrollHeight > inner.clientHeight + 2) issues.push('본문이 넘침');
                 const ct = s.querySelector('.ctext'), vis = s.querySelector('.vis');
                 if (ct) {
                   const t = ct.getBoundingClientRect();
                   if (t.top < s.getBoundingClientRect().top + 60) issues.push('표지 글이 너무 김');
                   const title = s.querySelector('.ctitle');
                   const lh = parseFloat(getComputedStyle(title).lineHeight);
                   if (title.getBoundingClientRect().height > lh * 2.5) issues.push('표지 제목이 3줄 이상');
                 }
                 const wide = [...s.querySelectorAll('h1,h2,p,.txt,.st,.ci')].some(e => e.scrollWidth > e.clientWidth + 2);
                 if (wide) issues.push('가로로 넘침');
                 return issues.length ? `${i + 1}번째 장: ${issues.join(', ')}` : null }).filter(Boolean)"""
        )
        if problems:
            await browser.close()
            tmp.unlink()
            return problems
        els = await pg.query_selector_all(".slide")
        sub = out_dir / ("slides" if kind == "carousel" else "frames")
        if sub.exists():
            shutil.rmtree(sub)
        sub.mkdir()
        for i, el in enumerate(els, 1):
            await el.screenshot(path=str(sub / f"{i:02d}.jpg"), type="jpeg", quality=92)
        await browser.close()
    tmp.unlink()
    return []


def main(folder):
    out_dir = Path(folder).resolve()
    post = json.loads((out_dir / "post.json").read_text(encoding="utf-8"))
    errors, warnings = check_post(post)
    for w in warnings:
        print("경고:", w)
    if errors:
        print("규칙 위반으로 렌더링 중단:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    if post["type"] == "video":
        src = out_dir / post["video"]["src"]
        if not src.exists():
            print(f"영상 파일 없음: {post['video']['src']}")
            sys.exit(1)
        from video import make_video_reel
        dur = make_video_reel(post, out_dir, CONFIG)
        print(f"영상 릴스 길이: {dur:.1f}초")
        print("완료:", out_dir)
        return
    for s in post["slides"]:
        if s.get("kind") == "clip" and not (out_dir / s["src"]).exists():
            print(f"인용 영상 파일 없음: {s['src']}")
            sys.exit(1)
    page = build_page(post, out_dir)
    problems = asyncio.run(shoot(page, out_dir, post["type"]))
    if problems:
        print("레이아웃 문제 → 문장을 줄이거나 장을 나눌 것:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    if post["type"] == "reel":
        from motion import make_motion_reel
        total = asyncio.run(make_motion_reel(page, post, out_dir, CONFIG))
        shutil.copy(sorted((out_dir / "frames").glob("*.jpg"))[0], out_dir / "cover.jpg")
        print(f"릴스 길이: {total:.1f}초")
    print("완료:", out_dir)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
