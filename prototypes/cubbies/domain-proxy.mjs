// One fixed origin, no storage, content logs, or redirect-following with credentials.
const PUBLIC_ORIGIN = "https://cubby.bayleaf.dev";
const RUN_ORIGIN = "https://gremlin-331254975906.us-west1.run.app";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.hostname !== "cubby.bayleaf.dev") {
      return new Response("Unknown host", { status: 404 });
    }
    if (url.protocol !== "https:") {
      return Response.redirect(PUBLIC_ORIGIN + url.pathname + url.search, 308);
    }
    const target = new URL(RUN_ORIGIN);
    target.pathname = url.pathname;
    target.search = url.search;
    const headers = new Headers(request.headers);
    headers.set("Host", target.hostname);
    headers.set("X-Forwarded-Host", "cubby.bayleaf.dev");
    headers.set("X-Forwarded-Proto", "https");
    // Keep the real browser Origin: the app's CSRF check uses its PUBLIC_URL.
    try {
      const upstream = await fetch(new Request(target, request), {
        headers,
        redirect: "manual",
        // An explicit cacheTtl can strip Set-Cookie, even when set to zero.
        cache: "no-store",
        cf: { cacheEverything: false },
      });
      const response = new Response(upstream.body, upstream);
      // Suppress zone-wide beacon injection without changing other BayLeaf sites.
      response.headers.set("Cache-Control", "no-store, no-transform");
      const location = response.headers.get("Location");
      if (location) {
        const redirect = new URL(location, RUN_ORIGIN);
        if (redirect.origin === RUN_ORIGIN) {
          response.headers.set("Location", PUBLIC_ORIGIN + redirect.pathname + redirect.search + redirect.hash);
        }
      }
      return response;
    } catch {
      return new Response("Campus Cubbies is temporarily unavailable.", {
        status: 503, headers: { "Cache-Control": "no-store" },
      });
    }
  },
};
