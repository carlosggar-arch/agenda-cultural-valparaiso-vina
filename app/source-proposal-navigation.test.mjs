import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const source = readFileSync(new URL("./service-worker.js", import.meta.url), "utf8");
const scope = "https://vivamos.pages.dev/app/";

function serviceWorker({ online = true, cachedForm = true } = {}) {
  const listeners = new Map();
  const requests = [];
  const cache = {
    async match(request) {
      const url = typeof request === "string" ? request : request.url;
      if (cachedForm && url?.includes("/proponer-fuente.html")) {
        return new Response("<form>FORMULARIO SIN CONEXION</form>", { status: 200 });
      }
      if (url?.includes("/index.html")) {
        return new Response("<h1>AGENDA PRINCIPAL</h1>", { status: 200 });
      }
      return undefined;
    },
    async put() {},
  };
  const sandbox = {
    URL, Response, __VIVAMOS_RELEASE__: 300, __VIVAMOS_SHELL_ASSETS__: ["./index.html"],
    importScripts() {},
    caches: { async open() { return cache; } },
    fetch: async (input) => {
      const url = typeof input === "string" ? input : input.url;
      requests.push(url);
      if (!online) throw new Error("offline");
      assert.equal(new URL(url).pathname, "/app/proponer-fuente", "never fetch redirected .html");
      return new Response("<form>FORMULARIO EN LINEA</form>", { status: 200 });
    },
    self: {
      registration: { scope },
      location: { origin: new URL(scope).origin },
      addEventListener(type, handler) { listeners.set(type, handler); },
    },
  };
  sandbox.globalThis = sandbox;
  runInNewContext(source, sandbox, { filename: "service-worker.js" });
  return {
    requests,
    async navigate(href) {
      let handled;
      const request = { url: new URL(href, scope).href, method: "GET", mode: "navigate" };
      listeners.get("fetch")({
        request,
        respondWith(value) { handled = value; },
        waitUntil() {},
      });
      assert.ok(handled, "navigation must be intercepted");
      return handled;
    },
  };
}

test("canonical and historical URLs serve the form rather than the agenda", async () => {
  const sw = serviceWorker();
  for (const path of ["./proponer-fuente?city=gijon", "./proponer-fuente.html?city=valparaiso"]) {
    const response = await sw.navigate(path);
    assert.equal(response.status, 200);
    assert.match(await response.text(), /FORMULARIO EN LINEA/);
  }
  assert.deepEqual(sw.requests.map((url) => new URL(url).pathname), [
    "/app/proponer-fuente", "/app/proponer-fuente",
  ]);
  assert.equal(new URL(sw.requests[0]).searchParams.get("city"), "gijon");
  assert.equal(new URL(sw.requests[1]).searchParams.get("city"), "valparaiso");
});

test("offline source-form navigation uses the form cache, not index.html", async () => {
  const sw = serviceWorker({ online: false, cachedForm: true });
  const response = await sw.navigate("./proponer-fuente?city=valparaiso");
  assert.equal(response.status, 200);
  assert.match(await response.text(), /FORMULARIO SIN CONEXION/);
});

test("missing offline form returns 503 instead of silently showing the agenda", async () => {
  const sw = serviceWorker({ online: false, cachedForm: false });
  const response = await sw.navigate("./proponer-fuente");
  assert.equal(response.status, 503);
  assert.doesNotMatch(await response.text(), /AGENDA PRINCIPAL/);
});
test("both CTA entry points use canonical route and preserve the selected city", () => {
  const community = readFileSync(new URL("./community-source.js", import.meta.url), "utf8");
  const header = readFileSync(new URL("./header-redesign.js", import.meta.url), "utf8");
  for (const js of [community, header]) {
    assert.ok(js.includes('new URL("./proponer-fuente", import.meta.url)'));
    assert.ok(js.includes('url.searchParams.set("city",'));
    assert.ok(!js.includes('button.href = "./proponer-fuente.html"'));
  }
});
