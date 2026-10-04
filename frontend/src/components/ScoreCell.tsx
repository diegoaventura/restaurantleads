/** Score cell: colored number + proportional bar (0-100). */

import type { ScoreReason } from "../api/types";

function scoreColor(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-slate-400";
}

function scoreText(score: number): string {
  if (score >= 70) return "text-emerald-600";
  if (score >= 40) return "text-amber-600";
  return "text-slate-500";
}

export default function ScoreCell({
  score,
  reasons,
}: {
  score: number | null;
  reasons?: ScoreReason[] | null;
}) {
  if (score === null) {
    return <span className="text-xs text-slate-400">sin puntuar</span>;
  }
  const title = reasons?.map((r) => `${r.points > 0 ? "+" : ""}${r.points} ${r.label}`).join("\n");
  return (
    <div className="flex items-center gap-2" title={title}>
      <span className={`w-8 text-sm font-semibold tabular-nums ${scoreText(score)}`}>
        {score}
      </span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full ${scoreColor(score)}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
    </div>
  );
}
