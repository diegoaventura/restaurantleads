/** API types mirroring the backend schemas (docs/API.md). */

export type LeadStatus =
  | "new"
  | "qualified"
  | "contacted"
  | "no_response"
  | "follow_up"
  | "interested"
  | "meeting"
  | "customer"
  | "not_interested"
  | "wrong_number"
  | "out_of_area"
  | "duplicate";

export type LeadPriority = "low" | "medium" | "high";

export type InteractionChannel = "call" | "whatsapp" | "email" | "meeting" | "other";

export type InteractionResult =
  | "no_answer"
  | "busy"
  | "callback_requested"
  | "interested"
  | "not_interested"
  | "meeting_scheduled"
  | "wrong_number"
  | "out_of_area"
  | "duplicate_reported";

export type FollowUpStatus = "pending" | "completed" | "postponed" | "cancelled";

export type DeliveryPlatform =
  | "glovo"
  | "uber_eats"
  | "just_eat"
  | "deliveroo"
  | "own_delivery"
  | "other";

export type SourceType = "manual_import" | "osm" | "google_places" | "manual";

export type UserRole = "admin" | "sales";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ScoreReason {
  factor: string;
  label: string;
  points: number;
}

export interface LeadSummary {
  status: LeadStatus;
  priority: LeadPriority;
  score: number | null;
  score_reasons: ScoreReason[] | null;
  scored_at: string | null;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface RestaurantRow {
  id: string;
  name: string;
  phone: string | null;
  website: string | null;
  city: string | null;
  category: string | null;
  lead: LeadSummary | null;
  delivery_platforms: string[];
  last_interaction_at: string | null;
  next_follow_up_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceRow {
  id: string;
  source: SourceType;
  source_url: string | null;
  external_id: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface DeliveryPresenceRow {
  id: string;
  platform: DeliveryPlatform;
  detected: boolean;
  url: string | null;
  detection_method: string;
  first_detected_at: string;
  last_detected_at: string;
}

export interface InteractionRow {
  id: string;
  channel: InteractionChannel;
  occurred_at: string;
  result: InteractionResult;
  notes: string | null;
  created_by: string | null;
  created_at: string;
}

export interface FollowUpRow {
  id: string;
  scheduled_at: string;
  channel: InteractionChannel;
  status: FollowUpStatus;
  notes: string | null;
  completed_at: string | null;
  created_by: string | null;
  created_at: string;
}

export interface RestaurantDetail extends RestaurantRow {
  email: string | null;
  address: string | null;
  postal_code: string | null;
  phone_source: SourceType | null;
  email_source: SourceType | null;
  website_source: SourceType | null;
  sources: SourceRow[];
  delivery_presence: DeliveryPresenceRow[];
  interactions: InteractionRow[];
  follow_ups: FollowUpRow[];
}

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InteractionCreated {
  interaction: InteractionRow;
  lead_status: LeadStatus;
  follow_up_created: FollowUpRow | null;
}

export interface FollowUpItem extends FollowUpRow {
  restaurant_id: string;
  restaurant_name: string;
}

export interface DashboardStats {
  restaurants_total: number;
  leads_total: number;
  leads_new: number;
  leads_qualified: number;
  pending_contact: number;
  follow_ups_due_today: number;
  follow_ups_overdue: number;
  interested: number;
  meetings: number;
  customers: number;
  conversion_rate: number;
}
