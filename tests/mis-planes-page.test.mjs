import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = async (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("home screens expose Mis planes compactly without rendering the full section", async () => {
  const [web, app] = await Promise.all([read("assets/favorites-web.js"), read("app/favorites.js")]);
  assert.match(web, /dataset\.favoritesAccess = "web"/);
  assert.match(web, /const MY_PLANS_URL = "\.\/mis-planes\/"/);
  assert.doesNotMatch(web, /buildMyPlansSection/);
  assert.match(app, /dataset\.favoritesAccess = "app"/);
  assert.match(app, /mis-planes\.html\?city=/);
  assert.doesNotMatch(app, /buildMyPlansSection/);
});

test("dedicated web and app pages render the shared Mis planes view", async () => {
  const [webPage, appPage, renderer] = await Promise.all([
    read("mis-planes/index.html"),
    read("app/mis-planes.html"),
    read("assets/mis-planes-page.mjs"),
  ]);
  assert.match(webPage, /data-favorites-mode="web"/);
  assert.match(webPage, /data-favorites-city="valparaiso"/);
  assert.match(appPage, /data-favorites-mode="app"/);
  assert.match(appPage, /data-my-plans-page/);
  assert.match(renderer, /buildMyPlansSection/);
  assert.match(renderer, /querySelectorAll\("\[data-my-plans-back\]"\)/);
  assert.match(renderer, /agenda-cultural-city/);
});
