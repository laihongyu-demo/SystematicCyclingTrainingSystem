import { useEffect, useState } from "react";
import { ApiError, api } from "../api";
import type {
  HealthDailyResponse,
  HealthDay,
  MorningRhrItem,
  MorningRhrResponse,
} from "../types";
import { fmtDate, fmtNum, useFetch } from "../hooks";

const RANGES = [
  { days: 7, label: "7天" },
  { days: 14, label: "14天" },
  { days: 30, label: "1月" },
  { days: 90, label: "3月" },
];

type Tab = "rhr" | "health";

function localTodayStr(): string {
  const p = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  return p;
}

// ---------- Δ 昨日差值徽章 ----------
function DeltaBadge({ delta, fallback }: { delta: number | null; fallback: string }) {
  if (delta === null) return <span className="tag">{fallback}</span>;
  const cls = delta > 0 ? "delta-up" : delta < 0 ? "delta-down" : "delta-flat";
  const sign = delta > 0 ? "+" : "";
  return <span className={`tag ${cls}`}>{sign}{fmtNum(delta, 1)}</span>;
}

// ---------- 双线迷你趋势 ----------
const TW = 620;
const TH = 170;
const TM = { t: 16, r: 12, b: 24, l: 42 };

function segments(pts: { x: number; y: number | null }[]): string[] {
  const segs: string[] = [];
  let cur: { x: number; y: number }[] = [];
  pts.forEach((p) => {
    if (p.y === null) {
      if (cur.length) {
        segs.push("M" + cur.map((q) => `${q.x.toFixed(1)} ${q.y.toFixed(1)}`).join(" L"));
        cur = [];
      }
      return;
    }
    cur.push({ x: p.x, y: p.y });
  });
  if (cur.length) segs.push("M" + cur.map((q) => `${q.x.toFixed(1)} ${q.y.toFixed(1)}`).join(" L"));
  return segs;
}

function DualTrend({
  days,
  morning,
}: {
  days: HealthDay[];
  morning: MorningRhrItem[];
}) {
  const morningByDate = new Map(morning.map((m) => [m.date, m.value]));
  const n = days.length;
  if (n === 0) return <div className="empty-hint">窗口内暂无 RHR 数据</div>;
  const plotW = TW - TM.l - TM.r;
  const plotH = TH - TM.t - TM.b;
  const xAt = (i: number) => (n <= 1 ? TM.l + plotW / 2 : TM.l + (i / (n - 1)) * plotW);

  const all = days.flatMap((d) => {
    const a = d.resting_rhr;
    const b = morningByDate.get(d.date) ?? null;
    return [a, b].filter((v): v is number => v !== null);
  });
  const lo = all.length ? Math.min(...all) - 2 : 0;
  const hi = all.length ? Math.max(...all) + 2 : 1;
  const yAt = (v: number) => TM.t + ((hi - v) / (hi - lo || 1)) * plotH;

  const icuPts: { x: number; y: number | null }[] = days.map((d, i) => ({
    x: xAt(i),
    y: d.resting_rhr !== null ? yAt(d.resting_rhr) : null,
  }));
  const momPts: { x: number; y: number | null }[] = days.map((d, i) => {
    const v = morningByDate.get(d.date) ?? null;
    return { x: xAt(i), y: v !== null ? yAt(v) : null };
  });

  const icuSegs = segments(icuPts);
  const momSegs = segments(momPts);

  const last = days[n - 1];
  const lastIcu = last.resting_rhr;
  const lastMom = morningByDate.get(last.date) ?? null;

  return (
    <div>
      <svg viewBox={`0 0 ${TW} ${TH}`} width="100%" style={{ display: "block" }}>
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={TM.l}
            x2={TW - TM.r}
            y1={TM.t + plotH * f}
            y2={TM.t + plotH * f}
            stroke="var(--grid)"
            strokeDasharray="3 3"
          />
        ))}
        {icuSegs.map((d, i) => (
          <path key={`i${i}`} d={d} fill="none" stroke="var(--ctl)" strokeWidth="1.8" />
        ))}
        {momSegs.map((d, i) => (
          <path key={`m${i}`} d={d} fill="none" stroke="var(--ok)" strokeWidth="1.8" />
        ))}
        {/* 晨起记录点 */}
        {momPts.map((p, i) =>
          p.y === null ? null : <circle key={`p${i}`} cx={p.x} cy={p.y} r="2.6" fill="var(--ok)" />,
        )}
        {lastIcu !== null ? (
          <circle cx={xAt(n - 1)} cy={yAt(lastIcu)} r="3" fill="var(--ctl)" />
        ) : null}
        {lastMom !== null ? (
          <circle cx={xAt(n - 1)} cy={yAt(lastMom)} r="3" fill="var(--ok)" />
        ) : null}
        <text x={TM.l} y={TH - 7} fontSize="10" fill="var(--text-dim)">
          {fmtDate(days[0]?.date, true)}
        </text>
        <text x={TW - TM.r} y={TH - 7} textAnchor="end" fontSize="10" fill="var(--text-dim)">
          {fmtDate(days[n - 1]?.date, true)}
        </text>
      </svg>
      <div className="legend-chips" style={{ marginTop: 6 }}>
        <span className="chip"><span className="dot" style={{ background: "var(--ctl)" }} />icu 原始 RHR（全天监控）</span>
        <span className="chip"><span className="dot" style={{ background: "var(--ok)" }} />晨起 RHR（手动）</span>
      </div>
    </div>
  );
}

