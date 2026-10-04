import type { ReactNode } from "react";

const ACCENTS: Record<string, string> = {
  teal: "bg-teal-500",
  sky: "bg-sky-500",
  amber: "bg-amber-500",
  violet: "bg-violet-500",
  emerald: "bg-emerald-500",
  rose: "bg-rose-500",
};

export default function KpiCard({
  label,
  value,
  hint,
  accent = "teal",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  accent?: keyof typeof ACCENTS;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <div className={`h-2.5 w-2.5 rounded-full ${ACCENTS[accent]}`} />
      </div>
      <div className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}
