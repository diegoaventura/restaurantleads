/** Endpoint wrappers: one module per API area. */

import { api } from "./client";
import type {
  DashboardStats,
  FollowUpItem,
  FollowUpRow,
  InteractionCreated,
  InteractionChannel,
  InteractionResult,
  LeadPriority,
  LeadStatus,
  LeadSummary,
  DeliveryPlatform,
  Page,
  RestaurantDetail,
  RestaurantRow,
  SourceType,
  UserOut,
} from "./types";

// --- auth ---

export function loginRequest(email: string, password: string) {
  return api<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function meRequest() {
  return api<UserOut>("/auth/me");
}

// --- restaurants / leads ---

export interface RestaurantFilters {
  search?: string;
  city?: string;
  category?: string;
  status?: LeadStatus;
  platform?: DeliveryPlatform;
  source?: SourceType;
  min_score?: number;
  sort?: "score" | "name" | "updated_at";
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export function listRestaurants(filters: RestaurantFilters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return api<Page<RestaurantRow>>(`/restaurants${query ? `?${query}` : ""}`);
}

export function getRestaurant(id: string) {
  return api<RestaurantDetail>(`/restaurants/${id}`);
}

export function patchLead(
  id: string,
  body: { status?: LeadStatus; priority?: LeadPriority; assigned_to?: string },
) {
  return api<LeadSummary>(`/restaurants/${id}/lead`, { method: "PATCH", body });
}

export interface RestaurantExport {
  exported_at: string;
  restaurant: RestaurantDetail;
}

export function exportRestaurant(id: string) {
  return api<RestaurantExport>(`/restaurants/${id}/export`);
}

export interface AssignableUser {
  id: string;
  full_name: string;
  role: "admin" | "sales";
}

export function listAssignableUsers() {
  return api<AssignableUser[]>("/users/assignable");
}

// --- CRM ---

export function createInteraction(
  restaurantId: string,
  body: { channel: InteractionChannel; result: InteractionResult; notes?: string },
) {
  return api<InteractionCreated>(`/restaurants/${restaurantId}/interactions`, {
    method: "POST",
    body,
  });
}

export function createFollowUp(
  restaurantId: string,
  body: { scheduled_at: string; channel: InteractionChannel; notes?: string },
) {
  return api<FollowUpRow>(`/restaurants/${restaurantId}/follow-ups`, {
    method: "POST",
    body,
  });
}

export function listFollowUps(params: { status?: string; due_on?: string }) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  return api<Page<FollowUpItem>>(`/follow-ups?${search.toString()}`);
}

export function actOnFollowUp(
  id: string,
  body: { action: "complete" | "postpone" | "cancel"; new_date?: string; notes?: string },
) {
  return api<FollowUpRow>(`/follow-ups/${id}`, { method: "PATCH", body });
}

// --- dashboard ---

export function getStats() {
  return api<DashboardStats>("/dashboard/stats");
}
