# 릴스용 영상 넣는 곳

여기에 넣은 영상이 다음 날 영상 프레임 릴스가 된다.

**허락받은 영상 / 직접 만든 영상** (영상 전체 사용):

```json
{
  "rights": "permission",
  "credit": "@원작자",
  "rights_note": "11/15 인스타 DM으로 허락",
  "source_url": "https://www.instagram.com/p/...",
  "start": 0, "end": null,
  "note": "어떤 영상인지 한두 줄"
}
```
`rights`: own(직접 만듦) / permission(원작자 허락) / license(재사용 허락 라이선스)

---

**허락 없이 짧게 인용하는 경우** (카드형 릴스 안의 10초 이하 장면):

1. 영상 파일: `이름.mp4` (휴대폰 화면 녹화도 가능)
2. 설명 파일: `이름.json`

```json
{
  "source": "OpenAI 공식 YouTube",
  "source_url": "https://www.youtube.com/watch?v=...",
  "start": 12.0,
  "end": 20.0,
  "note": "어떤 장면인지, 왜 쓰고 싶은지 한두 줄"
}
```

- `start`~`end`는 10초 이하로. 짧을수록 인용으로 인정받기 쉽다.
- 영상을 통째로 올리는 용도로는 쓰지 않는다. 우리 해설이 주인공이고 영상은 근거 자료.
