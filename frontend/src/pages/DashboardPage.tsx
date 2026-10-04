import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { actOnFollowUp, getStats, listFollowUps } from "../api/endpoints";
import type { DashboardStats, FollowUpItem } from "../api/types";
import KpiCard from "../components/KpiCard";
import { CHANNEL_LABELS } from "../lib/labels";
import { formatPercent, formatTime, todayISO } from "../lib/format";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [agenda, setAgenda] = useState<FollowUpItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [statsData, agendaData] = await Promise.all([
        getStats(),
        listFollowUps({ status: "pending", due_on: todayISO() }),
      ]);
      setStats(statsData);
      setAgenda(agendaData.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cargando datos");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function completeFollowUp(id: string) {
    setBusyId(id);
    try {
      await actOnFollowUp(id, { action: "complete" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error completando seguimiento");
    } finally {
      setBusyId(null);
    }
  }

  if (error && !stats) {
    return <div className="rounded-xl bg-rose-50 p-4 text-sm text-rose-700">{error}</div>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Resumen del embudo de captación y la agenda del día.
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          <KpiCard label="Restaurantes" value={stats.restaurants_total} accent="teal" />
          <KpiCard label="Leads nuevos" value={stats.leads_new} accent="sky" />
          <KpiCard
            label="Pendientes de contacto"
            value={stats.pending_contact}
            hint="Nuevos + cualificados"
            accent="amber"
          />
          <KpiCard
            label="Seguimientos hoy"
            value={stats.follow_ups_due_today}
            hint={
              stats.follow_ups_overdue > 0
                ? `${stats.follow_ups_overdue} atrasados`
                : "ninguno atrasado"
            }
            accent="violet"
          />
          <KpiCard label="Interesados" value={stats.interested} accent="emerald" />
          <KpiCard label="Reuniones" value={stats.meetings} accent="rose" />
          <KpiCard label="Clientes" value={stats.customers} accent="teal" />
          <KpiCard
            label="Conversión"
            value={formatPercent(stats.conversion_rate)}
            hint="Clientes / leads totales"
            accent="emerald"
          />
          <KpiCard label="Leads totales" value={stats.leads_total} accent="sky" />
          <KpiCard
            label="Cualificados"
            value={stats.leads_qualified}
            accent="amber"
          />
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Seguimientos de hoy</h2>
            <p className="text-xs text-slate-500">
              Llamadas pendientes programadas para hoy.
            </p>
          </div>
          <Link
            to="/leads"
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
          >
            Ver todos los leads →
          </Link>
        </div>

        {agenda.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-slate-400">
            No hay seguimientos pendientes para hoy. 🎉
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {agenda.map((item) => (
              <li key={item.id} className="flex items-center gap-4 px-5 py-3">
                <span className="w-12 text-sm font-semibold tabular-nums text-slate-700">
                  {formatTime(item.scheduled_at)}
                </span>
                <Link
                  to={`/leads?search=${encodeURIComponent(item.restaurant_name)}`}
                  className="flex-1 truncate text-sm font-medium text-slate-900 hover:text-teal-600"
                >
                  {item.restaurant_name}
                </Link>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
                  {CHANNEL_LABELS[item.channel]}
                </span>
                <button
                  onClick={() => void completeFollowUp(item.id)}
                  disabled={busyId === item.id}
                  className="rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60"
                >
                  {busyId === item.id ? "…" : "Completar"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && (
        <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}
    </div>
  );
}
