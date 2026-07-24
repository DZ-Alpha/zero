import { AdminShell } from "@/components/AdminShell";

export default function ResearchPage() {
  return (
    <AdminShell>
      <div className="admin-page-head">
        <h2>사용자 데이터 분석</h2>
        <p>AD-0109(검색기록 분석) · AD-0110(비교기록 분석) · AD-0111(AI 관심 패턴) · AD-0112(AI 선택 경향)</p>
      </div>
      <div className="admin-placeholder">
        기능명세서 API-Spec 시트 기준으로 이 4개 기능이 호출할 백엔드 엔드포인트(<code>/admin/research?menu=...</code>)가
        아직 어떤 서비스에도 구현돼 있지 않아요(admin-service엔 <code>/admin/me</code> 하나뿐이고, b-gateway에도
        관련 라우팅이 없어요). 백엔드가 준비되면 이 화면에 연결할게요.
      </div>
    </AdminShell>
  );
}
