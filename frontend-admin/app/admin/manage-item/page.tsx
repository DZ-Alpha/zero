"use client";

import { FormEvent, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { upsertProduct } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

const initialForm = {
  id: "",
  name: "",
  brand: "",
  categoryTagId: "",
  imageUrl: "",
  calories: "",
  sugars: "",
  purchaseUrl: "",
  ingredientText: "",
};

export default function ManageItemPage() {
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  function update<K extends keyof typeof initialForm>(key: K, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setMessage(null);
    const isUpdate = form.id.trim().length > 0;
    try {
      // AD-0101(등록)은 category_tag_id/image_url/calories/sugars가 필수,
      // AD-0102(수정, id 입력됨)는 전부 선택 — 백엔드(product-service/admin.py)
      // 검증과 동일한 규칙.
      if (!isUpdate && (!form.categoryTagId || !form.imageUrl || !form.calories || !form.sugars)) {
        setMessage({ kind: "error", text: "신규 등록은 카테고리 태그ID·이미지URL·칼로리·당류가 필수예요." });
        setSubmitting(false);
        return;
      }
      const result = await upsertProduct({
        id: isUpdate ? form.id.trim() : undefined,
        name: form.name || undefined,
        brand: form.brand || undefined,
        categoryTagId: form.categoryTagId || undefined,
        imageUrl: form.imageUrl || undefined,
        purchaseUrl: form.purchaseUrl || undefined,
        ingredientText: form.ingredientText || undefined,
        calories: form.calories || undefined,
        sugars: form.sugars || undefined,
      });
      setMessage({ kind: "success", text: isUpdate ? "상품 정보를 수정했어요." : `상품을 등록했어요. (id: ${result.id})` });
      if (!isUpdate) setForm(initialForm);
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "처리하지 못했어요." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AdminShell>
      <div className="admin-page-head">
        <h2>상품 등록 · 수정</h2>
        <p>AD-0101(등록) / AD-0102(수정) — product-service의 실제 관리자 API에 연결돼 있어요.</p>
      </div>
      <form className="admin-card" onSubmit={handleSubmit}>
        <div className="admin-form-grid">
          <label>
            상품 ID <small>(수정할 때만 입력 — 비우면 신규 등록)</small>
            <input value={form.id} onChange={(event) => update("id", event.target.value)} placeholder="기존 상품 UUID" />
          </label>
          <div className="admin-form-row">
            <label>
              상품명
              <input value={form.name} onChange={(event) => update("name", event.target.value)} />
            </label>
            <label>
              브랜드
              <input value={form.brand} onChange={(event) => update("brand", event.target.value)} />
            </label>
          </div>
          <label>
            카테고리 태그 ID <small>(신규 등록 시 필수 — 태그 관리 화면은 아직 준비 중이라 UUID를 직접 입력해요)</small>
            <input value={form.categoryTagId} onChange={(event) => update("categoryTagId", event.target.value)} placeholder="카테고리 태그 UUID" />
          </label>
          <label>
            이미지 URL <small>(신규 등록 시 필수)</small>
            <input value={form.imageUrl} onChange={(event) => update("imageUrl", event.target.value)} placeholder="https://..." />
          </label>
          <div className="admin-form-row">
            <label>
              칼로리(kcal) <small>(신규 등록 시 필수)</small>
              <input value={form.calories} onChange={(event) => update("calories", event.target.value)} inputMode="decimal" />
            </label>
            <label>
              당류(g) <small>(신규 등록 시 필수)</small>
              <input value={form.sugars} onChange={(event) => update("sugars", event.target.value)} inputMode="decimal" />
            </label>
          </div>
          <label>
            판매 링크
            <input value={form.purchaseUrl} onChange={(event) => update("purchaseUrl", event.target.value)} placeholder="https://..." />
          </label>
          <label>
            원재료 텍스트
            <textarea value={form.ingredientText} onChange={(event) => update("ingredientText", event.target.value)} rows={3} />
          </label>
          <button type="submit" className="admin-submit" disabled={submitting}>
            {submitting ? "처리하고 있어요…" : form.id.trim() ? "수정하기" : "등록하기"}
          </button>
        </div>
        {message && <p className={`admin-message ${message.kind === "success" ? "is-success" : "is-error"}`}>{message.text}</p>}
      </form>
    </AdminShell>
  );
}
