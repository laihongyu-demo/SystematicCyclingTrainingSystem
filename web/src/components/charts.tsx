import { useMemo, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import type { FitnessPoint, WeekRow } from "../types";
import { fmtDate, fmtNum } from "../hooks";

// ---------- 通用：按数据计算 y 坐标与刻度 ----------
function domainOf(values: number[]): { lo: number; hi: number } {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 10;
  return { lo: min - span * 0.08, hi: max + span * 0.08 };
}

function yTicks(lo: number, hi: number, count = 4): number[] {
  const step = (hi - lo) / count;
  const ticks: number[] = [];
  for (let i = 0; i <= count; i++) ticks.push(lo + step * i);
  return ticks;
}

interface XY {
  x: number;
  y: number;
}

/** 允许中间空值，把连续非空段拆成多条路径。 */
function lineSegments(
  values: (number | null)[],
  xAt: (i: number) => number,
  yAt: (v: number) => number,
): string[] {
  const segs: string[] = [];
  let cur: XY[] = [];
  values.forEach((v, i) => {
    if (v === null) {
      if (cur.length) {
        segs.push("M" + cur.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L"));
        cur = [];
      }
      return;
    }
    cur.push({ x: xAt(i), y: yAt(v) });
  });
  if (cur.length) {
    segs.push("M" + cur.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L"));
  }
  return segs;
}

const W = 760;
const H = 300;
const M = { t: 18, r: 14, b: 26, l: 50 };

export function LegendChips() {
  const chips: Array<{ key: string; cls: string; label: string }> = [
    { key: "ctl", cls: "ctl", label: "CTL 体能" },
    { key: "atl", cls: "atl", label: "ATL 疲劳" },
    { key: "tsb", cls: "tsb", label: "TSB 状态" },
  ];
  return (
    <div className="legend-chips">
      {chips.map((c) => (
        <span className="chip" key={c.key}>
          <span className={`dot ${c.cls}`} />
          {c.label}
        </span>
      ))}
    </div>
  );
}

// ---------- 体能曲线（CTL/ATL/TSB） ----------
export function FitnessChart({ series }: { series: FitnessPoint[] }) {
  const [hover, setHover] = useState<number | null>(null);

  const n = series.length;
  const plotW = W - M.l - M.r;
  const plotH = H - M.t - M.b;
  const xAt = (i: number) => (n <= 1 ? M.l + plotW / 2 : M.l + (i / (n - 1)) * plotW);
  const yAt = (v: number, lo: number, hi: number) =>
    M.t + ((hi - v) / (hi - lo)) * plotH;

  const model = useMemo(() => {
    const vals = series
      .flatMap((p) => [p.ctl, p.atl, p.tsb])
      .filter((v): v is number => v !== null);
    if (vals.length === 0 || n === 0) return null;
    const { lo, hi } = domainOf(vals);
    const ctl = lineSegments(series.map((p) => p.ctl), xAt, (v) => yAt(v, lo, hi));
    const atl = lineSegments(series.map((p) => p.atl), xAt, (v) => yAt(v, lo, hi));
    const tsb = lineSegments(series.map((p) => p.tsb), xAt, (v) => yAt(v, lo, hi));
    return { lo, hi, ctl, atl, tsb, ticks: yTicks(lo, hi) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, n]);

  if (!model) return <div className="empty-hint">窗口内暂无体能数据（需先完成同步）</div>;

  const onMove = (e: ReactMouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const sx = ((e.clientX - rect.left) / rect.width) * W;
    let idx = Math.round(((sx - M.l) / plotW) * (n - 1));
    idx = Math.max(0, Math.min(n - 1, idx));
    setHover(idx);
  };

  const h = hover !== null ? series[hover] : null;
  const tipLeft = hover !== null ? Math.min(88, Math.max(8, (hover / Math.max(1, n - 1)) * 90)) : 0;

  return (
    <div className="chart-box" style={{ position: "relative" }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ display: "block" }}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {model.ticks.map((t, i) => (
          <g key={i}>
            <line
              x1={M.l}
              x2={W - M.r}
              y1={yAt(t, model.lo, model.hi)}
              y2={yAt(t, model.lo, model.hi)}
              stroke="var(--grid)"
              strokeDasharray="3 3"
            />
            <text
              x={M.l - 6}
              y={yAt(t, model.lo, model.hi) + 3.5}
              textAnchor="end"
              fontSize="10"
              fill="var(--text-dim)"
              fontFamily="var(--mono)"
            >
              {fmtNum(t, 0)}
            </text>
          </g>
        ))}
        {model.ctl.map((d, i) => (
          <path key={`c${i}`} d={d} fill="none" stroke="var(--ctl)" strokeWidth="2" />
        ))}
        {model.atl.map((d, i) => (
          <path key={`a${i}`} d={d} fill="none" stroke="var(--atl)" strokeWidth="2" />
        ))}
        {model.tsb.map((d, i) => (
          <path key={`t${i}`} d={d} fill="none" stroke="var(--tsb)" strokeWidth="2" strokeDasharray="5 3" />
        ))}
        {/* 末尾最新值标记 */}
        {hover !== null ? (
          <line
            x1={xAt(hover)}
            x2={xAt(hover)}
            y1={M.t}
            y2={H - M.b}
            stroke="var(--text-dim)"
            strokeWidth="1"
            opacity="0.35"
          />
        ) : null}
        {["ctl", "atl", "tsb"].map((key) => {
          const last = series[n - 1];
          const v = last?.[key as "ctl" | "atl" | "tsb"];
          if (v === null || v === undefined) return null;
          return (
            <circle
              key={key}
              cx={xAt(n - 1)}
              cy={yAt(v, model.lo, model.hi)}
              r="3"
              fill={`var(--${key})`}
            />
          );
        })}
        <text x={M.l} y={H - 6} fontSize="10" fill="var(--text-dim)">
          起 {series[0]?.date ?? ""}
        </text>
        <text x={W - M.r} y={H - 6} textAnchor="end" fontSize="10" fill="var(--text-dim)">
          最新 {series[n - 1]?.date ?? ""}
        </text>
      </svg>
      {h && hover !== null ? (
        <div className="chart-tip" style={{ left: `${tipLeft}%`, top: 0 }}>
          <div style={{ fontWeight: 600, marginBottom: 3 }}>{h.date}</div>
          <div className="row">
            <span className="k">CTL</span>
            <span>{fmtNum(h.ctl, 1)}</span>
            <span className="k">ATL</span>
            <span>{fmtNum(h.atl, 1)}</span>
            <span className="k">TSB</span>
            <span>{fmtNum(h.tsb, 1)}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// ---------- 周负荷柱状 ----------
const BW = 380;
const BH = 210;
const BM = { t: 22, r: 8, b: 32, l: 44 };

export function WeeklyBars({ weeks }: { weeks: WeekRow[] }) {
  if (weeks.length === 0) return <div className="empty-hint">窗口内暂无周负荷数据</div>;
  const plotW = BW - BM.l - BM.r;
  const plotH = BH - BM.t - BM.b;
  const maxLoad = Math.max(...weeks.map((w) => w.load), 1);
  const step = plotW / weeks.length;
  const barW = Math.max(6, step * 0.62);
  const yAt = (v: number) => BM.t + plotH - (v / maxLoad) * plotH;

  return (
    <svg viewBox={`0 0 ${BW} ${BH}`} width="100%" style={{ display: "block" }}>
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line
            x1={BM.l}
            x2={BW - BM.r}
            y1={BM.t + plotH * f}
            y2={BM.t + plotH * f}
            stroke="var(--grid)"
            strokeDasharray="3 3"
          />
          <text
            x={BM.l - 6}
            y={BM.t + plotH * f + 3}
            textAnchor="end"
            fontSize="10"
            fill="var(--text-dim)"
            fontFamily="var(--mono)"
          >
            {f === 0 ? fmtNum(maxLoad, 0) : f === 1 ? "0" : fmtNum(maxLoad / 2, 0)}
          </text>
        </g>
      ))}
      {weeks.map((w, i) => {
        const x = BM.l + i * step + (step - barW) / 2;
        const y = yAt(w.load);
        return (
          <g key={w.week_start}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={Math.max(0, BM.t + plotH - y)}
              rx={2}
              fill="var(--accent)"
              opacity={w.load > 0 ? 0.9 : 0.15}
            >
              <title>{`${w.week_start} 起 · 负荷 ${w.load} · ${w.activities} 次 · ${w.distance_km}km`}</title>
            </rect>
            {i % 2 === 0 || i === weeks.length - 1 ? (
              <text
                x={x + barW / 2}
                y={BH - 10}
                textAnchor="middle"
                fontSize="9"
                fill="var(--text-dim)"
              >
                {fmtDate(w.week_start)}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
