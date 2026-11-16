"""검토 페이지: 열린 검토 PR(post/*)의 게시물을 휴대폰에서 보고 승인하러 가는 곳.

GitHub PR 화면에서는 릴스 영상과 카드 장을 바로 볼 수 없어서 만든다.
열린 PR 중 head 브랜치가 post/ 로 시작하는 것들을 읽어 docs/review/index.html을 만든다.
GitHub Pages: https://vmvm0406.github.io/tokenwar-agent/review/

- 미디어는 raw.githubusercontent.com으로 PR head 커밋에 고정해서 보여 준다 (저장소에 미디어를 또 올리지 않는다).
  jsDelivr는 저장소 전체가 50MB를 넘는 커밋이면 403("Package size exceeded")을 내서 쓰지 않는다.
  raw는 파일당 100MB까지, 영상 구간 요청(Range)도 된다.
- 페이지에서 직접 merge하지 않는다. 토큰·비밀값은 페이지에 넣지 않는다. 버튼은 PR 주소로 보낼 뿐.
- 인증: 환경 변수 GITHUB_TOKEN/GH_TOKEN, 없으면 로컬 `gh auth token`.
- 내용(갱신 시각 제외)이 그대로면 파일을 다시 쓰지 않는다 (30분마다 쓸데없는 커밋 막기).

사용: py -3.12 agent/review_page.py
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "review" / "index.html"
REPO = os.environ.get("GITHUB_REPOSITORY", "vmvm0406/tokenwar-agent")
PAGES = "https://vmvm0406.github.io/tokenwar-agent"
KST = timezone(timedelta(hours=9))
STAMP_RE = re.compile(r"<!--stamp-->.*?<!--/stamp-->", re.S)
DAYS = "월화수목금토일"


def _token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    gh = shutil.which("gh")
    if gh:
        r = subprocess.run([gh, "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    sys.exit("GitHub 인증이 없습니다 (GITHUB_TOKEN 또는 gh auth login)")


TOKEN = None


def api(path, raw=False):
    global TOKEN
    TOKEN = TOKEN or _token()
    req = urllib.request.Request(
        f"https://api.github.com/{path.lstrip('/')}",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tokenwar-review-page"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data.decode("utf-8") if raw else json.loads(data)


def api_pages(path):
    out, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        chunk = api(f"{path}{sep}per_page=100&page={page}")
        out += chunk
        if len(chunk) < 100:
            return out
        page += 1


def cdn(sha, folder, name):
    return f"https://raw.githubusercontent.com/{REPO}/{sha}/posts/queue/{folder}/{name}"


def when(s):
    try:
        d = datetime.fromisoformat(s).astimezone(KST)
    except (TypeError, ValueError):
        return "게시 시각 없음"
    return f"{d.month}월 {d.day}일({DAYS[d.weekday()]}) {d:%H:%M}"


def e(s):
    return html.escape(str(s or ""))


def text_block(s):
    return e(s).replace("\n", "<br>")


def collect():
    """열린 post/* PR과 그 PR이 추가·수정한 게시물 목록."""
    prs = []
    for pr in api_pages(f"repos/{REPO}/pulls?state=open"):
        if not pr["head"]["ref"].startswith("post/"):
            continue
        n, sha = pr["number"], pr["head"]["sha"]
        files = api_pages(f"repos/{REPO}/pulls/{n}/files")
        folders = []
        for f in files:
            m = re.match(r"posts/queue/([^/]+)/", f["filename"])
            if m and f["status"] != "removed" and m.group(1) not in folders:
                folders.append(m.group(1))
        tree = api(f"repos/{REPO}/git/trees/{sha}?recursive=1")["tree"]
        paths = {t["path"]: t.get("size") for t in tree if t["type"] == "blob"}
        posts = []
        for folder in folders:
            base = f"posts/queue/{folder}/"
            if base + "post.json" not in paths:
                continue
            try:
                post = json.loads(api(f"repos/{REPO}/contents/{base}post.json?ref={sha}", raw=True))
            except Exception as ex:  # 깨진 post.json도 페이지는 만든다
                post = {"title": f"post.json을 읽지 못함: {ex}"}
            slides = sorted(p[len(base) + 7:] for p in paths
                            if p.startswith(base + "slides/") and p.endswith(".jpg"))
            # 카드뉴스 첫 장 영상(slides/01.mp4): 같은 이름 jpg는 정지 화면(포스터)으로 쓴다
            slide_videos = {p[len(base) + 7:-4] for p in paths
                            if p.startswith(base + "slides/") and p.endswith(".mp4")}
            posts.append({"folder": folder, "post": post, "slides": slides, "slide_videos": slide_videos,
                          "reel": base + "reel.mp4" in paths,
                          "reel_size": paths.get(base + "reel.mp4") or 0,
                          "cover": base + "cover.jpg" in paths,
                          "dm": base + "dm.md" in paths})
        posts.sort(key=lambda p: p["post"].get("publish_at") or "")
        prs.append({"n": n, "title": pr["title"], "url": pr["html_url"], "sha": sha, "posts": posts})
    prs.sort(key=lambda p: p["n"])
    return prs


def render_post(pr, item):
    p, folder, sha = item["post"], item["folder"], pr["sha"]
    is_reel = p.get("type") in ("video", "reel")
    kind = "릴스" if is_reel else "카드뉴스"
    if p.get("format") == "howto":
        kind += " · 따라 하기"
    elif p.get("format") == "ask":
        kind += " · 질문"
    title = (p.get("thumb") or {}).get("title") if is_reel and not p.get("title") else p.get("title")
    if not title and p.get("slides"):
        title = p["slides"][0].get("title")
    h = [f'<article class="post" id="{e(folder)}">',
         f'<div class="meta"><span class="kind">{e(kind)}</span><span>{e(when(p.get("publish_at")))}</span></div>',
         f'<h3>{text_block(title)}</h3>']

    if is_reel:
        if item["reel"]:
            poster = f' poster="{cdn(sha, folder, "cover.jpg")}"' if item["cover"] else ""
            h.append(f'<video class="reel" controls playsinline preload="metadata"{poster} '
                     f'src="{cdn(sha, folder, "reel.mp4")}"></video>')
        else:
            h.append('<p class="warn">아직 렌더링 전입니다 (reel.mp4 없음). 몇 분 뒤 다시 보세요.</p>')
        if item["cover"]:
            h.append(f'<div class="label">썸네일</div><img class="cover" loading="lazy" alt="썸네일" '
                     f'src="{cdn(sha, folder, "cover.jpg")}">')
    else:
        if item["slides"]:
            n = len(item["slides"])
            h.append(f'<div class="label">옆으로 넘겨 보기 · {n}장</div><div class="slides">')
            for i, s in enumerate(item["slides"], 1):
                stem = s[:-4]
                if stem in item.get("slide_videos", ()):
                    h.append(f'<figure><video controls playsinline loop preload="metadata" '
                             f'poster="{cdn(sha, folder, "slides/" + s)}" src="{cdn(sha, folder, "slides/" + stem + ".mp4")}"></video>'
                             f'<figcaption>{i} / {n} · 영상 장</figcaption></figure>')
                    continue
                h.append(f'<figure><img loading="lazy" alt="{i}장" src="{cdn(sha, folder, "slides/" + s)}">'
                         f'<figcaption>{i} / {n}</figcaption></figure>')
            h.append("</div>")
        else:
            h.append('<p class="warn">아직 렌더링 전입니다 (slides 없음). 몇 분 뒤 다시 보세요.</p>')

    if p.get("caption"):
        h.append(f'<div class="label">캡션</div><div class="caption">{text_block(p["caption"].strip())}</div>')
    if p.get("hashtags"):
        h.append(f'<div class="tags">{e(" ".join(p["hashtags"]))}</div>')
    th = p.get("threads")
    if isinstance(th, dict) and th.get("text"):
        imgs = ", ".join("표지" if x == "cover" else f"{x}장" for x in th.get("images") or []) or "없음 (글만)"
        h.append(f'<div class="label">스레드 글 · 인스타 게시 뒤 자동 · 주제 {e(th.get("topic") or "AI Threads")} · 사진 {e(imgs)}</div>'
                 f'<div class="caption threads">{text_block(str(th["text"]).strip())}</div>')
        for i, r in enumerate(th.get("replies") or [], 1):
            h.append(f'<div class="reply"><span>답글 {i}</span> {text_block(str(r).strip())}</div>')
    links = []
    if p.get("source_url"):
        links.append((p.get("credit") or "원본 영상", p["source_url"]))
    for s in p.get("sources") or []:
        if isinstance(s, dict) and s.get("url"):
            links.append((s.get("name") or s["url"], s["url"]))
    if links:
        h.append('<div class="label">출처</div><ul class="src">')
        h += [f'<li><a href="{e(u)}" target="_blank" rel="noopener">{e(t)}</a></li>' for t, u in links]
        h.append("</ul>")
    if item["dm"] or p.get("dm"):
        kw = (p.get("dm") or {}).get("keyword", "자료")
        h.append(f'<p class="note">따라 하기: 댓글 \'{e(kw)}\' 자동 DM 설정 메모 '
                 f'<a href="https://github.com/{REPO}/blob/{sha}/posts/queue/{e(folder)}/dm.md" '
                 f'target="_blank" rel="noopener">dm.md</a> (merge 뒤 Zorcha에 넣기)</p>')
    h.append("</article>")
    return "\n".join(h)


CSS = """
:root{--bg:#0A0B0A;--fg:#F2F5F3;--dim:#8A928C;--line:#262A27;--g:#00FF66}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--fg)}
body{font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;line-height:1.6;font-size:15px;word-break:keep-all}
main{max-width:560px;margin:0 auto;padding:28px 16px 64px}
h1,h2,h3{font-family:'Black Han Sans',sans-serif;font-weight:400;margin:0}
h1{color:var(--g);font-size:34px;line-height:1.1}
.lead{color:var(--dim);margin:8px 0 0;font-size:13px}
a{color:var(--g)}
section.pr{border-top:2px solid var(--g);margin-top:36px;padding-top:16px}
.prno{color:var(--g);font-size:13px;font-weight:700;letter-spacing:.04em}
h2{font-size:22px;line-height:1.3;margin:4px 0 12px}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0 4px}
.btn{display:block;text-align:center;padding:13px 8px;font-weight:700;text-decoration:none;border:2px solid var(--g);color:var(--g)}
.btn.go{background:var(--g);color:#0A0B0A}
.post{border-top:1px solid var(--line);margin-top:20px;padding-top:16px}
.meta{display:flex;gap:12px;font-size:13px;color:var(--dim)}
.kind{color:var(--g);font-weight:700}
h3{font-size:21px;line-height:1.3;margin:6px 0 12px}
video.reel{display:block;width:100%;aspect-ratio:9/16;background:#000;border:1px solid var(--line)}
img.cover{display:block;width:62%;border:1px solid var(--line)}
.slides{display:flex;gap:8px;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;margin:0 -16px;padding:0 16px 6px}
.slides figure{flex:0 0 88%;margin:0;scroll-snap-align:center}
.slides img,.slides video{display:block;width:100%;aspect-ratio:4/5;object-fit:cover;background:#000;border:1px solid var(--line)}
.slides figcaption{font-size:12px;color:var(--dim);margin-top:4px}
.label{font-size:12px;color:var(--dim);margin:16px 0 6px;font-weight:700}
.caption{white-space:normal;font-size:14px;border-left:3px solid var(--g);padding-left:12px}
.tags{color:var(--g);font-size:14px;margin-top:8px}
.caption.threads{border-left-color:var(--fg)}
.reply{font-size:13px;margin:6px 0 0 15px;color:var(--dim);word-break:break-all}.reply span{color:var(--fg);font-weight:700}
ul.src{margin:0;padding-left:18px;font-size:13px}ul.src li{margin:2px 0;word-break:break-all}
.note{font-size:13px;color:var(--fg);margin-top:12px}
.warn{color:#FFD400;font-size:13px}
.empty{margin-top:40px;font-family:'Black Han Sans',sans-serif;font-size:24px;color:var(--dim)}
footer{margin-top:48px;font-size:12px;color:var(--dim)}
"""


def build(prs):
    body = []
    if not prs:
        body.append('<p class="empty">검토할 게시물 없음</p>')
    for pr in prs:
        body.append(f'<section class="pr"><div class="prno">PR #{pr["n"]} · 게시물 {len(pr["posts"])}개</div>'
                    f'<h2><a href="{e(pr["url"])}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">{e(pr["title"])}</a></h2>'
                    f'<div class="btns"><a class="btn go" href="{e(pr["url"])}" target="_blank" rel="noopener">승인(Merge)하러 가기</a>'
                    f'<a class="btn" href="{e(pr["url"])}#issuecomment-new" target="_blank" rel="noopener">고칠 점 남기기</a></div>')
        if not pr["posts"]:
            body.append('<p class="warn">이 PR에서 바뀐 게시물 폴더를 찾지 못했습니다.</p>')
        body += [render_post(pr, it) for it in pr["posts"]]
        body.append("</section>")
    now = datetime.now(KST)
    stamp = f"<!--stamp-->{now.year}년 {now.month}월 {now.day}일 {now:%H:%M} (한국 시간)<!--/stamp-->"
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>토큰전쟁 검토</title><meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><main>
<h1>검토할 게시물</h1>
<p class="lead">영상과 카드를 여기서 보고, 괜찮으면 PR에서 Merge를 누르세요. 게시는 Merge한 뒤 게시 시각에 자동으로 됩니다.</p>
{chr(10).join(body)}
<footer>마지막 갱신: {stamp} · 30분마다, PR이 바뀔 때마다 새로 만듭니다.</footer>
</main></body></html>
"""


def main():
    page = build(collect())
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if STAMP_RE.sub("", old) == STAMP_RE.sub("", page):
        print("검토 페이지: 바뀐 것 없음")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"검토 페이지 갱신: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