// ---------- 今日录入表单 ----------
function EntryForm({ onSaved }: { onSaved: () => void }) {
  const today = localTodayStr();
  const [date, setDate] = useState(today);
  const [value, setValue] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok?: string; err?: string } | null>(null);

  async function submit(overwrite: boolean): Promise<void> {
    setBusy(true);
    setMsg(null);
    try {
      await api.morningRhrSave({ date, value: Number(value), note: note || null, overwrite });
      setMsg({ ok: overwrite ? "已覆盖保存" : "已保存" });
      setValue("");
      setNote("");
      onSaved();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && !overwrite) {
        const go = window.confirm(`${date} 已有晨起 RHR 记录，确认覆盖为新值 ${value} 吗？`);
        if (go) return submit(true);
        setMsg({ err: "已取消，未覆盖原记录" });
      } else {
        setMsg({ err: e instanceof Error ? e.message : String(e) });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="entry-form">
      <div className="entry-title">今日晨起 RHR 录入</div>
      <div className="entry-row">
        <label>日期
          <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>心率(bpm)
          <input
            type="number"
            inputMode="numeric"
            min={20}
            max={250}
            step={1}
            placeholder="如 45"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>
        <label>备注
          <input
            value={note}
            placeholder="睡眠/状态等（可选）"
            maxLength={200}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <button
          className="btn primary"
          disabled={busy || !date || value === ""}
          onClick={() => submit(false)}
        >
          {busy ? "保存中…" : "保存"}
        </button>
      </div>
      <div className="hint">测量规范：清晨清醒后持续测量 5 分钟，取最终稳定值；仅保存在本地，不回写 intervals.icu。</div>
      {msg?.ok ? <div className="sync-msg ok-msg">{msg.ok}</div> : null}
      {msg?.err ? <div className="sync-msg err-msg">{msg.err}</div> : null}
    </div>
  );
}

function LatestRow({
  title,
  date,
  value,
  delta,
  unit,
}: {
  title: string;
  date: string | null;
  value: number | null;
  delta: number | null;
  unit: string;
}) {
  return (
    <div className="stat-card">
      <div className="label">{title}</div>
      <div className="value" style={{ fontSize: 22 }}>
        {value !== null ? fmtNum(value, 0) : "—"}
        <span className="unit">{unit}</span>
      </div>
      <div className="foot" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {date ? <span>{fmtDate(date, true)}</span> : null}
        <DeltaBadge delta={delta} fallback="无昨日数据" />
      </div>
    </div>
  );
}

