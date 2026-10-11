import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "./domain-proxy.mjs";

const csp = "default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'";

test("fixed-host proxy preserves auth, cookies, Origin, body and Google redirect without caching", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (request, options) => {
    assert.equal(request.url, "https://gremlin-331254975906.us-west1.run.app/login?x=1");
    assert.equal(request.method, "POST");
    assert.equal(await request.text(), "test-body");
    assert.equal(options.headers.get("Origin"), "https://cubby.bayleaf.dev");
    assert.equal(options.headers.get("Authorization"), "Bearer test-only");
    assert.equal(options.headers.get("Cookie"), "session=test-only");
    assert.equal(options.headers.get("X-Forwarded-Host"), "cubby.bayleaf.dev");
    assert.equal(options.redirect, "manual");
    assert.equal(options.cache, "no-store");
    assert.equal(options.cf.cacheTtl, undefined);
    assert.equal(options.cf.cacheEverything, false);
    return new Response(null, { status: 302, headers: {
      Location: "https://accounts.google.com/example",
      "Set-Cookie": "session=test-only; Secure; HttpOnly; SameSite=Lax",
      "Content-Security-Policy": csp,
    } });
  };
  try {
    const r = await worker.fetch(new Request("https://cubby.bayleaf.dev/login?x=1", {
      method: "POST", body: "test-body", headers: {
        Origin: "https://cubby.bayleaf.dev", Authorization: "Bearer test-only",
        Cookie: "session=test-only", "X-Forwarded-Host": "spoof.invalid",
      },
    }));
    assert.equal(r.headers.get("Location"), "https://accounts.google.com/example");
    assert.equal(r.headers.get("Cache-Control"), "no-store, no-transform");
    assert.match(r.headers.get("Set-Cookie"), /Secure/);
    assert.equal(r.headers.get("Content-Security-Policy"), csp);
    assert.equal(r.headers.get("Access-Control-Allow-Origin"), null);
  } finally { globalThis.fetch = original; }
});

test("reject other hosts and force HTTPS before origin access", async () => {
  assert.equal((await worker.fetch(new Request("https://other.invalid/"))).status, 404);
  const r = await worker.fetch(new Request("http://cubby.bayleaf.dev/connect?code=test"));
  assert.equal(r.status, 308);
  assert.equal(r.headers.get("Location"), "https://cubby.bayleaf.dev/connect?code=test");
});

test("rewrite only fixed-origin redirects and redact network failures", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(null, { status: 302, headers: {
      Location: "https://gremlin-331254975906.us-west1.run.app/connect?code=test",
    } });
    const r = await worker.fetch(new Request("https://cubby.bayleaf.dev/"));
    assert.equal(r.headers.get("Location"), "https://cubby.bayleaf.dev/connect?code=test");
    globalThis.fetch = async () => { throw Error("private error value"); };
    const failed = await worker.fetch(new Request("https://cubby.bayleaf.dev/"));
    assert.equal(failed.status, 503);
    assert.equal(failed.headers.get("Cache-Control"), "no-store");
    assert.equal((await failed.text()).includes("private"), false);
  } finally { globalThis.fetch = original; }
});
