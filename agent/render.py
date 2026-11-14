"""post.json → 카드뉴스 JPEG / 릴스 MP4.

사용법:
    python agent/render.py posts/queue/<게시물 폴더>

결과:
    carousel: slides/01.jpg ... (1080x1350)
    reel:     frames/01.jpg ... (1080x1920), reel.mp4, cover.jpg  (카드형 모션 릴스, 선택)
    video:    reel.mp4, cover.jpg  (영상 프레임 릴스, video.py)

디자인 원칙 (STYLE_GUIDE.md 1-1장): 편집 디자인. 큰 활자, 선, 녹색 면.
알약 태그·둥근 카드·작은 대문자 라벨·가짜 UI 화면·점 무늬·진행 바 같은 'AI 디자인 티'는 쓰지 않는다.

표지 유형(cover.layout): big, list, image
본문 유형(kind): body, steps, compare, stat
그림(visual): image, bars, timeline
자세한 형식은 TEMPLATES.md.
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
@import url('FONTS/black-han-sans/index.css');
@font-face{font-family:'Wanted';src:url('FONTS/WantedSans-Medium.otf');font-weight:500}
@font-face{font-family:'Wanted';src:url('FONTS/WantedSans-SemiBold.otf');font-weight:600}
@font-face{font-family:'Wanted';src:url('FONTS/WantedSans-Bold.otf');font-weight:700}
@font-face{font-family:'Wanted';src:url('FONTS/WantedSans-ExtraBold.otf');font-weight:800}
*{box-sizing:border-box}
html,body{margin:0;background:#000}
.slide{width:Wpx;height:Hpx;background:BG;color:TEXT;font-family:'Wanted',sans-serif;position:relative;overflow:hidden;
  word-break:keep-all;overflow-wrap:break-word;margin-bottom:20px}
.hl{color:ACCENT}
.disp{font-family:'Black Han Sans','Wanted',sans-serif;font-weight:400}

/* 브랜드: 왼쪽 아래 작은 글자 하나 */
.brand{position:absolute;left:PADXpx;bottom:BRANDYpx;font-family:'Black Han Sans';font-size:30px;color:ACCENT;letter-spacing:.01em}

/* 표지 */
.vis{position:absolute;left:0;right:0;top:0;height:VISHpx;overflow:hidden}
.vis img{width:100%;height:100%;object-fit:cover;display:block}
.vis .shade{position:absolute;left:0;right:0;bottom:0;height:45%;background:linear-gradient(to bottom,rgba(10,11,10,0),BG)}
.big{position:absolute;left:PADXpx;top:BIGTOPpx;font-family:'Black Han Sans';color:ACCENT;line-height:.86;letter-spacing:-.04em;white-space:nowrap}
.bignote{position:absolute;left:PADXpx;font-size:36px;font-weight:700;color:TEXT}
.covlist{position:absolute;left:PADXpx;right:PADXpx;top:LISTTOPpx;display:flex;flex-direction:column}
.covlist div{display:flex;align-items:baseline;gap:28px;padding:20px 0;border-top:3px solid ACCENT;font-family:'Black Han Sans';font-size:58px;line-height:1.1}
.covlist div:last-child{border-bottom:3px solid ACCENT}
.covlist b{font-weight:400;color:ACCENT;min-width:48px}
.ctext{position:absolute;left:PADXpx;right:PADXpx;bottom:CTEXTBpx;display:flex;flex-direction:column;gap:22px}
.ctitle{margin:0;font-family:'Black Han Sans';font-weight:400;font-size:CTITLEpx;line-height:1.16;letter-spacing:-.02em;text-wrap:balance}
.ctitle .pre{color:ACCENT}
.csub{margin:0;font-size:CSUBpx;font-weight:600;color:#B9C2BD}
.rule{height:6px;background:ACCENT;width:100%}

/* 본문 장 */
.inner{position:absolute;left:PADXpx;right:PADXpx;top:INTOPpx;bottom:INBOTpx;display:flex;flex-direction:column;justify-content:center;gap:34px;overflow:hidden}
.heading{margin:0;font-family:'Black Han Sans';font-weight:400;font-size:HEADpx;line-height:1.2;letter-spacing:-.02em;text-wrap:balance}
.body{margin:0;font-size:BODYpx;font-weight:500;line-height:1.62;color:#CFD6D2;text-wrap:pretty}
.pull{border-top:6px solid ACCENT;padding-top:22px;font-family:'Black Han Sans';font-size:PULLpx;line-height:1.3;color:ACCENT;text-wrap:balance}
.bvis{height:BVISpx;flex:none;position:relative;overflow:hidden}
.bvis img{width:100%;height:100%;object-fit:cover}
.steps{display:flex;flex-direction:column}
.step{display:grid;grid-template-columns:76px 1fr;gap:10px;padding:24px 0;border-top:2px solid #2A3530}
.step:last-child{border-bottom:2px solid #2A3530}
.step .k{font-family:'Black Han Sans';font-size:60px;line-height:1;color:ACCENT}
.step .st{font-size:STEPTpx;font-weight:800;line-height:1.3}
.step .sx{font-size:STEPXpx;font-weight:500;color:#AEB8B2;line-height:1.5;margin-top:6px}
.cmp{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:0}
.cmp .col{padding:6px 34px 6px 0;display:flex;flex-direction:column;gap:16px}
.cmp .col+.col{padding:6px 0 6px 34px;border-left:3px solid ACCENT}
.cmp .cl{font-family:'Black Han Sans';font-size:44px;color:MUTED}
.cmp .col.on .cl{color:ACCENT}
.cmp .ci{font-size:CMPpx;font-weight:600;line-height:1.45;color:#DDE4E0}
.stat .n{font-family:'Black Han Sans';font-size:STATpx;line-height:.9;color:ACCENT;letter-spacing:-.04em;white-space:nowrap}
.stat .n small{font-size:.45em;margin-left:6px}
.stat .u{font-size:36px;font-weight:700;color:TEXT;margin-top:18px}
.bars{display:flex;flex-direction:column;gap:22px;width:100%}
.brow .bl{display:flex;justify-content:space-between;font-size:30px;font-weight:700;color:#CFD6D2;margin-bottom:8px}
.brow .bt{height:30px;background:#1B231F}
.brow .bt i{display:block;height:100%;background:#4A5A50}
.brow.on .bl{color:TEXT}.brow.on .bt i{background:ACCENT}
.tl{display:flex;flex-direction:column;width:100%}
.tli{display:grid;grid-template-columns:150px 1fr;gap:20px;padding:20px 0;border-top:2px solid #2A3530;align-items:baseline}
.tli:last-child{border-bottom:2px solid #2A3530}
.tli .d{font-family:'Black Han Sans';font-size:34px;color:MUTED}
.tli .t{font-size:34px;font-weight:700;line-height:1.35;color:#CFD6D2}
.tli.on .d{color:ACCENT}.tli.on .t{color:TEXT}

/* 인용 영상 장면 (카드형 릴스) */
.clipbox{flex:none;margin:0 -PADXpx;height:CLIPHpx;background:#141c17;display:flex;align-items:center;justify-content:center;position:relative}
.clipbox .ph{font-family:'Black Han Sans';font-size:40px;color:#4a5a50}
.clipsrc{font-size:28px;font-weight:700;color:MUTED;margin-top:-10px}
.clipsrc b{color:ACCENT}

/* 마지막 장: 녹색 면 */
.outro{background:ACCENT;color:BG}
.outro .inner{justify-content:flex-end;gap:40px}
.slogan{margin:0;font-family:'Black Han Sans';font-weight:400;font-size:SLOGANpx;line-height:1.12;letter-spacing:-.03em;white-space:pre-line}
.outro .who{font-family:'Black Han Sans';font-size:44px}
.outro .cta{font-size:34px;font-weight:800}
.outro .src{font-size:22px;line-height:1.55;font-weight:600;opacity:.8;border-top:3px solid BG;padding-top:20px}
.outro .brand{color:BG}
"""

