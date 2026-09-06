import { useMemo } from "react";
import type { CalendarDay, Window } from "../types";
import { fmtNum } from "../hooks";

interface Cell {
  iso: string | null;
  inWindow: boolean;
  load: number;
  acts: number;
  km: number;
}

interface MonthTile {
  label: string;
  weeks: Cell[][];
}

function parseIso(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function isoOf(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function alphaFor(load: number): number {
  if (load <= 0) return 0;
  if (load < 40) return 0.2;
  if (load < 90) return 0.38;
  if (load < 160) return 0.58;
  if (load < 260) return 0.78;
  return 1;
}

const WEEKS = ["一", "二", "三", "四", "五", "六", "日"];

export default function CalendarHeatmap({
  days,
  window: win,
}: {
  days: CalendarDay[];
  window: Window;
}) {
  const tiles = useMemo<MonthTile[]>(() => {
    const byDate = new Map(days.map((d) => [d.date, d]));
    const start = parseIso(win.oldest);
    const end = parseIso(win.newest);
    const startTs = start.getTime();
    const endTs = end.getTime();
    const out: MonthTile[] = [];

    const cursor = new Date(start.getFullYear(), start.getMonth(), 1);
    while (
      cursor.getFullYear() < end.getFullYear() ||
      (cursor.getFullYear() === end.getFullYear() && cursor.getMonth() <= end.getMonth())
    ) {
      const y = cursor.getFullYear();
      const m = cursor.getMonth();
      const daysInMonth = new Date(y, m + 1, 0).getDate();
      const firstDow = cursor.getDay();
      const lead = (firstDow + 6) % 7; // 周一为 0
      const totalCells = lead + daysInMonth;
      const weekCount = Math.ceil(totalCells / 7);
      const firstDate = new Date(y, m, 1 - lead);
      const weeks: Cell[][] = [];
      for (let w = 0; w < weekCount; w++) {
        const row: Cell[] = [];
        for (let i = 0; i < 7; i++) {
          const date = new Date(firstDate);
          date.setDate(firstDate.getDate() + w * 7 + i);
          const ts = date.getTime();
          const inMonth = date.getMonth() === m;
          const inWindow = inMonth && ts >= startTs && ts <= endTs;
          if (!inMonth) {
            row.push({ iso: null, inWindow: false, load: 0, acts: 0, km: 0 });
            continue;
          }
          const iso = isoOf(date);
          const day = byDate.get(iso);
          row.push({
            iso,
            inWindow,
            load: day?.load ?? 0,
            acts: day?.activities ?? 0,
            km: day?.distance_km ?? 0,
          });
        }
        weeks.push(row);
      }
      out.push({ label: `${y}-${String(m + 1).padStart(2, "0")}`, weeks });
      cursor.setMonth(cursor.getMonth() + 1);
    }
    return out;
  }, [days, win]);

  if (days.length === 0) return <div className="empty-hint">窗口内暂无训练记录（需先完成同步）</div>;

  const renderCell = (cell: Cell, key: string) => {
    if (!cell.iso) return <span key={key} />;
    const bg =
      !cell.inWindow || cell.load <= 0
        ? undefined
        : `rgba(var(--heat-rgb), ${alphaFor(cell.load)})`;
    const title =
      cell.inWindow && cell.acts > 0
        ? `${cell.iso} · 负荷 ${fmtNum(cell.load, 0)} · ${cell.acts} 次 · ${fmtNum(cell.km, 1)} km`
        : cell.iso;
    return (
      <span
        key={key}
        className="heat-cell"
        style={bg ? { backgroundColor: bg } : undefined}
        title={title}
      />
    );
  };

  return (
    <div>
      <div className="heat-months">
        {tiles.map((tile) => (
          <div className="heat-month" key={tile.label}>
            <div className="heat-month-title">{tile.label}</div>
            <div className="heat-weekdays">
              {WEEKS.map((wd) => (
                <span key={wd}>{wd}</span>
              ))}
            </div>
            {tile.weeks.map((row, ri) => (
              <div className="heat-row" key={ri}>
                {row.map((cell, ci) => renderCell(cell, `${tile.label}-${ri}-${ci}`))}
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="heat-legend">
        <span>少</span>
        {[0.2, 0.38, 0.58, 0.78, 1].map((a) => (
          <span key={a} className="swatch" style={{ backgroundColor: `rgba(var(--heat-rgb), ${a})` }} />
        ))}
        <span>多</span>
        <span style={{ marginLeft: 14 }}>色阶按日负荷（训练负荷）着色，悬停查看详情</span>
      </div>
    </div>
  );
}
