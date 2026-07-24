"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { TurnstileWidget } from "@/components/TurnstileWidget";
import { useAdminSession } from "@/hooks/useAdminSession";
import { adminLogin, getAdminMe } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

export default function AdminLoginPage() {
  const router = useRouter();
  const { ready, signedIn, login } = useAdminSession();
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [captcha, setCaptcha] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (ready && signedIn) router.replace("/");
  }, [ready, signedIn, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!captcha) {
      setError("캡차 확인을 완료해 주세요.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await adminLogin(id.trim(), pw, captcha);
      const identity = await getAdminMe(result.token);
      login(result.token, identity);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "로그인하지 못했어요. 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready || signedIn) return <div className="auth-loading">확인하고 있어요…</div>;

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>당당 관리자</h1>
        <p>관리자 계정으로 로그인해 주세요.</p>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <label className="auth-field">
          아이디
          <input value={id} onChange={(event) => setId(event.target.value)} autoComplete="username" required />
        </label>
        <label className="auth-field">
          비밀번호
          <input type="password" value={pw} onChange={(event) => setPw(event.target.value)} autoComplete="current-password" required />
        </label>
        <TurnstileWidget onToken={setCaptcha} />
        <button type="submit" className="auth-submit" disabled={submitting}>
          {submitting ? "로그인하고 있어요…" : "로그인"}
        </button>
      </form>
    </main>
  );
}