DIMS = {
    "carousel": dict(PADX=72, BRANDY=60, VISH=860, BIGTOP=96, LISTTOP=120, CTEXTB=150, CTITLE=80, CSUB=32,
                     INTOP=110, INBOT=140, HEAD=76, BODY=40, PULL=50, BVIS=440, STEPT=38, STEPX=31,
                     CMP=32, STAT=230, SLOGAN=104, CLIPH=608),
    "reel": dict(PADX=80, BRANDY=330, VISH=1200, BIGTOP=260, LISTTOP=300, CTEXTB=420, CTITLE=92, CSUB=36,
                 INTOP=260, INBOT=420, HEAD=84, BODY=46, PULL=56, BVIS=560, STEPT=44, STEPX=36,
                 CMP=36, STAT=250, SLOGAN=112, CLIPH=608),
}


def build_css(kind):
    w, h = SIZES[kind]
    c = CSS.replace("FONTS", FONTS)
    for k, v in sorted(DIMS[kind].items(), key=lambda kv: -len(kv[0])):
        c = c.replace(f"{k}px", f"{v}px")
    c = c.replace("width:Wpx", f"width:{w}px").replace("height:Hpx", f"height:{h}px")
    for k, v in [("ACCENT", B["accent"]), ("MUTED", B["muted"]), ("TEXT", B["text"]), ("BG", B["bg"])]:
        c = c.replace(k, v)
    return c


# ---------- 그림 ----------

