# 릴스용 영상 넣는 곳

여기에 넣은 영상이 다음 날 영상 프레임 릴스가 된다.

**기본: 인용** (원본에서 15초 이하 한 구간)

```json
{
  "rights": "quote",
  "credit": "Dwarkesh Patel (팟캐스터)",
  "source_url": "https://www.youtube.com/watch?v=...",
  "start": 62.0, "end": 75.0,
  "note": "어떤 장면인지, 왜 쓰고 싶은지 한두 줄"
}
```

- 영상 파일은 원본 그대로 넣어도 된다. `start`~`end` 구간만 잘라 쓴다.
- 화면에 "출처 · credit"이 크게 고정되고, 캡션에도 들어간다.
- 15초를 넘으면 에이전트가 핵심 구간으로 줄인다.

허락받은 영상(`permission`)이나 직접 만든 영상(`own`)은 길이 제한 없이 쓴다. 이때는 `rights_note`에 허락받은 날짜와 경로를 적는다.
