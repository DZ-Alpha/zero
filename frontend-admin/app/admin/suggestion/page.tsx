import { AdminShell } from "@/components/AdminShell";

export default function SuggestionPage() {
  return (
    <AdminShell>
      <div className="admin-page-head">
        <h2>개선 제안</h2>
        <p>AD-0113 — 소비 패턴 기반 관심기준 수정 제안</p>
      </div>
      <div className="admin-placeholder">
        이 기능도 아직 백엔드(<code>/admin?menu=suggestion</code>)가 구현돼 있지 않아요. AD-0109~0112(사용자 데이터
        분석)의 결과를 바탕으로 만들어질 기능이라, 그쪽이 먼저 준비돼야 해요.
      </div>
    </AdminShell>
  );
}
