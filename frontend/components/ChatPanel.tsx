"use client";

import { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { getChatHistory, sendChatbotMessage, streamChatbotMessage } from "@/lib/api/zerocheck";
import { convertHeicToJpeg, isHeicFile } from "@/lib/heic";
import { renderInlineMarkdown } from "@/lib/inlineMarkdown";

type ChatMessage = { role: "question" | "answer"; text: string; imageUrl?: string };

const fallbackAnswer = "질문을 기준으로 성분표를 쉽게 풀어드릴게요. 지금은 상담 기능을 준비하고 있어서, 제품 검색과 레시피에서 성분 정보를 먼저 확인해 주세요.";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

// 상담이 실제로 처리할 수 있는 갈래(일반 지식 / 상품 비교 / 레시피 대체)를
// 하나씩 고른 예시다. 빈 화면을 채우는 게 아니라 "여기서 뭘 물어볼 수 있는지"를
// 보여주는 게 목적이라, 답변이 잘 나오는 질문으로만 둔다.
const SUGGESTED_QUESTIONS = [
  "하루 당류 권장량이 얼마나 돼요?",
  "제로 콜라가 다이어트에 도움이 되나요?",
  "떡볶이 대신 먹을 저당 메뉴 알려줘",
];

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [attaching, setAttaching] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, pending]);

  // conversation-memory-frontend-spec.md §2 — 채팅창을 열 때 서버가 기억하는
  // 이전 대화(로그인=계정 기준, 비로그인=session_id 기준)를 복원한다. 대화가
  // 없으면(신규/24시간 만료) 빈 로그를 그대로 두고 "무엇을 도와드릴까요?" 안내만 보여준다.
  useEffect(() => {
    let active = true;
    getChatHistory(getAccessToken()).then(({ messages: history }) => {
      if (!active || history.length === 0) return;
      setMessages(history.map((item) => ({
        role: item.role === "user" ? "question" : "answer",
        text: item.text,
        ...(item.imageUrl ? { imageUrl: item.imageUrl } : {}),
      })));
    }).catch(() => {
      // 히스토리 복원 실패 — 빈 로그(안내 문구)를 그대로 둔다.
    });
    return () => {
      active = false;
    };
  }, []);

  function handleAttachClick() {
    fileInputRef.current?.click();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    // 한글 IME 조합 중에 누른 Enter는 "전송"이 아니라 "조합 확정"이다.
    // 이걸 구분하지 않고 send()를 부르면, 입력값을 비운 직후에 브라우저가
    // 조합 중이던 글자를 확정하면서 입력창에 도로 넣는다 — "안녕"을 보내면
    // 다음 입력창에 "녕"이 남아 있던 게 이거였다(2026-08-13 제보).
    // isComposing은 조합이 끝나는 Enter에서 true, 그 다음 Enter에서 false다.
    if (event.nativeEvent.isComposing) return;
    send();
  }

  async function handleFileSelected(event: ChangeEvent<HTMLInputElement>) {
    const rawFile = event.target.files?.[0];
    event.target.value = "";
    if (!rawFile) return;
    if (!rawFile.type.startsWith("image/") && !isHeicFile(rawFile)) return;

    setAttaching(true);
    try {
      // 아이폰 카메라 기본 포맷(HEIC) — 챗봇도 식단 사진 등록과 동일하게
      // 선택 즉시 JPEG로 변환한다. 용량 체크는 변환 후 실제로 전송될 파일
      // 기준으로 해야 한다 - HEIC은 JPEG보다 압축률이 좋아서 원본 기준으로만
      // 재면 변환 후 용량이 늘어 제한을 넘어설 수 있다.
      const file = isHeicFile(rawFile) ? await convertHeicToJpeg(rawFile) : rawFile;
      if (file.size > MAX_IMAGE_BYTES) return;
      const dataUrl = await readFileAsDataUrl(file);
      setAttachedImage(dataUrl);
    } catch {
      // 변환/읽기 실패 — 기존과 동일하게 조용히 무시(별도 에러 UI 없음)
    } finally {
      setAttaching(false);
    }
  }

  async function send(preset?: string) {
    const question = (preset ?? value).trim();
    const image = attachedImage;
    if ((!question && !image) || pending) return;
    setValue("");
    setAttachedImage(null);
    setMessages((items) => [...items, { role: "question", text: question, ...(image ? { imageUrl: image } : {}) }]);
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
      // 첫 delta가 도착하면(=답변이 실제로 시작되면) 그 즉시 "답변을 준비하고
      // 있어요" 로딩을 끈다. 예전엔 done/error를 받을 때까지 켜져 있어서, 답변이
      // 다 스트리밍된 뒤에도 로딩 문구가 말풍선과 함께 계속 떠 있었다.
      if (isFirstChunk) setPending(false);
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
      }, undefined, image);
    } catch {
      // 스트리밍 자체가 실패 — 아래에서 messageStarted 여부로 폴백 처리
    }

    if (!messageStarted) {
      let answer = fallbackAnswer;
      try {
        const reply = await sendChatbotMessage(question, getAccessToken(), undefined, image);
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
      {/* brand-mark는 `img` 자식에만 스타일이 걸려 있다 — 예전엔 빈 `<i/>`를 넣어서
          31px짜리 투명한 칸만 남고 아이콘이 안 보였다(Shell.tsx와 같은 방식으로 맞춤). */}
      <div className="chat-head"><span className="brand-mark"><img src="/icon.svg" alt="" width={32} height={32} /></span><div><b>당당 상담</b><small>영양·성분 질문과 사진 검색</small></div></div>
      <div className="chat-log" ref={logRef}>
        {messages.length === 0 && !pending && (
          <div className="chat-empty">
            <p className="chat-empty-hint">무엇을 도와드릴까요?</p>
            {/* 상담이 뭘 할 수 있는지 화면에 단서가 없어서 빈 영역만 400px 남아 있었다.
                누르면 바로 질문이 나가고, 동시에 지원하는 기능을 알려주는 역할. */}
            <ul className="chat-suggestions">
              {SUGGESTED_QUESTIONS.map((suggestion) => (
                <li key={suggestion}>
                  <button type="button" onClick={() => send(suggestion)} disabled={pending}>
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {messages.map((message, index) => (
          <p className={message.role} key={`${message.role}-${index}`}>
            {message.imageUrl && (
              <img
                className="chat-log-image"
                src={message.imageUrl}
                alt="첨부한 사진"
                // 사진 원본은 24시간만 보관된다 - 만료 후 imageUrl은 404가 나므로
                // 깨진 이미지 아이콘 대신 조용히 숨긴다.
                onError={(event) => { event.currentTarget.style.display = "none"; }}
              />
            )}
            {message.text && renderInlineMarkdown(message.text)}
          </p>
        ))}
        {pending && <p className="answer is-pending">답변을 준비하고 있어요…</p>}
      </div>
      {attachedImage && (
        <div className="chat-attach-preview">
          <img src={attachedImage} alt="첨부할 사진 미리보기" />
          <span>사진 1장 첨부됨</span>
          <button type="button" className="chat-attach-remove" onClick={() => setAttachedImage(null)}>제거</button>
        </div>
      )}
      <div className="chat-compose">
        <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={handleFileSelected} aria-hidden="true" />
        <button
          type="button"
          className="chat-attach-button"
          onClick={handleAttachClick}
          disabled={attaching}
          aria-label="사진 첨부"
          title="사진 첨부"
        >
          {attaching ? (
            <span className="chat-attach-spinner" aria-hidden="true" />
          ) : (
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 8.5a2 2 0 0 1 2-2h1.6l.9-1.5A2 2 0 0 1 10.23 4h3.54a2 2 0 0 1 1.73 1l.9 1.5H18a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
              <circle cx="12" cy="12.5" r="3.4" stroke="currentColor" strokeWidth="1.8" />
            </svg>
          )}
        </button>
        <input
          aria-label="질문"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="궁금한 성분이나 제품을 물어보세요"
        />
        {/* onClick={send}로 두면 MouseEvent가 preset 인자로 들어간다 — 반드시 감싼다 */}
        <button className="chat-send-button" onClick={() => send()} disabled={pending || (!value.trim() && !attachedImage)}>{pending ? "전송 중" : "보내기"}</button>
      </div>
    </section>
  );
}
