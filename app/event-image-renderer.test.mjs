import assert from "node:assert/strict";
import test from "node:test";

import { createEventImageElement } from "./event-image-renderer.mjs";
import { safeHttpImageUrl } from "./image-resolver-core.mjs";

class FakeImage {
  constructor() {
    this.dataset = {};
    this.listeners = [];
    this.hidden = false;
  }
  addEventListener(type, handler, options) {
    this.listeners.push({ type, handler, options });
  }
  dispatch(type) {
    for (const listener of this.listeners.filter((item) => item.type === type)) listener.handler();
  }
}

const documentRef = { createElement: (tag) => {
  assert.equal(tag, "img");
  return new FakeImage();
} };

const ROOT_BASE = "https://example.test/agenda/";
const APP_BASE = "https://example.test/agenda/app/";

for (const city of ["valparaiso", "gijon"]) {
  test(`canonical renderer exposes a loadable owned-image contract for ${city}`, () => {
    const event = {
      id: `${city}-fixture`,
      title: `Fixture ${city}`,
      image: { url: `./assets/event-images/${city}/official.webp` },
    };
    const appUrl = safeHttpImageUrl(event.image.url, { baseUrl: APP_BASE });
    const rootUrl = safeHttpImageUrl(event.image.url, { baseUrl: ROOT_BASE });
    assert.equal(appUrl, `https://example.test/agenda/app/assets/event-images/${city}/official.webp`);
    assert.equal(rootUrl, appUrl);
    for (const url of [appUrl, rootUrl]) {
      const image = createEventImageElement(event, { url, documentRef });
      assert.equal(image.src, appUrl);
      assert.equal(image.dataset.eventImage, "relevant");
      assert.equal(image.dataset.eventImageId, event.id);
      assert.equal(image.loading, "lazy");
      assert.match(image.alt, /Fixture/);
    }
  });
}

test("failed image is hidden before the owning surface installs its fallback", () => {
  let fallbackCalls = 0;
  const event = {
    id: "gijon-teatro-albeniz-fixture",
    title: "Santero y los Muchachos",
    image: { url: "https://www.teatroalbenizgijon.com/wp-content/uploads/2026/04/post-santero.png" },
  };
  const image = createEventImageElement(event, {
    url: event.image.url,
    documentRef,
    onError: () => { fallbackCalls += 1; },
  });
  assert.equal(image.hidden, false);
  image.dispatch("error");
  assert.equal(image.hidden, true);
  assert.equal(image.dataset.eventImageFailed, "true");
  assert.equal(fallbackCalls, 1);
});
