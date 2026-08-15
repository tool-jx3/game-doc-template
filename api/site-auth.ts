import {
  COOKIE_NAME,
  MAX_AGE_SECONDS,
  createAuthCookieValue,
  pinToOrigin,
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

  const origin = new URL(request.url).origin;

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    const safeErrorUrl = pinToOrigin("/", origin);
    safeErrorUrl.searchParams.set("error", "1");
    return new Response(null, {
      status: 302,
      headers: { Location: safeErrorUrl.toString() },
    });
  }

  const password = String(form.get("password") ?? "");
  const redirect = sanitizeRedirect(String(form.get("redirect") ?? "/"));
  const expected = process.env.SITE_PASSWORD || "";

  if (expected && password === expected) {
    const value = await createAuthCookieValue(expected);
    const safeLocation = pinToOrigin(redirect, origin);
    return new Response(null, {
      status: 302,
      headers: {
        Location: safeLocation.toString(),
        "Set-Cookie": `${COOKIE_NAME}=${value}; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE_SECONDS}; Path=/`,
      },
    });
  }

  const safeErrorUrl = pinToOrigin(redirect, origin);
  safeErrorUrl.searchParams.set("error", "1");
  return new Response(null, {
    status: 302,
    headers: { Location: safeErrorUrl.toString() },
  });
}
