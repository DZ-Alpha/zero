"use client";

import { useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { sendChatbotMessage } from "@/lib/api/zerocheck";

type ChatMessage = { role: "question" | "answer"; text: string };

const fallbackAnswer = "질문을 기준으로 성분표를 쉽게 풀어드릴게요. 지금은 상담 기능을 준비하고 있어서, 제품 검색과 레시피에서 성분 정보를 먼저 확인해 주세요.";

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

    // MN-0111 /ai/chatbot — 백엔드가 아직 없어서 실패하면 안내 답변으로 폴백한다.
    let answer = fallbackAnswer;
    try {
      const reply = await sendChatbotMessage(question, getAccessToken());
      if (reply.status !== "PREPARING" && reply.msg) answer = reply.msg;
    } catch {
      // 상담 백엔드 미기동 — 폴백 답변 유지
    }
    setMessages((items) => [...items, { role: "answer", text: answer }]);
    setPending(false);
  }

  return (
    <section className="chat-panel">
      <div className="chat-head"><span className="brand-mark"><i /></span><div><b>당당 상담</b><small>영양·성분 질문과 사진 검색</small></div></div>
      <div className="chat-log" ref={logRef}>
        {messages.map((message, index) => <p className={message.role} key={`${message.text}-${index}`}>{message.text}</p>)}
        {pending && <p className="answer is-pending">답변을 준비하고 있어요…</p>}
      </div>
      <div className="chat-compose">
        <input aria-label="질문" value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => event.key === "Enter" && send()} placeholder="궁금한 성분이나 제품을 물어보세요" />
        <button onClick={send} disabled={pending}>{pending ? "전송 중" : "보내기"}</button>
      </div>
    </section>
  );
}
