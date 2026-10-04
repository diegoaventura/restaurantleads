import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  actOnFollowUp,
  exportRestaurant,
  getRestaurant,
  listAssignableUsers,
  patchLead,
  type AssignableUser,
} from "../api/endpoints";
import type {
  InteractionChannel,
  LeadPriority,
  LeadStatus,
  RestaurantDetail,
} from "../api/types";
import RegisterInteractionModal from "../components/RegisterInteractionModal";
import ScoreCell from "../components/ScoreCell";
import StatusBadge from "../components/StatusBadge";
import { formatDate, formatDateTime } from "../lib/format";
import {
  CHANNEL_LABELS,
  FOLLOW_UP_STATUS_LABELS,
  INTERACTION_RESULT_LABELS,
  LEAD_STATUS_INFO,
  PLATFORM_LABELS,
  SOURCE_LABELS,
} from "../lib/labels";

const SECTION_TITLE =
  "text-xs font-semibold uppercase tracking-wide text-slate-400";
const CARD = "rounded-xl border border-slate-200 bg-white p-5 shadow-sm";
const SELECT_CLASS =
  "rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100";
const QUICK_ACTION =
  "rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50";

export default function RestaurantPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<RestaurantDetail | null>(null);
  const [assignable, setAssignable] = useState<AssignableUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalChannel, setModalChannel] = useState<InteractionChannel>("call");

  const load = useCallback(async () => {
    try {
      setDetail(await getRestaurant(id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cargando ficha");
    }
  }, [id]);

  useEffect(() => {
    void load();
    listAssignableUsers()
      .then(setAssignable)
      .catch(() => setAssignable([]));
  }, [load]);

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setError("No se pudo copiar");
    }
  }

  async function updateLead(
    body: { status?: LeadStatus; priority?: LeadPriority; assigned_to?: string },
  ) {
    if (!detail) return;
    setBusy(true);
    try {
      await patchLead(detail.id, body);
      await load();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error actualizando lead");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function downloadExport() {
    if (!detail) return;
    try {
      const data = await exportRestaurant(detail.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `restaurante-${detail.name.toLowerCase().replace(/\s+/g, "-")}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error exportando");
    }
  }

  async function act(
    followUpId: string,
    action: "complete" | "postpone" | "cancel",
    daysAhead?: number,
  ) {
    setBusy(true);
    try {
      await actOnFollowUp(followUpId, {
        action,
        ...(action === "postpone" && daysAhead !== undefined
          ? {
              new_date: new Date(Date.now() + daysAhead * 86400000).toISOString(),
              notes: `Aplazado ${daysAhead} día(s) desde la ficha`,
            }
          : {}),
      });
      await load();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error actualizando seguimiento");
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return (
      <div className="flex flex-col gap-4">
        {error ? (
          <div className="rounded-xl bg-rose-50 p-4 text-sm text-rose-700">
            {error} ·{" "}
            <button onClick={() => void load()} className="font-semibold underline">
              reintentar
            </button>
          </div>
        ) : (
          <div className="p-10 text-center text-slate-400">Cargando ficha…</div>
        )}
      </div>
    );
  }

  const phone = detail.phone;
  const whatsappHref = phone ? `https://wa.me/${phone.replace(/[^0-9]/g, "")}` : null;
  const pendingFollowUps = detail.follow_ups.filter((f) => f.status === "pending");
  const pastFollowUps = detail.follow_ups.filter((f) => f.status !== "pending");

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="text-sm font-medium text-slate-500 transition hover:text-slate-900"
          >
            ← Volver
          </button>
          <div className="flex gap-2">
            <button
              onClick={() => void downloadExport()}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 shadow-sm transition hover:bg-slate-50"
              title="Export JSON completo (portabilidad RGPD)"
            >
              ⭳ Export JSON
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-slate-900">{detail.name}</h1>
              {detail.lead && <StatusBadge status={detail.lead.status} />}
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {[detail.category, detail.city, `creado ${formatDate(detail.created_at)}`]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>

          {/* Quick actions (each contact action surfaces registration) */}
          <div className="flex flex-wrap gap-2">
            {phone && (
              <a
                href={`tel:${phone}`}
                onClick={() => {
                  setModalChannel("call");
                  setModalOpen(true);
                }}
                className="rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-teal-700"
              >
                📞 Llamar
              </a>
            )}
            {whatsappHref && (
              <a
                href={whatsappHref}
                target="_blank"
                rel="noreferrer"
                onClick={() => {
                  setModalChannel("whatsapp");
                  setModalOpen(true);
                }}
                className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700"
              >
                💬 WhatsApp
              </a>
            )}
            <button
              onClick={() => {
                setModalChannel("call");
                setModalOpen(true);
              }}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
            >
              ✓ Registrar contacto
            </button>
            {phone && (
              <button
                onClick={() => void copy(phone, "teléfono")}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 shadow-sm transition hover:bg-slate-50"
              >
                {copied === "teléfono" ? "¡Copiado!" : "⧉ Teléfono"}
              </button>
            )}
            {detail.email && (
              <button
                onClick={() => void copy(detail.email!, "email")}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 shadow-sm transition hover:bg-slate-50"
              >
                {copied === "email" ? "¡Copiado!" : "⧉ Email"}
              </button>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column (2/3): data */}
        <div className="flex flex-col gap-6 lg:col-span-2">
          {/* Datos */}
          <section className={CARD}>
            <h2 className={SECTION_TITLE}>Datos</h2>
            <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-y-2.5 text-sm">
              <dt className="text-slate-500">Teléfono</dt>
              <dd className="tabular-nums text-slate-900">
                {phone ?? "—"}
                {detail.phone_source && (
                  <span className="ml-2 text-xs text-slate-400">
                    {SOURCE_LABELS[detail.phone_source]}
                    {detail.phone_verified_at &&
                      ` · verificado ${formatDate(detail.phone_verified_at)}`}
                  </span>
                )}
              </dd>
              <dt className="text-slate-500">Email</dt>
              <dd className="text-slate-900">
                {detail.email ?? "—"}
                {detail.email_source && (
                  <span className="ml-2 text-xs text-slate-400">
                    {SOURCE_LABELS[detail.email_source]}
                  </span>
                )}
              </dd>
              <dt className="text-slate-500">Web</dt>
              <dd className="text-slate-900">
                {detail.website ? (
                  <a
                    href={`https://${detail.website}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-teal-600 hover:underline"
                  >
                    {detail.website}
                  </a>
                ) : (
                  "—"
                )}
                {detail.website_source && (
                  <span className="ml-2 text-xs text-slate-400">
                    {SOURCE_LABELS[detail.website_source]}
                  </span>
                )}
              </dd>
              <dt className="text-slate-500">Dirección</dt>
              <dd className="text-slate-900">
                {[detail.address, detail.postal_code, detail.city].filter(Boolean).join(", ") ||
                  "—"}
              </dd>
              <dt className="text-slate-500">Categoría</dt>
              <dd className="text-slate-900">{detail.category ?? "—"}</dd>
              <dt className="text-slate-500">Fuentes</dt>
              <dd className="flex flex-wrap gap-1.5">
                {detail.sources.map((s) => (
                  <span
                    key={s.id}
                    className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                    title={`${SOURCE_LABELS[s.source]}${s.external_id ? ` (${s.external_id})` : ""} · visto ${formatDate(s.last_seen_at)}`}
                  >
                    {SOURCE_LABELS[s.source]}
                  </span>
                ))}
              </dd>
            </dl>
          </section>

          {/* Delivery */}
          <section className={CARD}>
            <h2 className={SECTION_TITLE}>Presencia en delivery</h2>
            {detail.delivery_presence.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">
                Sin plataformas detectadas.
              </p>
            ) : (
              <ul className="mt-3 flex flex-col gap-2 text-sm">
                {detail.delivery_presence.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700">
                      {PLATFORM_LABELS[d.platform]}
                    </span>
                    {d.url && (
                      <a
                        href={d.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-teal-600 hover:underline"
                      >
                        enlace
                      </a>
                    )}
                    <span className="text-xs text-slate-500">
                      {d.detection_method === "website_link"
                        ? "detectado en su web"
                        : d.detection_method === "api"
                          ? "vía API"
                          : "confirmado manualmente"}{" "}
                      · {formatDate(d.last_detected_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Score */}
          {detail.lead && (
            <section className={CARD}>
              <div className="flex items-center justify-between">
                <h2 className={SECTION_TITLE}>Score</h2>
                <span className="text-xs text-slate-400">
                  recalculado {formatDate(detail.lead.scored_at)}
                </span>
              </div>
              <div className="mt-3">
                <ScoreCell score={detail.lead.score} />
              </div>
              {detail.lead.score_reasons && detail.lead.score_reasons.length > 0 && (
                <ul className="mt-3 flex flex-col gap-1 text-sm">
                  {detail.lead.score_reasons.map((reason) => (
                    <li key={reason.factor} className="flex items-center gap-2">
                      <span
                        className={`w-10 text-right font-semibold tabular-nums ${
                          reason.points >= 0 ? "text-emerald-600" : "text-rose-600"
                        }`}
                      >
                        {reason.points > 0 ? `+${reason.points}` : reason.points}
                      </span>
                      <span className="text-slate-600">{reason.label}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Historial */}
          <section className={CARD}>
            <h2 className={SECTION_TITLE}>Historial ({detail.interactions.length})</h2>
            {detail.interactions.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">Sin contactos registrados.</p>
            ) : (
              <ol className="mt-3 flex flex-col gap-3">
                {detail.interactions.map((i) => (
                  <li
                    key={i.id}
                    className="border-l-2 border-slate-200 pl-4 text-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-slate-900">
                        {INTERACTION_RESULT_LABELS[i.result]}
                      </span>
                      <span className="text-xs text-slate-400">
                        {formatDateTime(i.occurred_at)} · {CHANNEL_LABELS[i.channel]}
                      </span>
                    </div>
                    {i.notes && (
                      <div className="mt-0.5 text-xs text-slate-500">{i.notes}</div>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        {/* Right column (1/3): CRM + seguimientos */}
        <div className="flex flex-col gap-6">
          {detail.lead && (
            <section className={CARD}>
              <h2 className={SECTION_TITLE}>CRM</h2>
              <div className="mt-3 flex flex-col gap-3 text-sm">
                <label className="flex items-center justify-between gap-2">
                  <span className="text-slate-500">Estado</span>
                  <select
                    value={detail.lead.status}
                    disabled={busy}
                    onChange={(e) =>
                      void updateLead({ status: e.target.value as LeadStatus })
                    }
                    className={SELECT_CLASS}
                  >
                    {Object.entries(LEAD_STATUS_INFO).map(([value, info]) => (
                      <option key={value} value={value}>
                        {info.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center justify-between gap-2">
                  <span className="text-slate-500">Prioridad</span>
                  <select
                    value={detail.lead.priority}
                    disabled={busy}
                    onChange={(e) =>
                      void updateLead({ priority: e.target.value as LeadPriority })
                    }
                    className={SELECT_CLASS}
                  >
                    <option value="low">Baja</option>
                    <option value="medium">Media</option>
                    <option value="high">Alta</option>
                  </select>
                </label>
                <label className="flex items-center justify-between gap-2">
                  <span className="text-slate-500">Responsable</span>
                  <select
                    value={detail.lead.assigned_to ?? ""}
                    disabled={busy}
                    onChange={(e) => void updateLead({ assigned_to: e.target.value })}
                    className={SELECT_CLASS}
                  >
                    <option value="">Sin asignar</option>
                    {assignable.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>
          )}

          {/* Seguimientos */}
          <section className={CARD}>
            <h2 className={SECTION_TITLE}>Próximos seguimientos</h2>
            {pendingFollowUps.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">Ninguno programado.</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-3">
                {pendingFollowUps.map((f) => (
                  <li
                    key={f.id}
                    className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm"
                  >
                    <div className="font-medium text-slate-900">
                      {formatDateTime(f.scheduled_at)} · {CHANNEL_LABELS[f.channel]}
                    </div>
                    {f.notes && (
                      <div className="mt-0.5 text-xs text-slate-500">{f.notes}</div>
                    )}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <button
                        onClick={() => void act(f.id, "complete")}
                        disabled={busy}
                        className="rounded-md bg-teal-600 px-2 py-1 text-xs font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60"
                      >
                        ✓ Completar
                      </button>
                      <button
                        onClick={() => void act(f.id, "postpone", 1)}
                        disabled={busy}
                        className={QUICK_ACTION}
                      >
                        +1 día
                      </button>
                      <button
                        onClick={() => void act(f.id, "postpone", 3)}
                        disabled={busy}
                        className={QUICK_ACTION}
                      >
                        +3 días
                      </button>
                      <button
                        onClick={() => void act(f.id, "cancel")}
                        disabled={busy}
                        className={QUICK_ACTION}
                      >
                        Cancelar
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {pastFollowUps.length > 0 && (
              <>
                <h3 className={`${SECTION_TITLE} mt-5`}>Anteriores</h3>
                <ul className="mt-2 flex flex-col gap-1 text-xs text-slate-500">
                  {pastFollowUps.map((f) => (
                    <li key={f.id}>
                      {formatDateTime(f.scheduled_at)} · {CHANNEL_LABELS[f.channel]} ·{" "}
                      {FOLLOW_UP_STATUS_LABELS[f.status]}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>

          {/* Enlaces rápidos */}
          <section className={`${CARD} flex flex-col gap-2 text-sm`}>
            <h2 className={SECTION_TITLE}>Accesos</h2>
            <Link to="/leads" className="text-teal-600 hover:underline">
              → Volver a la tabla de leads
            </Link>
            <Link to="/" className="text-teal-600 hover:underline">
              → Ir al dashboard
            </Link>
          </section>
        </div>
      </div>

      {modalOpen && (
        <RegisterInteractionModal
          restaurantId={detail.id}
          restaurantName={detail.name}
          defaultChannel={modalChannel}
          onDone={() => {
            setModalOpen(false);
            void load();
          }}
          onCancel={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}
