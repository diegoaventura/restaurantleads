import { LEAD_STATUS_INFO } from "../lib/labels";
import type { LeadStatus } from "../api/types";

export default function StatusBadge({ status }: { status: LeadStatus }) {
  const info = LEAD_STATUS_INFO[status];
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${info.badge}`}
    >
      {info.label}
    </span>
  );
}
