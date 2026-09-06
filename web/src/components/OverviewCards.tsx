import type { ReactNode } from "react";
import type { OverviewResponse } from "../types";
import { fmtNum } from "../hooks";

function StatCard({
  label,
  value,
  cls,
  foot,
}: {
  label: string;
  value: string;
  cls?: string;
  foot?: ReactNode;
}) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className={`value ${cls ?? ""}`}>{value}</div>
      {foot ? <div className="foot">{foot}</div> : null}
    </div>
  );
}

export default function OverviewCards({
  data,
  loading,
  error,
}: {
  data: OverviewResponse | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <div className="state-box">加载概览…</div>;
  if (error || !data) return <div className="state-box error">{error ?? "无概览数据"}</div>;

  const c = data.current;
  const s = data.summary;
  const range = `${data.window.oldest.slice(5)} ~ ${data.window.newest.slice(5)}`;
  const ctl = c?.ctl ?? null;
  const atl = c?.atl ?? null;
  const tsb = c?.tsb ?? null;

  return (
    <div className="cards">
      <StatCard label="CTL 当前体能" value={fmtNum(ctl, 1)} cls="ctl" foot="较前日衰减推演" />
      <StatCard label="ATL 当前疲劳" value={fmtNum(atl, 1)} cls="atl" />
      <StatCard
        label="TSB 状态分"
        value={fmtNum(tsb, 1)}
        cls="tsb"
        foot={tsb !== null ? (tsb >= 0 ? "偏恢复" : "偏疲劳") : undefined}
      />
      <StatCard label="近窗口活动" value={fmtNum(s.activities)} foot={`训练日 ${data.workout_days} 天`} />
      <StatCard label="总距离" value={`${fmtNum(s.distance_km, 1)} km`} />
      <StatCard label="总时长" value={`${fmtNum(s.moving_h, 1)} h`} foot="骑行时间" />
      <StatCard label="总负荷" value={fmtNum(s.load, 0)} foot={range} />
    </div>
  );
}
