/** Typed API client: bearer token, JSON, 401 handling. */

const BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "http://127.0.0.1:8000/api/v1";

const TOKEN_KEY = "rl_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  // Any expired/invalid token (outside login itself) -> back to login.
  if (response.status === 401 && !path.startsWith("/auth/login")) {
    setToken(null);
    window.location.href = "/login";
    throw new ApiError(401, "No autenticado");
  }

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const data: unknown = await response.json();
      if (
        typeof data === "object" &&
        data !== null &&
        "detail" in data &&
        typeof (data as { detail: unknown }).detail === "string"
      ) {
        detail = (data as { detail: string }).detail;
      }
    } catch {
      // keep the default detail
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}
