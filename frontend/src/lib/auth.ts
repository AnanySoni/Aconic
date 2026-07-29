const ACCESS_KEY = "aconic_access_token";
const REFRESH_KEY = "aconic_refresh_token";

export function saveTokens(access: string, refresh: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function requireAuthClient(): string {
  const token = getAccessToken();
  if (!token) {
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  return token;
}
