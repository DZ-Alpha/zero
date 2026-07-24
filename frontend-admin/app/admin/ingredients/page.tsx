"use client";

import { FormEvent, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { createTag, TagInput, upsertIngredients } from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

const initialIngredientForm = { id: "", ingredientText: "", allergenTagIds: "" };
// tagType을 "ALLERGEN" as const로만 두면 useState가 리터럴 "ALLERGEN" 하나로
// 타입을 좁혀버려서, 드롭다운으로 다른 값을 골라도 타입상 항상 "ALLERGEN"인
// 것처럼 보인다 — TagInput["tagType"] 유니온으로 명시해 이 문제를 막는다.
type TagFormState = { tagType: TagInput["tagType"]; tagCode: string; tagName: string; description: string };
const initialTagForm: TagFormState = { tagType: "ALLERGEN", tagCode: "", tagName: "", description: "" };

export default function IngredientsPage() {
  const [form, setForm] = useState(initialIngredientForm);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const [tagForm, setTagForm] = useState(initialTagForm);
  const [tagSubmitting, setTagSubmitting] = useState(false);
  const [tagMessage, setTagMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.id.trim()) {
      setMessage({ kind: "error", text: "상품 ID는 필수예요." });
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      const allergenTagIds = form.allergenTagIds
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      await upsertIngredients({ id: form.id.trim(), ingredientText: form.ingredientText || undefined, allergenTagIds });
      setMessage({ kind: "success", text: "원재료·알레르기 정보를 저장했어요." });
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "처리하지 못했어요." });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTagSubmit(event: FormEvent) {
    event.preventDefault();
    if (!tagForm.tagCode.trim() || !tagForm.tagName.trim()) {
      setTagMessage({ kind: "error", text: "태그 코드·이름은 필수예요." });
      return;
    }
    setTagSubmitting(true);
    setTagMessage(null);
    try {
      const result = await createTag({
        tagType: tagForm.tagType,
        tagCode: tagForm.tagCode.trim(),
        tagName: tagForm.tagName.trim(),
        description: tagForm.description || undefined,
      });
      setTagMessage({ kind: "success", text: `태그를 만들었어요. (id: ${result.id}) 위 알레르기 태그ID 칸에 콤마로 이어붙여 쓰세요.` });
      setTagForm(initialTagForm);
    } catch (err) {
      setTagMessage({ kind: "error", text: err instanceof ApiError ? err.message : "처리하지 못했어요." });
    } finally {
      setTagSubmitting(false);
    }
  }

  return (
    <AdminShell>
      <div className="admin-page-head">
        <h2>원재료 · 알레르기 등록</h2>
        <p>AD-0104 — 알레르기 태그를 고르는 UI는 아직 준비 중이라, 태그 ID를 콤마(,)로 구분해 직접 입력해요.</p>
      </div>

      <form className="admin-card" onSubmit={handleSubmit} style={{ marginBottom: 24 }}>
        <div className="admin-form-grid">
          <label>
            상품 ID <small>(필수)</small>
            <input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value })} placeholder="상품 UUID" required />
          </label>
          <label>
            원재료 텍스트
            <textarea value={form.ingredientText} onChange={(event) => setForm({ ...form, ingredientText: event.target.value })} rows={3} />
          </label>
          <label>
            알레르기 태그 ID 목록 <small>(콤마로 구분)</small>
            <input value={form.allergenTagIds} onChange={(event) => setForm({ ...form, allergenTagIds: event.target.value })} placeholder="uuid1, uuid2" />
          </label>
          <button type="submit" className="admin-submit" disabled={submitting}>
            {submitting ? "저장하고 있어요…" : "저장하기"}
          </button>
        </div>
        {message && <p className={`admin-message ${message.kind === "success" ? "is-success" : "is-error"}`}>{message.text}</p>}
      </form>

      <div className="admin-page-head">
        <h2 style={{ fontSize: 16 }}>새 태그 만들기</h2>
        <p>ingredients-service 태그 마스터에 새 알레르기/감미료/카테고리 태그를 추가해요.</p>
      </div>
      <form className="admin-card" onSubmit={handleTagSubmit}>
        <div className="admin-form-grid">
          <label>
            태그 유형
            <select
              value={tagForm.tagType}
              onChange={(event) => setTagForm({ ...tagForm, tagType: event.target.value as typeof tagForm.tagType })}
            >
              <option value="ALLERGEN">알레르기(ALLERGEN)</option>
              <option value="CATEGORY">카테고리(CATEGORY)</option>
              <option value="SWEETENER">감미료(SWEETENER)</option>
              <option value="HEALTH_LABEL">건강라벨(HEALTH_LABEL)</option>
            </select>
          </label>
          <div className="admin-form-row">
            <label>
              태그 코드
              <input value={tagForm.tagCode} onChange={(event) => setTagForm({ ...tagForm, tagCode: event.target.value })} placeholder="예: PEANUT" />
            </label>
            <label>
              태그 이름
              <input value={tagForm.tagName} onChange={(event) => setTagForm({ ...tagForm, tagName: event.target.value })} placeholder="예: 땅콩" />
            </label>
          </div>
          <label>
            설명
            <textarea value={tagForm.description} onChange={(event) => setTagForm({ ...tagForm, description: event.target.value })} rows={2} />
          </label>
          <button type="submit" className="admin-submit" disabled={tagSubmitting}>
            {tagSubmitting ? "만들고 있어요…" : "태그 만들기"}
          </button>
        </div>
        {tagMessage && <p className={`admin-message ${tagMessage.kind === "success" ? "is-success" : "is-error"}`}>{tagMessage.text}</p>}
      </form>
    </AdminShell>
  );
}
