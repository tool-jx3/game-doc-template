import {
  COOKIE_NAME,
  MAX_AGE_SECONDS,
  createAuthCookieValue,
  sanitizeRedirect,
} from "../lib/site-auth-shared";

export const config = { runtime: "edge" };

export default async function handler(request: Request): Promise<Response> {
  if (request.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  const form = await request.formData();
  const password = String(form.get("password") ?? "");
  const redirect = sanitizeRedirect(String(form.get("redirect") ?? "/"));
  const expected = process.env.SITE_PASSWORD || "";
  const origin = new URL(request.url).origin;

  if (expected && password === expected) {
    const value = await createAuthCookieValue(expected);
    const location = new URL(redirect, origin);
    // Defense in depth: even if sanitizeRedirect has a gap, never issue a
    // Location header that resolves off-origin.
    const safeLocation = location.origin === origin ? location : new URL("/", origin);
    return new Response(null, {
      status: 302,
      headers: {
        Location: safeLocation.toString(),
        "Set-Cookie": `${COOKIE_NAME}=${value}; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE_SECONDS}; Path=/`,
      },
    });
  }

  const errorUrl = new URL(redirect, origin);
  const safeErrorUrl = errorUrl.origin === origin ? errorUrl : new URL("/", origin);
  safeErrorUrl.searchParams.set("error", "1");
  return new Response(null, {
    status: 302,
    headers: { Location: safeErrorUrl.toString() },
  });
}
