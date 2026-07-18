"use client";

import { useEffect, useState } from "react";
import { getDailyGauge, GaugeResponse } from "@/lib/api/zerocheck";

export function useDailyGauge(token: string | null) {
  const [gauge, setGauge] = useState<GaugeResponse | null>(null);

  useEffect(() => {
    if (!token) {
      setGauge(null);
      return;
    }
    let active = true;
    getDailyGauge(token)
      .then((value) => {
        if (active && Number.isFinite(Number(value.cal)) && Number.isFinite(Number(value.sugar))) setGauge(value);
      })
      .catch(() => {
        if (active) setGauge(null);
      });
    return () => {
      active = false;
    };
  }, [token]);

  return gauge;
}