// ---------- 健康看板表格 ----------
function HealthTable({ days, covered }: { days: HealthDay[]; covered: number }) {
  if (days.length === 0) return <div className="empty-hint">窗口内暂无健康数据（需先完成同步）</div>;
  const reversed = [...days].reverse();
  return (
    <div>
      <div className="meta-line" style={{ marginBottom: 8 }}>
        <span className="dot ok" /> 窗口覆盖 <b>{covered}</b>/{days.length} 天；缺口日（—）表示未同步或无设备数据。
      </div>
      <div className="table-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th className="align-l">日期</th>
              <th>RHR(bpm)</th>
              <th>HRV(ms)</th>
              <th>HRV_SDNN</th>
              <th>体重(kg)</th>
              <th>体脂(%)</th>
            </tr>
          </thead>
          <tbody>
            {reversed.map((d) => (
              <tr key={d.date} style={d.has_data ? undefined : { opacity: 0.55 }}>
                <td className="align-l">{fmtDate(d.date, true)}</td>
                <td className="num">{d.resting_rhr !== null ? fmtNum(d.resting_rhr, 1) : "—"}</td>
                <td className="num">{d.hrv !== null ? fmtNum(d.hrv, 1) : "—"}</td>
                <td className="num">{d.hrv_sdnn !== null ? fmtNum(d.hrv_sdnn, 1) : "—"}</td>
                <td className="num">{d.weight !== null ? fmtNum(d.weight, 1) : "—"}</td>
                <td className="num">{d.fat_percent !== null ? fmtNum(d.fat_percent, 1) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------- 健康中心主组件 ----------
export default function HealthCenter({ reloadKey = 0 }: { reloadKey?: number }) {
  const [tab, setTab] = useState<Tab>("rhr");
  const [days, setDays] = useState(14);

  const health = useFetch<HealthDailyResponse>(
    () => `/api/wellness/daily?days=${days}`,
    [days],
  );
  const morning = useFetch<MorningRhrResponse>(
    () => `/api/wellness/morning-rhr?days=${days}`,
    [days],
  );

  const healthDays = health.data?.days ?? [];
  const morningItems = morning.data?.items ?? [];
  // 外部（如全量同步完成）刷新请求
  useEffect(() => {
    if (reloadKey > 0) {
      health.reload();
      morning.reload();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);
  const reloadAll = () => {
    health.reload();
    morning.reload();
  };

  // 计算 icu RHR 最新有值日与昨日差
  let icuLatest: { date: string; value: number; delta: number | null } | null = null;
  for (let i = healthDays.length - 1; i >= 0; i--) {
    const d = healthDays[i];
    if (d.resting_rhr !== null) {
      const prev = healthDays[i - 1];
      icuLatest = {
        date: d.date,
        value: d.resting_rhr,
        delta: prev && prev.resting_rhr !== null ? d.resting_rhr - prev.resting_rhr : null,
      };
      break;
    }
  }
  const morningLatest = morningItems.length ? morningItems[morningItems.length - 1] : null;

  const err = health.error ?? morning.error ?? null;

  return (
    <div className="panel">
      <div className="section-head" style={{ flexWrap: "wrap", gap: 10 }}>
        <h2>健康中心</h2>
        <div className="seg" style={{ marginLeft: "auto" }}>
          <button className={tab === "rhr" ? "active" : ""} onClick={() => setTab("rhr")}>RHR 对比</button>
          <button className={tab === "health" ? "active" : ""} onClick={() => setTab("health")}>健康看板</button>
        </div>
        <div className="seg">
          {RANGES.map((r) => (
            <button key={r.days} className={days === r.days ? "active" : ""} onClick={() => setDays(r.days)}>
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {err ? <div className="banner-error">{err}</div> : null}

      {tab === "rhr" ? (
        <div className="rhr-layout">
          <div className="cards" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
            <LatestRow
              title="icu 原始 RHR"
              date={icuLatest?.date ?? null}
              value={icuLatest?.value ?? null}
              delta={icuLatest?.delta ?? null}
              unit="bpm"
            />
            <LatestRow
              title="晨起 RHR"
              date={morningLatest?.date ?? null}
              value={morningLatest?.value ?? null}
              delta={morningLatest?.delta ?? null}
              unit="bpm"
            />
          </div>
          {morningLatest ? (
            <div className="hint" style={{ margin: "6px 0 8px" }}>
              最近一次晨起记录 {morningLatest.date}：{fmtNum(morningLatest.value, 0)} bpm
              {morningLatest.note ? ` · ${morningLatest.note}` : ""}
            </div>
          ) : null}

          {health.loading || morning.loading ? (
            <div className="state-box">加载 RHR 数据…</div>
          ) : (
            <>
              <div className="legend-chips" style={{ margin: "8px 0 4px" }}>近 {days} 天 RHR 走势（双线对比）</div>
              <DualTrend days={healthDays} morning={morningItems} />
            </>
          )}

          <EntryForm onSaved={reloadAll} />
        </div>
      ) : (
        health.loading ? (
          <div className="state-box">加载健康看板…</div>
        ) : (
          <HealthTable days={healthDays} covered={health.data?.covered_days ?? 0} />
        )
      )}
    </div>
  );
}
