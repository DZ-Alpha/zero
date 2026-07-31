"use client";

import { useEffect, useRef, useState } from "react";

// 팝업이 열릴 때는 CSS 애니메이션이 있는데, 닫힐 때는 부모가 즉시 언마운트해서
// exit 애니메이션이 재생될 시간이 없었다(2026-07-31 요청). onClose를 그
// 자리에서 바로 부르는 대신, 먼저 closing 상태를 켜서 CSS가 exit 애니메이션
// class를 타게 하고, 그 애니메이션 길이만큼 뒤에야 실제 onClose(부모의
// 언마운트)를 부른다. 접근성 설정(요약 애니메이션 끔)이면 지연 없이 바로 닫는다.
export function useDelayedClose(onClose: () => void, durationMs = 200) {
  const [closing, setClosing] = useState(false);

  function requestClose() {
    if (closing) return;
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      onClose();
      return;
    }
    setClosing(true);
    window.setTimeout(onClose, durationMs);
  }

  return { closing, requestClose };
}

// 위 useDelayedClose는 "열림 여부만" 다루는 팝업(별도 컴포넌트로 분리된 것)에
// 맞다. 반면 부모 컴포넌트 하나가 "무엇을 보여줄지"까지 같은 state 값으로
// 결정하는 인라인 팝업(예: editor: "profile"|"goals"|null)은, 그 값이
// null이 되는 순간 내용까지 같이 사라져서 exit 애니메이션이 재생될 콘텐츠가
// 없어진다. 이 훅은 마지막으로 렌더링된 값을 붙들고 있다가, exit 애니메이션이
// 끝난 뒤에야 진짜로 null로 넘어간다 - 부모는 원래 state 대신 rendered를 써서
// 내용을 그리면 된다.
export function useExitPresence<T>(value: T | null, durationMs = 200) {
  const [rendered, setRendered] = useState<T | null>(value);
  const [closing, setClosing] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (value !== null) {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      setClosing(false);
      setRendered(value);
      return;
    }
    if (rendered === null) return;
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setRendered(null);
      return;
    }
    setClosing(true);
    timerRef.current = window.setTimeout(() => {
      setRendered(null);
      setClosing(false);
    }, durationMs);
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return { rendered, closing };
}
