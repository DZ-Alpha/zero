"use client";

import { useEffect, useState } from "react";
import { DIET_SAVE_EVENT } from "@/hooks/useDietRecords";
import { getDailyGauge, GaugeResponse } from "@/lib/api/zerocheck";

export function useDailyGauge(token: string | null) {
  const [gauge, setGauge] = useState<GaugeResponse | null>(null);

  useEffect(() => {
    if (!token) {
      setGauge(null);
      return;
    }
    let active = true;

    function fetchGauge() {
      getDailyGauge(token as string)
        .then((value) => {
          if (active && Number.isFinite(Number(value.cal)) && Number.isFinite(Number(value.sugar))) setGauge(value);
        })
        .catch(() => {
          if (active) setGauge(null);
        });
    }

    fetchGauge();
    // 식단 기록 저장/삭제가 서버에 반영되면 useDietRecords가 이 이벤트를 쏜다 —
    // 이게 없으면 오늘 당류/칼로리 게이지가 마운트 시점 값에 고정돼서, 새로고침
    // 하거나 페이지를 나갔다 들어와야만(리마운트) 바뀌는 문제가 있었다.
    window.addEventListener(DIET_SAVE_EVENT, fetchGauge);
    return () => {
      active = false;
      window.removeEventListener(DIET_SAVE_EVENT, fetchGauge);
    };
  }, [token]);

  return gauge;
}
