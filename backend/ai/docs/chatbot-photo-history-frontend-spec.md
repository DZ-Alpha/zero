# 챗봇 사진 이미지 복원 — 프론트 연동 스펙 (담당자 전달)

백엔드에 **사진 첨부 대화의 이미지 복원**이 구현됐다. 지금까지는 챗봇을 껐다
켜면 텍스트(질문·답변)만 복원되고 사진은 사라졌는데, 이제 `/history`가 사진의
**서명 URL(imageUrl)**을 함께 내려준다. 프론트에서 아래 한 가지만 반영하면
복원 시 사진도 다시 보인다.

> 이 문서는 **구현·테스트 완료 후의 확정 스펙**이다(백엔드 배포 후 동작).

## 무엇이 바뀌었나 (백엔드)

`GET /b/ai/chatbot/history` 응답의 각 메시지에 **`imageUrl?: string`** 필드가
추가됐다. 사진이 첨부됐던 사용자 메시지에만 붙는다.

```json
{
  "messages": [
    {
      "role": "user",
      "text": "이거 당류 많아?",
      "imageUrl": "/b/chat-photos/7/8f3a....png?X-Amz-Algorithm=...&X-Amz-Signature=..."
    },
    { "role": "assistant", "text": "초코케이크네요! 당류는 약 45g으로 보여요." }
  ]
}
```

- `imageUrl`은 **사진이 있는 메시지에만** 존재(없으면 필드 자체가 없음).
- 값은 **`/b/...` 상대경로**(짧은 만료 서명 URL). 식단(diet) 사진과 **동일한
  방식**이다.
- 질문 없이 사진만 올린 턴도 이제 저장·복원된다(그 경우 `text`는 빈 문자열,
  `imageUrl`만 있음).

## 프론트가 할 일 (1가지)

`ChatPanel`의 대화 복원 코드(`getChatHistory().then(...)`)에서 현재 `text`만
매핑하는 것을 `imageUrl`도 포함하도록 확장한다.

```js
// 변경 전
setMessages(history.map((item) => ({
  role: item.role === "user" ? "question" : "answer",
  text: item.text,
})));

// 변경 후
setMessages(history.map((item) => ({
  role: item.role === "user" ? "question" : "answer",
  text: item.text,
  ...(item.imageUrl ? { imageUrl: item.imageUrl } : {}),
})));
```

실시간 전송 경로는 이미 `imageUrl`을 다루므로(`{ role, text, imageUrl }`),
말풍선 렌더 코드(`{message.imageUrl && <img ... />}`)는 그대로 재사용된다.

## 주의사항

- **`imageUrl`을 그대로 `<img src>`에 넣는다.** 절대 URL로 바꾸거나 경로를
  rewrite하지 말 것 — SigV4 서명은 경로·호스트를 포함하므로 한 글자만 바뀌어도
  `SignatureDoesNotMatch`로 깨진다. `/b/...` 상대경로 그대로 두면 프론트의
  `app/b/[...path]/route.ts` 프록시가 서버사이드로 중계한다(식단 사진과 동일).
- **사진 원본은 24시간 보관**된다. 그 뒤 만료된 사진은 `imageUrl`을 열면 404가
  날 수 있으니 `<img onError>`로 깨진 이미지 숨김 처리 권장(텍스트는 정상 복원됨).
- `getChatHistory`의 응답 타입에 `imageUrl?: string`를 추가한다.

## 체크리스트 (프론트 담당)

- [ ] `getChatHistory` 응답 타입에 `imageUrl?: string` 추가
- [ ] `ChatPanel` 복원 매핑에 `imageUrl` 포함
- [ ] 말풍선 렌더가 복원된 `imageUrl`도 표시하는지 확인(기존 렌더 재사용)
- [ ] (권장) `<img onError>`로 만료(404) 사진 숨김 처리
