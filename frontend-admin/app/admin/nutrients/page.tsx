"use client";

import { FormEvent, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { upsertNutrition } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

const initialForm = { id: "", cal: "", natu: "", dang: "", dan: "", carb: "", fat: "" };

export default function NutrientsPage() {
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  function update<K extends keyof typeof initialForm>(key: K, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.id.trim()) {
      setMessage({ kind: "error", text: "상품 ID는 필수예요." });
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      await upsertNutrition({
        id: form.id.trim(),
        cal: form.cal || undefined,
        natu: form.natu || undefined,
        dang: form.dang || undefined,
        dan: form.dan || undefined,
        carb: form.carb || undefined,
        fat: form.fat || undefined,
      });
      setMessage({ kind: "success", text: "영양성분을 저장했어요." });
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "처리하지 못했어요." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AdminShell>
      <div className="admin-page-head">
        <h2>영양성분 등록</h2>
        <p>AD-0103 — 값을 비워두면 해당 항목은 그대로 유지돼요 (부분 수정).</p>
      </div>
      <form className="admin-card" onSubmit={handleSubmit}>
        <div className="admin-form-grid">
          <label>
            상품 ID <small>(필수)</small>
            <input value={form.id} onChange={(event) => update("id", event.target.value)} placeholder="상품 UUID" required />
          </label>
          <div className="admin-form-row">
            <label>
              칼로리(kcal)
              <input value={form.cal} onChange={(event) => update("cal", event.target.value)} inputMode="decimal" />
            </label>
            <label>
              당류(g)
              <input value={form.dang} onChange={(event) => update("dang", event.target.value)} inputMode="decimal" />
            </label>
          </div>
          <div className="admin-form-row">
            <label>
              나트륨(mg)
              <input value={form.natu} onChange={(event) => update("natu", event.target.value)} inputMode="decimal" />
            </label>
            <label>
              단백질(g)
              <input value={form.dan} onChange={(event) => update("dan", event.target.value)} inputMode="decimal" />
            </label>
          </div>
          <div className="admin-form-row">
            <label>
              탄수화물(g)
              <input value={form.carb} onChange={(event) => update("carb", event.target.value)} inputMode="decimal" />
            </label>
            <label>
              지방(g)
              <input value={form.fat} onChange={(event) => update("fat", event.target.value)} inputMode="decimal" />
            </label>
          </div>
          <button type="submit" className="admin-submit" disabled={submitting}>
            {submitting ? "저장하고 있어요…" : "저장하기"}
          </button>
        </div>
        {message && <p className={`admin-message ${message.kind === "success" ? "is-success" : "is-error"}`}>{message.text}</p>}
      </form>
    </AdminShell>
  );
}