def img_uri(folder, src):
    p = (folder / src).resolve()
    if not p.exists():
        raise FileNotFoundError(f"이미지 없음: {src}")
    return p.as_uri()


def visual_html(v, folder):
    t = v.get("type")
    if t == "image":
        return f'<img src="{img_uri(folder, v["src"])}" style="object-fit:{v.get("fit", "cover")}">'
    if t == "bars":
        mx = max(it["value"] for it in v["items"]) or 1
        unit = esc(v.get("unit", ""))
        rows = "".join(
            f'<div class="brow{" on" if it.get("on") else ""}"><div class="bl"><span>{esc(it["label"])}</span>'
            f'<span>{esc(it.get("display", it["value"]))}{unit}</span></div>'
            f'<div class="bt"><i style="width:{it["value"] / mx * 100:.1f}%"></i></div></div>'
            for it in v["items"])
        return f'<div class="bars">{rows}</div>'
    if t == "timeline":
        rows = "".join(
            f'<div class="tli{" on" if it.get("on") else ""}"><span class="d">{esc(it["date"])}</span>'
            f'<span class="t">{esc(it["text"])}</span></div>' for it in v["items"])
        return f'<div class="tl">{rows}</div>'
    raise ValueError(f"알 수 없는 visual type: {t}")


# ---------- 장 만들기 ----------

def brand_html():
    return '<div class="brand">TOKEN WAR</div>'


def cover_html(post, s, folder):
    layout = s.get("layout", "big")
    series = s.get("series_label", post["series"])
    pre = f'<span class="pre">[{esc(series)}]</span> ' if series else ""
    sub = f'<p class="csub">{esc(s["sub"])}</p>' if s.get("sub") else ""
    text = (f'<div class="ctext"><h1 class="ctitle">{pre}{br(hl(s.get("title", ""), s.get("highlight")))}</h1>'
            f'{sub}</div>')
    if layout == "image":
        vis = (f'<div class="vis">{visual_html(s["visual"], folder)}<div class="shade"></div></div>')
        return f'<div class="slide">{vis}{text}{brand_html()}</div>'
    if layout == "list":
        items = "".join(f'<div><b>{i}</b><span>{esc(x)}</span></div>' for i, x in enumerate(s["items"], 1))
        return f'<div class="slide"><div class="covlist">{items}</div>{text}{brand_html()}</div>'
    # big: 화면을 꽉 채우는 큰 글자 (숫자나 단어). 가장자리에서 잘려도 된다.
    big = esc(s["big"])
    size = s.get("big_size") or (520 if len(s["big"]) <= 3 else 380 if len(s["big"]) <= 5 else 280)
    note = f'<div class="bignote" style="top:{96 + int(size * 0.9) + 26}px">{esc(s["big_note"])}</div>' if s.get("big_note") else ""
    return (f'<div class="slide"><div class="big" style="font-size:{size}px">{big}</div>{note}'
            f'{text}{brand_html()}</div>')


def frame(inner, extra_cls=""):
    return f'<div class="slide {extra_cls}"><div class="inner">{inner}</div>{brand_html()}</div>'


def body_html(post, s, n, total, folder):
    kind = s["kind"]
    parts = []
    if s.get("visual"):
        v = s["visual"]
        if v.get("type") == "image":
            parts.append(f'<div class="bvis">{visual_html(v, folder)}</div>')
        else:
            parts.append(visual_html(v, folder))
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
        parts.append(f'<div class="pull">{br(esc(s["point"]))}</div>')
    return frame("".join(parts))


def clip_html(post, s, n, total):
    parts = []
    if s.get("heading"):
        parts.append(f'<h2 class="heading">{br(hl(s["heading"], s.get("highlight")))}</h2>')
    parts.append('<div class="clipbox"><span class="ph">인용 영상</span></div>')
    parts.append(f'<div class="clipsrc"><b>출처</b> {esc(s["source"])}</div>')
    if s.get("caption"):
        parts.append(f'<p class="body">{br(esc(s["caption"]))}</p>')
    return frame("".join(parts))


def outro_html(post, n, total):
    srcs = " · ".join(esc(x["name"]) for x in post["sources"])
    date = post["date"].replace("-", ".")
    inner = (f'<h2 class="slogan">{esc(B["slogan"])}</h2>'
             f'<div><div class="who">{esc(CONFIG["handle"])}</div><div class="cta">{esc(B["cta"])}</div></div>'
             f'<div class="src">출처 {srcs} · {date} 기준</div>')
    return frame(inner, "outro")


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
                   if (title.getBoundingClientRect().height > lh * 3.5) issues.push('표지 제목이 4줄 이상');
                 }
                 const wide = [...s.querySelectorAll('h1,h2,p,.pull,.st,.ci')].some(e => e.scrollWidth > e.clientWidth + 2);
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
