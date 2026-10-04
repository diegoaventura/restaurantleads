/** Spanish labels and color tokens for statuses, channels and platforms. */

import type {
  DeliveryPlatform,
  FollowUpStatus,
  InteractionChannel,
  InteractionResult,
  LeadStatus,
  SourceType,
} from "../api/types";

export const LEAD_STATUS_INFO: Record<LeadStatus, { label: string; badge: string }> = {
  new: { label: "Nuevo", badge: "bg-sky-100 text-sky-700" },
  qualified: { label: "Cualificado", badge: "bg-cyan-100 text-cyan-700" },
  contacted: { label: "Contactado", badge: "bg-amber-100 text-amber-700" },
  no_response: { label: "Sin respuesta", badge: "bg-stone-100 text-stone-600" },
  follow_up: { label: "Seguimiento", badge: "bg-orange-100 text-orange-700" },
  interested: { label: "Interesado", badge: "bg-violet-100 text-violet-700" },
  meeting: { label: "Reunión", badge: "bg-fuchsia-100 text-fuchsia-700" },
  customer: { label: "Cliente", badge: "bg-emerald-100 text-emerald-700" },
  not_interested: { label: "No interesado", badge: "bg-stone-100 text-stone-500" },
  wrong_number: { label: "Nº equivocado", badge: "bg-rose-100 text-rose-700" },
  out_of_area: { label: "Fuera de zona", badge: "bg-stone-100 text-stone-500" },
  duplicate: { label: "Duplicado", badge: "bg-stone-100 text-stone-500" },
};

export const INTERACTION_RESULT_LABELS: Record<InteractionResult, string> = {
  no_answer: "Sin respuesta",
  busy: "Ocupado",
  callback_requested: "Pide que llamemos",
  interested: "Interesado",
  not_interested: "No interesado",
  meeting_scheduled: "Reunión concertada",
  wrong_number: "Nº equivocado",
  out_of_area: "Fuera de zona",
  duplicate_reported: "Reporta duplicado",
};

export const CHANNEL_LABELS: Record<InteractionChannel, string> = {
  call: "Llamada",
  whatsapp: "WhatsApp",
  email: "Email",
  meeting: "Reunión",
  other: "Otro",
};

export const PLATFORM_LABELS: Record<DeliveryPlatform, string> = {
  glovo: "Glovo",
  uber_eats: "Uber Eats",
  just_eat: "Just Eat",
  deliveroo: "Deliveroo",
  own_delivery: "Envío propio",
  other: "Otra",
};

export const SOURCE_LABELS: Record<SourceType, string> = {
  manual_import: "CSV manual",
  osm: "OpenStreetMap",
  google_places: "Google Places",
  manual: "Alta manual",
};

export const FOLLOW_UP_STATUS_LABELS: Record<FollowUpStatus, string> = {
  pending: "Pendiente",
  completed: "Completado",
  postponed: "Aplazado",
  cancelled: "Cancelado",
};
