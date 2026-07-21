"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { sendChatbotMessage, streamChatbotMessage } from "@/lib/api/zerocheck";

type ChatMessage = { role: "question" | "answer"; text: string };

const fallbackAnswer = "질문을 기준으로 성분표를 쉽게 풀어드릴게요. 지금은 상담 기능을 준비하고 있어서, 제품 검색과 레시피에서 성분 정보를 먼저 확인해 주세요.";

// chatbot-streaming-design.md §8-3 — 백엔드가 마크다운을 그대로 보내므로
// **볼드**만 인라인으로 굵게 표시한다. 챗봇 답변엔 헤딩/리스트가 거의 안 나와서
// react-markdown 같은 별도 의존성 없이 이 정도로 충분하다고 판단했다.
function renderInlineMarkdown(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "question", text: "탄수화물과 당류는 어떻게 달라?" },
    { role: "answer", text: "당류는 탄수화물 중 단맛을 내는 단순당을 말해요. 제품을 비교할 땐 총 탄수화물과 당류를 함께 보세요." },
  ]);
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, pending]);

  async function send() {
    const question = value.trim();
    if (!question || pending) return;
    setValue("");
    setMessages((items) => [...items, { role: "question", text: question }]);
    setPending(true);

    // chatbot-streaming-design.md — /ai/chatbot/stream으로 토큰 단위로 받아 답변
    // 말풍선을 그때그때 채운다. 스트림이 한 글자도 못 받고 끊기면(연결 실패,
    // 시작하자마자 에러) 기존 비스트리밍 /ai/chatbot로 한 번 더 시도하고,
    // 그것도 안 되면 안내 답변으로 폴백한다.
    let streamedText = "";
    let messageStarted = false;

    function appendAnswer(text: string) {
      streamedText += text;
      // messageStarted는 setMessages 콜백이 아니라 여기서 직접(동기적으로) 바꾼다 —
      // React가 업데이트 함수 실행을 지연시켜도 아래 `if (!messageStarted)` 체크가
      // 항상 최신 값을 보게 하기 위함.
      const isFirstChunk = !messageStarted;
      messageStarted = true;
      setMessages((items) => {
        if (isFirstChunk) return [...items, { role: "answer", text: streamedText }];
        const next = [...items];
        next[next.length - 1] = { role: "answer", text: streamedText };
        return next;
      });
    }

    // AI팀 리포트(streaming-frontend-spec.md §3) — delta만 처리하고 done/error를
    // 무시해서 "답변을 준비하고 있어요" 로딩이 안 꺼지는 버그가 있었다. 스트림이
    // 끝나길 기다리지 않고 done/error를 받는 즉시 로딩을 꺼준다.
    try {
      await streamChatbotMessage(question, getAccessToken(), (event) => {
        if (event.type === "delta") appendAnswer(event.text);
        else if (event.type === "done" || event.type === "error") setPending(false);
      });
    } catch {
      // 스트리밍 자체가 실패 — 아래에서 messageStarted 여부로 폴백 처리
    }

    if (!messageStarted) {
      let answer = fallbackAnswer;
      try {
        const reply = await sendChatbotMessage(question, getAccessToken());
        if (reply.status !== "PREPARING" && reply.msg) answer = reply.msg;
      } catch {
        // 상담 백엔드 미기동 — 폴백 답변 유지
      }
      setMessages((items) => [...items, { role: "answer", text: answer }]);
    }
    setPending(false);
  }

  return (
    <section className="chat-panel">
      <div className="chat-head"><span className="brand-mark"><i /></span><div><b>당당 상담</b><small>영양·성분 질문과 사진 검색</small></div></div>
      <div className="chat-log" ref={logRef}>
        {messages.map((message, index) => <p className={message.role} key={`${message.role}-${index}`}>{renderInlineMarkdown(message.text)}</p>)}
        {pending && <p className="answer is-pending">답변을 준비하고 있어요…</p>}
      </div>
      <div className="chat-compose">
        <input aria-label="질문" value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => event.key === "Enter" && send()} placeholder="궁금한 성분이나 제품을 물어보세요" />
        <button onClick={send} disabled={pending}>{pending ? "전송 중" : "보내기"}</button>
      </div>
    </section>
  );
}
