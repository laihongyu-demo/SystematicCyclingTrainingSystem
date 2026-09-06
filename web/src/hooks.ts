import { useCallback, useEffect, useRef, useState } from "react";

/** 通用数据加载 hook：URL 由 builder 依据 deps 动态构造。 */
export function useFetch<T>(buildUrl: () => string, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    const my = ++seq.current;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(buildUrl(), { headers: { Accept: "application/json" } })
      .then(async (res) => {
        if (!res.ok) {
          let detail = `HTTP ${res.status} ${res.statusText}`;
          try {
            const body = (await res.json()) as { detail?: unknown };
            if (body.detail !== undefined) detail = String(body.detail);
          } catch {
            /* noop */
          }
          throw new Error(detail);
        }
        return (await res.json()) as T;
      })
      .then((d) => {
        if (!cancelled && my === seq.current) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled && my === seq.current) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload };
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** 'YYYY-MM-DD' / 'YYYY-MM-DDTHH:MM' 统一取 'MM-DD' 显示。 */
export function fmtDate(dateStr: string | null | undefined, withYear = false): string {
  if (!dateStr) return "—";
  const d = dateStr.slice(0, 10).split("-");
  if (d.length !== 3) return dateStr;
  return withYear ? `${d[0]}-${d[1]}-${d[2]}` : `${d[1]}-${d[2]}`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function fmtDuration(min: number | null | undefined): string {
  if (min === null || min === undefined) return "—";
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return h > 0 ? `${h}h${String(m).padStart(2, "0")}m` : `${m}m`;
}
