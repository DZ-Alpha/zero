# 챗봇 대화 메모리 — 프론트 연동 스펙 (확정본)

백엔드에 대화 기억이 구현되어 배포 예정이다. 챗봇이 이전 대화를 기억하고
(예: "나 알레르기 있어" → "땅콩"이 맥락으로 이어짐), 페이지 이동·새로고침
후에도 화면에 대화가 복원된다. 프론트에서 아래 2가지를 반영하면 된다.

> 이 문서는 **구현이 끝난 뒤의 확정 스펙**이다(경로·필드 실제값). 기존
> `streaming-frontend-spec.md`(SSE 스트리밍)와 함께 본다.

## 동작 규칙 요약

- **대화 보관**: 마지막 대화 후 **24시간** 유지(대화할 때마다 갱신). 이후 자동 삭제.
- **기억 범위**: LLM은 최근 **6턴**(1턴=질문+답변)을 참고. 화면 복원은 최근 **20턴**까지.
- **대화방**: 사용자당 1개. 로그인=계정(user_id) 기준, 비로그인=`session_id` 기준.
- **Redis 장애 시**: 챗봇은 그대로 답한다(기억만 일시적으로 안 됨). 프론트 대응 불필요.

## 1. 요청에 `session_id` 추가

기존 채팅 요청(`POST /b/ai/chatbot`, `POST /b/ai/chatbot/stream`)의 JSON body에
`session_id`를 추가한다.

- **로그인 사용자**: `session_id` 불필요(보내도 무시됨). 기존처럼 `usr`(JWT)만
  넣으면 서버가 계정 기준으로 대화방을 만든다.
- **비로그인 사용자**: 프론트가 임시 세션 ID를 발급해 **localStorage에 저장**하고
  매 요청에 함께 보낸다. 페이지 이동·새로고침에도 **같은 값**을 유지해야 대화가 이어진다.

```js
// 앱 진입 시: 비로그인용 세션 ID 확보(없으면 발급해 저장)
function getGuestSessionId() {
  let id = localStorage.getItem("chat_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("chat_session_id", id);
  }
  return id;
}

// 채팅 요청 body
const body = {
  msg,
  ...(token
    ? { usr: token }                        // 로그인: JWT만
    : { session_id: getGuestSessionId() }), // 비로그인: 세션 ID
};
```

> 비로그인인데 `session_id`를 안 보내면 그 대화는 기억되지 않는다(단발 응답).
> 오류는 아니지만 맥락이 이어지지 않는다.

## 2. 화면 진입 시 이전 대화 복원 (`GET /b/ai/chatbot/history`)

채팅창을 열 때 호출해 이전 대화를 화면에 다시 그린다.

**요청 (쿼리 파라미터)**
- 로그인: `GET /b/ai/chatbot/history?usr=<JWT>`
- 비로그인: `GET /b/ai/chatbot/history?session_id=<localStorage 값>`

**응답**
```json
{
  "messages": [
    { "role": "user", "text": "나 알레르기 있어" },
    { "role": "assistant", "text": "어떤 성분에 알레르기가 있으신가요?" },
    { "role": "user", "text": "땅콩" },
    { "role": "assistant", "text": "땅콩 알레르기가 있으시군요. ..." }
  ]
}
```
- 최근 **20턴**(최대 40메시지)까지 **시간순**으로 온다.
- 대화가 없거나 24시간 지나 만료됐으면 `{"messages": []}`.
- `role`은 `"user"`(사용자) 또는 `"assistant"`(당당봇).

```js
// 채팅창 마운트 시 이전 대화 복원
const qs = token
  ? `usr=${encodeURIComponent(token)}`
  : `session_id=${encodeURIComponent(getGuestSessionId())}`;
const res = await fetch(`/b/ai/chatbot/history?${qs}`);
const { messages } = await res.json();
messages.forEach(m => renderMessage(m.role, m.text)); // user/assistant 구분해 렌더
```

## 3. 스트리밍과의 관계

스트리밍(`/b/ai/chatbot/stream`)은 기존 SSE 방식 그대로다. `session_id`만
추가하면 대화가 이어진다. 서버는 **답변이 다 끝난 뒤에** 그 턴을 저장하므로,
스트림 도중 끊기면 반쪽 대화가 저장되지 않는다.

## 4. 인증

- 로그인 상태면 `usr`에 JWT를 넣는다(개인화 + 계정 기준 대화방).
- 무효 토큰이면 서버가 **401**로 응답한다(채팅·history 공통). 스트림은 시작 전
  401이므로, 스트림 열기 전에 상태코드를 확인한다.
- 비로그인은 `session_id`만으로 동작한다(익명 허용).

## 체크리스트 (프론트 담당)

- [ ] `getGuestSessionId()`로 비로그인 세션 ID를 localStorage에 관리
- [ ] 채팅 요청 body에 `session_id`(비로그인) 추가
- [ ] 채팅창 진입 시 `GET /b/ai/chatbot/history` 호출해 이전 대화 복원
- [ ] 복원 시 `role`(user/assistant) 구분해 말풍선 렌더
