# 챗봇 스트리밍 연동 — 프론트/게이트웨이 스펙

백엔드가 `POST /ai/chatbot/stream`에서 SSE로 답변을 실시간 전송한다.
프론트·게이트웨이에서 아래를 반영하면 타이핑되듯 나오고, 마크다운이 굵게 렌더된다.

## 1. 게이트웨이(nginx) — /b/ai 블록에 버퍼링 해제

`location ~ ^/b/ai(/.*)?$` 블록에 추가:
```
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 120s;
```
(이거 없으면 nginx가 응답을 모아 한 번에 보내 스트리밍이 안 보인다.
 백엔드가 `X-Accel-Buffering: no` 헤더도 보내지만, nginx 설정으로 확실히 해두는 게 안전.)

## 2. SSE 형식

```
data: {"delta": "탄수화물은"}

data: {"delta": " 에너지원이에요"}

data: {"done": true, "cs-partner": "당당봇", "time": "...", "is-img": false}
```

- `delta`: 이어붙여 화면에 표시
- `done`: 스트림 종료 + 메타(cs-partner 등) 반영
- `error`: `{"error": "...", "state": "error"}` → 에러 표시

## 3. 프론트 수신 예시 (fetch reader)

```js
const res = await fetch("/b/ai/chatbot/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ msg, ...(token ? { usr: token } : {}) }),
});

const reader = res.body.getReader();
const decoder = new TextDecoder();
let buf = "", answer = "";

while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buf += decoder.decode(value, { stream: true });

  // "\n\n"로 구분된 완성 이벤트만 처리하고 나머지는 버퍼에 남긴다
  let idx;
  while ((idx = buf.indexOf("\n\n")) !== -1) {
    const line = buf.slice(0, idx);
    buf = buf.slice(idx + 2);
    const m = line.match(/^data: (.*)$/s);
    if (!m) continue;
    const evt = JSON.parse(m[1]);
    if (evt.delta) { answer += evt.delta; render(answer); }
    if (evt.done)  { setLoading(false); /* "답변 준비 중" 로딩 끄기 + 메타(cs-partner 등) 반영, 종료 */ }
    if (evt.error) { setLoading(false); /* 에러 표시 */ }
  }
}
```

## 4. 마크다운 렌더링 (굵게 표시)

누적 `answer`를 `react-markdown` 등으로 렌더 → `**당류**`가 굵게, `## 제목`이 크게 표시.
(스트리밍 경로는 백엔드가 마크다운을 그대로 보낸다. 별표 제거 안 함.
 기존 비스트리밍 `/b/ai/chatbot`은 백엔드가 별표를 제거하므로, 스트리밍으로 전환하면
 마크다운 렌더링을 프론트가 맡는 것으로 역할이 바뀐다.)

## 5. 인증

- 로그인 상태면 `usr`에 JWT를 넣어 보낸다(개인화).
- 토큰 없으면 `usr` 생략 → 익명으로 일반 답변(백엔드가 허용).
- 무효 토큰이면 스트림 시작 전 **HTTP 401**(SSE 아님)로 응답하므로, 스트림 열기 전에 상태코드를 확인한다.

## 6. 폴백

기존 JSON 경로 `POST /b/ai/chatbot`도 그대로 동작하므로,
스트리밍 미구현/실패 시 폴백으로 쓸 수 있다.
