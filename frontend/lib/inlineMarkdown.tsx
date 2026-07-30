import { Fragment } from "react";

// 백엔드 AI 응답의 **볼드** 마커만 <strong>으로 인라인 변환한다. 챗봇 답변과
// 상품 상세 AI 요약(한줄요약/감미료 설명)이 공유 - AI 텍스트엔 헤딩/리스트가
// 오지 않도록 서버가 프롬프트+후처리로 걷어내므로(product-service의
// sanitize_summary, ai의 strip_chat_markdown) react-markdown 같은 의존성
// 없이 이 정도로 충분하다.
export function renderInlineMarkdown(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}
