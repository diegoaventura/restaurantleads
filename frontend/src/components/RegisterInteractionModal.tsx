import { useState, type FormEvent } from "react";
import { createFollowUp, createInteraction } from "../api/endpoints";
import type { InteractionChannel, InteractionResult } from "../api/types";
import {
  CHANNEL_LABELS,
  INTERACTION_RESULT_LABELS,
} from "../lib/labels";

const SELECT_CLASS =
  "w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-700 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100";

function defaultFollowUpDate(): string {
  // datetime-local value 3 days ahead (mirrors the backend's auto +3).
  const date = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T09:00`;
}

export default function RegisterInteractionModal({
  restaurantId,
  restaurantName,
  defaultChannel = "call",
  onDone,
  onCancel,
}: {
  restaurantId: string;
  restaurantName: string;
  defaultChannel?: InteractionChannel;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [channel, setChannel] = useState<InteractionChannel>(defaultChannel);
  const [result, setResult] = useState<InteractionResult>("no_answer");
  const [notes, setNotes] = useState("");
  const [scheduleFollowUp, setScheduleFollowUp] = useState(false);
  const [followUpDate, setFollowUpDate] = useState(defaultFollowUpDate());
  const [followUpChannel, setFollowUpChannel] = useState<InteractionChannel>("call");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createInteraction(restaurantId, {
        channel,
        result,
        notes: notes || undefined,
      });

      let followUpNote = "";
      if (scheduleFollowUp) {
        const followUp = await createFollowUp(restaurantId, {
          scheduled_at: new Date(followUpDate).toISOString(),
          channel: followUpChannel,
        });
        followUpNote = ` · seguimiento programado (${new Date(
          followUp.scheduled_at,
        ).toLocaleString("es-ES")})`;
      } else if (created.follow_up_created) {
        followUpNote = ` · seguimiento automático: ${new Date(
          created.follow_up_created.scheduled_at,
        ).toLocaleString("es-ES")}`;
      }
      setSuccess(
        `Registrado: ${INTERACTION_RESULT_LABELS[result]} · estado → ${created.lead_status}${followUpNote}`,
      );
      setBusy(false);
      // Brief success display, then close so the flow stays fast.
      setTimeout(onDone, 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error registrando contacto");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40" onClick={busy ? undefined : onCancel} />
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl"
      >
        <h2 className="text-lg font-semibold text-slate-900">Registrar contacto</h2>
        <p className="mb-4 mt-0.5 text-sm text-slate-500">{restaurantName}</p>

        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-700">Canal</span>
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value as InteractionChannel)}
                className={SELECT_CLASS}
              >
                {Object.entries(CHANNEL_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-700">Resultado</span>
              <select
                value={result}
                onChange={(e) => setResult(e.target.value as InteractionResult)}
                className={SELECT_CLASS}
              >
                {Object.entries(INTERACTION_RESULT_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">Notas</span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Qué ha pasado, con quién has hablado…"
              className="w-full rounded-lg border border-slate-300 px-2.5 py-2 text-sm outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
            />
          </label>

          <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={scheduleFollowUp}
              onChange={(e) => setScheduleFollowUp(e.target.checked)}
              className="h-4 w-4 accent-teal-600"
            />
            <span className="font-medium text-slate-700">
              Programar seguimiento
              <span className="ml-1 font-normal text-slate-400">
                (no_answer ya lo crea automático)
              </span>
            </span>
          </label>

          {scheduleFollowUp && (
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-slate-700">Fecha y hora</span>
                <input
                  type="datetime-local"
                  required
                  value={followUpDate}
                  onChange={(e) => setFollowUpDate(e.target.value)}
                  className={SELECT_CLASS}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-slate-700">Canal</span>
                <select
                  value={followUpChannel}
                  onChange={(e) =>
                    setFollowUpChannel(e.target.value as InteractionChannel)
                  }
                  className={SELECT_CLASS}
                >
                  {Object.entries(CHANNEL_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              {success}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={busy}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-60"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60"
            >
              {busy ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
