import { AdminShell } from "@/components/AdminShell";

export default function DashboardPage() {
  return (
    <AdminShell>
      <div className="admin-page-head">
        <h2>모니터링 대시보드</h2>
        <p>AD-0114 — 이상징후 탐지 대시보드</p>
      </div>
      <div className="admin-placeholder">
        지금은 Grafana(Prometheus/Loki/Tempo 기반)가 이 역할을 대신하고 있어요. 이 화면에서 직접 보여주려면
        Grafana를 iframe으로 임베드하거나, 필요한 지표만 뽑아주는 별도 API가 있어야 해요 — 둘 다 아직 정해진
        게 없어서 스텁으로 남겨둬요.
      </div>
    </AdminShell>
  );
}
