# 주간 계정 분석 (월요일, scripts/weekly-analysis.ps1이 claude -p로 부른다)

목표: 2026-12-16까지 @tokenwar_ai 팔로워 1만 명. 한국어로 쓴다. 토큰을 아끼기 위해 아래 파일만 읽고, 긴 표는 위쪽만 본다.

## 1. 읽기 (위쪽만)
- `data/benchmark_patterns.md` 처음 25줄 + '계정별 형식'·'빠르게 크는 계정' 표
- `data/followers.csv`(우리 팔로워), `data/performance.json`(우리 게시물 조회·공유·저장), `data/trends.md` 첫 3줄(목표 진행)
- `config.json` `benchmarks.accounts`, `data/benchmark_changes.md`(지난 변경), 지난 `data/weekly_insights.md`

## 2. 새 계정 찾기 (웹 검색 10회 이내)
- 조건: 한국어, AI·테크 정보, 팔로워 1만 이상, 최근 30일 안에 게시, 남의 영상을 그대로 퍼 오는 계정이 아님(직접 만든 카드·영상·직접 해 본 결과).
- 우선: 최근 몇 달 안에 1만을 넘은 빠른 성장 계정(인터뷰·뉴스레터·기사·소셜블레이드류 공개 페이지에서 확인). 확인 못 한 숫자는 "확인 못 함"이라고 쓴다.
- 이미 목록에 있거나 `data/benchmark_changes.md`에서 뺀 계정은 이유가 바뀌지 않았으면 다시 넣지 않는다.
- 인스타에 로그인하거나 어떤 계정에도 글·댓글·DM을 보내지 않는다. 공개 페이지만 읽는다.

## 3. 목록 고치기 (`config.json` `benchmarks.accounts`, 최대 15개)
- 추가: 최대 3개. 빼기: '계정별 형식'에서 최근 30일 게시 0개가 3주째, 또는 3주 연속 팔로워 1천 미만·조회 실패(파일 updated_at이 안 바뀜)인 계정.
- 15개를 넘으면 반응·성장이 가장 낮은 계정부터 뺀다. config.json의 다른 키는 건드리지 않는다.
- 바꾼 것은 `data/benchmark_changes.md` 맨 위 `## YYYY-MM-DD` 아래 "+ @계정: 이유(팔로워, 근거 주소)" / "- @계정: 이유"로 남긴다.
- config.json이 바뀌면 benchmarks.yml이 다시 돈다(Graph API 약 36회). 그래서 한 주에 한 번만 바꾼다.

## 4. `data/weekly_insights.md` 새로 쓰기 (40줄 이내)
첫 줄은 정확히 `# 주간 인사이트 (YYYY-MM-DD)` (오늘 날짜. 스크립트가 이 날짜로 이번 주에 했는지 본다).
1. **목표 진행**: 우리 팔로워, 지난주 대비 증가, 하루 필요 증가 vs 실제. 늦어지면 원인 한 줄.
2. **이번 주 우리에게 바로 적용할 3가지**: 각각 "무엇을 → 어떻게(칸·형식·첫 줄 예시) → 근거 숫자(배수, n, 계정 일치)". 우리 규칙(STYLE_GUIDE, CLAUDE.md 운영자 취향)과 부딪히면 쓰지 않는다.
3. **빠르게 크는 계정에서 배울 점**: 1~3줄, 계정과 숫자.
4. **벤치마크 목록 변경**: 이번 주 추가·제외와 이유 한 줄씩.
5. **확인 못 한 것**: 한두 줄.

## 5. 저장
`git add config.json data/weekly_insights.md data/benchmark_changes.md` → 커밋(한국어 "주간 계정 분석: …") → `git pull --rebase` → `git push origin main`. 다른 파일은 고치지 않는다.
