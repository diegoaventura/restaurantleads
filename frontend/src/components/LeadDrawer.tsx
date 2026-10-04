import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getRestaurant, patchLead } from "../api/endpoints";
import type {
  InteractionChannel,
  LeadPriority,
  LeadStatus,
  RestaurantDetail,
} from "../api/types";
import RegisterInteractionModal from "./RegisterInteractionModal";
import ScoreCell from "./ScoreCell";
import StatusBadge from "./StatusBadge";
import {
  CHANNEL_LABELS,
  FOLLOW_UP_STATUS_LABELS,
  INTERACTION_RESULT_LABELS,
  LEAD_STATUS_INFO,
  PLATFORM_LABELS,
  SOURCE_LABELS,
} from "../lib/labels";
import { formatDateTime } from "../lib/format";

const SECTION_TITLE = "text-xs font-semibold uppercase tracking-wide text-slate-400";

export default function LeadDrawer({
  restaurantId,
  onClose,
  onChanged,
}: {
  restaurantId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [detail, setDetail] = useState<RestaurantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalChannel, setModalChannel] = useState<InteractionChannel>("call");
  const [copied, setCopied] = useState<string | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setDetail(await getRestaurant(restaurantId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cargando ficha");
    }
  }, [restaurantId]);

  useEffect(() => {
    void load();
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

  async function changeStatus(status: LeadStatus) {
    if (!detail) return;
    setStatusBusy(true);
    try {
      await patchLead(detail.id, { status });
      await load();
      onChanged();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cambiando estado");
      await load(); // revert the select
    } finally {
      setStatusBusy(false);
    }
  }

  async function changePriority(priority: LeadPriority) {
    if (!detail) return;
    setStatusBusy(true);
    try {
      await patchLead(detail.id, { priority });
      await load();
      onChanged();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cambiando prioridad");
    } finally {
      setStatusBusy(false);
    }
  }

  const pendingFollowUps = (detail?.follow_ups ?? []).filter(
    (f) => f.status === "pending",
  );
  const phone = detail?.phone ?? null;
  const whatsappHref = phone ? `https://wa.me/${phone.replace(/[^0-9]/g, "")}` : null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-slate-900/30 backdrop-blur-[1px]"
        onClick={onClose}
      />

      {/* Panel */}
      <aside className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto bg-white shadow-2xl">
        {error && (
          <div className="sticky top-0 z-10 bg-rose-50 px-6 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        {!detail ? (
          <div className="p-10 text-center text-slate-400">Cargando ficha…</div>
        ) : (
          <>
            {/* Header */}
            <div className="sticky top-0 z-10 border-b border-slate-200 bg-white px-6 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">{detail.name}</h2>
                  <div className="mt-1 flex items-center gap-2">
                    {detail.lead && <StatusBadge status={detail.lead.status} />}
                    <span className="text-xs text-slate-400">
                      creado {formatDateTime(detail.created_at)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="rounded-lg border border-slate-200 px-2.5 py-1 text-sm text-slate-500 transition hover:bg-slate-50"
                >
                  ✕
                </button>
              </div>

              {/* Action bar: the 5-click flow's contact step.
                  Call/WhatsApp open the register modal with the channel
                  preset (the action is logged, plan FASE 11). */}
              <div className="mt-4 flex flex-wrap gap-2">
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
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  ✓ Registrar contacto
                </button>
                {phone && (
                  <button
                    onClick={() => void copy(phone, "teléfono")}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50"
                  >
                    {copied === "teléfono" ? "¡Copiado!" : "⧉ Teléfono"}
                  </button>
                )}
                <Link
                  to={`/restaurants/${restaurantId}`}
                  onClick={onClose}
                  className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-700 transition hover:bg-teal-100"
                >
                  Ver ficha completa →
                </Link>
              </div>
            </div>

            <div className="flex flex-col gap-6 px-6 py-6">
              {/* Datos */}
              <section className="flex flex-col gap-2">
                <h3 className={SECTION_TITLE}>Datos</h3>
                <dl className="grid grid-cols-[7rem_1fr] gap-y-2 text-sm">
                  <dt className="text-slate-500">Teléfono</dt>
                  <dd className="tabular-nums text-slate-900">
                    {phone ?? "—"}
                    {detail.phone_source && (
                      <span className="ml-2 text-xs text-slate-400">
                        ({SOURCE_LABELS[detail.phone_source]})
                      </span>
                    )}
                  </dd>
                  <dt className="text-slate-500">Email</dt>
                  <dd className="text-slate-900">{detail.email ?? "—"}</dd>
                  <dt className="text-slate-500">Web</dt>
                  <dd className="truncate text-slate-900">
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
                  </dd>
                  <dt className="text-slate-500">Dirección</dt>
                  <dd className="text-slate-900">
                    {[detail.address, detail.postal_code, detail.city]
                      .filter(Boolean)
                      .join(", ") || "—"}
                  </dd>
                  <dt className="text-slate-500">Categoría</dt>
                  <dd className="text-slate-900">{detail.category ?? "—"}</dd>
                  <dt className="text-slate-500">Fuentes</dt>
                  <dd className="text-slate-900">
                    {[...new Set(detail.sources.map((s) => SOURCE_LABELS[s.source]))].join(
                      ", ",
                    )}
                  </dd>
                </dl>
              </section>

              {/* Delivery */}
              <section className="flex flex-col gap-2">
                <h3 className={SECTION_TITLE}>Delivery</h3>
                {detail.delivery_presence.length === 0 ? (
                  <p className="text-sm text-slate-400">Sin plataformas detectadas.</p>
                ) : (
                  <ul className="flex flex-col gap-1.5 text-sm">
                    {detail.delivery_presence.map((d) => (
                      <li key={d.id} className="flex items-center gap-2">
                        <span className="rounded-md bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700">
                          {PLATFORM_LABELS[d.platform]}
                        </span>
                        <span className="text-xs text-slate-500">
                          {d.detection_method === "website_link"
                            ? "detectado en su web"
                            : "confirmado manualmente"}{" "}
                          · {formatDateTime(d.last_detected_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Score */}
              {detail.lead && (
                <section className="flex flex-col gap-2">
                  <h3 className={SECTION_TITLE}>Score</h3>
                  <ScoreCell score={detail.lead.score} />
                  {detail.lead.score_reasons && detail.lead.score_reasons.length > 0 && (
                    <ul className="mt-1 flex flex-col gap-1 text-sm">
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

              {/* CRM */}
              {detail.lead && (
                <section className="flex flex-col gap-2">
                  <h3 className={SECTION_TITLE}>CRM</h3>
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <label className="flex items-center gap-2">
                      <span className="text-slate-500">Estado</span>
                      <select
                        value={detail.lead.status}
                        disabled={statusBusy}
                        onChange={(e) =>
                          void changeStatus(e.target.value as LeadStatus)
                        }
                        className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      >
                        {Object.entries(LEAD_STATUS_INFO).map(([value, info]) => (
                          <option key={value} value={value}>
                            {info.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex items-center gap-2">
                      <span className="text-slate-500">Prioridad</span>
                      <select
                        value={detail.lead.priority}
                        disabled={statusBusy}
                        onChange={(e) =>
                          void changePriority(e.target.value as LeadPriority)
                        }
                        className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                      >
                        <option value="low">Baja</option>
                        <option value="medium">Media</option>
                        <option value="high">Alta</option>
                      </select>
                    </label>
                  </div>
                </section>
              )}

              {/* Próximos seguimientos */}
              <section className="flex flex-col gap-2">
                <h3 className={SECTION_TITLE}>Próximos seguimientos</h3>
                {pendingFollowUps.length === 0 ? (
                  <p className="text-sm text-slate-400">Ninguno programado.</p>
                ) : (
                  <ul className="flex flex-col gap-2 text-sm">
                    {pendingFollowUps.map((f) => (
                      <li
                        key={f.id}
                        className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2"
                      >
                        <div className="font-medium text-slate-900">
                          {formatDateTime(f.scheduled_at)} ·{" "}
                          {CHANNEL_LABELS[f.channel]}
                        </div>
                        {f.notes && (
                          <div className="mt-0.5 text-xs text-slate-500">{f.notes}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Historial */}
              <section className="flex flex-col gap-2">
                <h3 className={SECTION_TITLE}>Historial ({detail.interactions.length})</h3>
                {detail.interactions.length === 0 ? (
                  <p className="text-sm text-slate-400">Sin contactos registrados.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {detail.interactions.map((i) => (
                      <li
                        key={i.id}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium text-slate-900">
                            {INTERACTION_RESULT_LABELS[i.result]}
                          </span>
                          <span className="text-xs text-slate-400">
                            {formatDateTime(i.occurred_at)} ·{" "}
                            {CHANNEL_LABELS[i.channel]}
                          </span>
                        </div>
                        {i.notes && (
                          <div className="mt-0.5 text-xs text-slate-500">{i.notes}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Follow-ups completados (audit) */}
              {detail.follow_ups.filter((f) => f.status !== "pending").length > 0 && (
                <section className="flex flex-col gap-2">
                  <h3 className={SECTION_TITLE}>Seguimientos anteriores</h3>
                  <ul className="flex flex-col gap-1 text-xs text-slate-500">
                    {detail.follow_ups
                      .filter((f) => f.status !== "pending")
                      .map((f) => (
                        <li key={f.id}>
                          {formatDateTime(f.scheduled_at)} · {CHANNEL_LABELS[f.channel]} ·{" "}
                          {FOLLOW_UP_STATUS_LABELS[f.status]}
                        </li>
                      ))}
                  </ul>
                </section>
              )}
            </div>
          </>
        )}
      </aside>

      {detail && modalOpen && (
        <RegisterInteractionModal
          restaurantId={detail.id}
          restaurantName={detail.name}
          defaultChannel={modalChannel}
          onDone={() => {
            setModalOpen(false);
            void load();
            onChanged();
          }}
          onCancel={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}
