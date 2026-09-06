import type { Capability } from "../types";
import { fmtDate, fmtNum } from "../hooks";

function CapCard({
  label,
  value,
  unit,
  foot,
}: {
  label: string;
  value: string;
  unit?: string;
  foot?: string;
}) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">
        {value}
        {unit ? <span className="unit">{unit}</span> : null}
      </div>
      {foot ? <div className="foot">{foot}</div> : null}
    </div>
  );
}

export default function CapabilityCards({
  data,
  loading,
  error,
}: {
  data: Capability | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <div className="state-box">加载能力指标…</div>;
  if (error || !data) return <div className="state-box error">{error ?? "无能力指标数据"}</div>;

  const weightSrc =
    data.weight_source === "wellness"
      ? `wellness 日值 ${fmtDate(data.weight_date)}`
      : data.weight_source === "athlete_profile"
        ? `档案快照 ${fmtDate(data.weight_date)}`
        : "暂无体重来源";

  return (
    <div className="cards">
      <CapCard
        label="FTP"
        value={data.ftp !== null ? fmtNum(data.ftp, 0) : "—"}
        unit="W"
        foot={data.ftp_synced ? `intervals 档案设置 · ${fmtDate(data.ftp_synced, true)}` : undefined}
      />
      <CapCard
        label="eFTP"
        value={data.eftp !== null ? fmtNum(data.eftp, 0) : "—"}
        unit="W"
        foot={
          data.eftp !== null
            ? `icu 滚动估算 · ${fmtDate(data.eftp_date, true)}`
            : "intervals 未提供官方值"
        }
      />
      <CapCard
        label="w/kg"
        value={data.w_per_kg !== null ? fmtNum(data.w_per_kg, 2) : "—"}
        unit="W/kg"
        foot={
          data.weight_kg !== null
            ? `FTP ÷ ${fmtNum(data.weight_kg, 1)}kg · ${weightSrc}`
            : "缺体重，暂无法计算"
        }
      />
    </div>
  );
}
