export const COOKIE_NAME = "site_auth";
export const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

async function hmacSign(payload: string, secret: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  return btoa(String.fromCharCode(...new Uint8Array(sig)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** cookie 值格式：`<expiresEpochSeconds>.<base64url(HMAC-SHA256(expires, password))>` */
export async function createAuthCookieValue(password: string): Promise<string> {
  const expires = Math.floor(Date.now() / 1000) + MAX_AGE_SECONDS;
  const payload = String(expires);
  return `${payload}.${await hmacSign(payload, password)}`;
}

export async function verifyAuthCookieValue(
  value: string | null,
  password: string,
): Promise<boolean> {
  if (!value || !password) return false;
  const dot = value.indexOf(".");
  if (dot <= 0) return false;
  const payload = value.slice(0, dot);
  const expires = Number(payload);
  if (!Number.isFinite(expires) || expires * 1000 < Date.now()) return false;
  return timingSafeEqual(value.slice(dot + 1), await hmacSign(payload, password));
}

/** 只接受站內相對路徑，阻擋 open redirect（`//evil.com`、絕對網址、反斜線變體）。 */
export function sanitizeRedirect(redirect: string | null | undefined): string {
  if (!redirect) return "/";
  if (!redirect.startsWith("/") || redirect.startsWith("//") || redirect.startsWith("/\\")) {
    return "/";
  }
  return redirect;
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
