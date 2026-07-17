"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { readUserGoals, readUserProfile } from "@/hooks/useUserSettings";

type WelcomeData = {
  name: string;
  calories: number;
  sugar: number;
};

export default function Page() {
  const [data, setData] = useState<WelcomeData>({ name: "회원", calories: 2000, sugar: 50 });

  useEffect(() => {
    try {
      const profile = readUserProfile();
      const goals = readUserGoals();
      setData({
        name: profile.name || "회원",
        calories: goals.calories || 2000,
        sugar: goals.sugar || 50,
      });
    } catch {
      // 기본값으로도 다음 단계에 문제없이 진행할 수 있어요.
    }
  }, []);

  return (
    <AuthFrame asideTitle="오늘부터 가볍게 기록해볼까요?">
      <div className="signup-success">
        <div className="welcome-sugar-character" role="img" aria-label="설탕이가 반갑게 인사해요" />
        <p className="eyebrow">준비 완료</p>
        <h1>{data.name}님, 환영해요!</h1>
        <p>하루 목표를 저장했어요.<br />첫 식사를 기록하면 설탕이가 오늘의 흐름을 알려드릴게요.</p>
        <div className="success-summary">
          <div><span>하루 당류 목표</span><b>{data.sugar}g</b></div>
          <div><span>하루 칼로리 목표</span><b>{data.calories.toLocaleString()}kcal</b></div>
        </div>
        <Link className="auth-primary" href="/">오늘 식단 기록하기</Link>
        <Link className="success-secondary" href="/search">식품부터 둘러보기</Link>
      </div>
    </AuthFrame>
  );
}
