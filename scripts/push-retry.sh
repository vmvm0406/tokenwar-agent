#!/usr/bin/env bash
# 커밋해 둔 결과를 지금 브랜치에 올린다: git pull --rebase → git push, 최대 5번 (5·10·15·20초 쉬고 다시).
# 다른 워크플로가 그사이 main에 push하면 push가 거절되는데, 한 번만 시도하면 결과가 사라진다
# (2026-11-17 FPS 릴스: 게시 기록 push 실패 → 다음 실행이 같은 릴스를 또 올림).
# 다 실패하면 ::error::를 남기고 1로 끝난다 (조용히 넘어가지 않게).
# 쓰는 법 (GitHub Actions run 단계): bash scripts/push-retry.sh
set -u
tries=${PUSH_TRIES:-5}
for i in $(seq 1 "$tries"); do
  if git pull --rebase; then
    if git push; then
      echo "push 완료 ($i번째 시도)"
      exit 0
    fi
  else
    git rebase --abort 2>/dev/null || true
  fi
  if [ "$i" -lt "$tries" ]; then
    echo "push 실패, $((i * 5))초 뒤 다시 ($i/$tries)"
    sleep $((i * 5))
  fi
done
echo "::error::push가 ${tries}번 모두 실패함. 결과 커밋이 main에 없음 (중복 게시 위험, 로그 확인)"
exit 1
