import test from "node:test";
import assert from "node:assert/strict";
import {
  SOURCE_PRIORITY,
  applyCanonicalSourceEvidence,
  classifySourceEvidence,
  chooseCanonicalSourceEvidence,
} from "./source-evidence-policy.mjs";
import { deduplicateCrossSourceDataset } from "./cross-source-deduplication.mjs";
import { normalizeAgendaSourceEvidence } from "./source-evidence-normalizer.mjs";

function baseEvent({ id, sourceId, sourceName, sourceUrl, official = false, venue = "Teatro Principal", city = "Gijón" }) {
  const start = "2026-08-28T19:00:00+02:00";
  return {
    id,
    title: "Noche de jazz",
    event_type: "event",
    source_id: sourceId,
    source_name: sourceName,
    source_url: sourceUrl,
    primary_category: { id: "musica", label: "Música" },
    categories: [{ id: "musica", label: "Música" }],
    schedule: { mode: "dated", start, end: start, occurrences: [{ start, end: start }] },
    location: { venue, city },
    links: { source: sourceUrl },
    public_status: { source_official: official, information_completeness: "complete" },
  };
}

test("source hierarchy is explicit and stable", () => {
  assert.deepEqual(SOURCE_PRIORITY, {
    official: 0,
    institutional: 1,
    ticketing: 2,
    web: 3,
    social_aggregator: 4,
  });

  const official = baseEvent({
    id: "official",
    sourceId: "teatro",
    sourceName: "Teatro Principal",
    sourceUrl: "https://teatro.example/evento",
    official: true,
  });
  const institutional = baseEvent({ id: "institutional", sourceId: "gijon", sourceName: "Ayuntamiento de Gijón", sourceUrl: "https://www.gijon.es/evento" });
  const ticketing = baseEvent({ id: "tickets", sourceId: "passline", sourceName: "Passline", sourceUrl: "https://www.passline.com/evento" });
  const web = baseEvent({ id: "web", sourceId: "cultura", sourceName: "Cultura local", sourceUrl: "https://culturalocal.example/evento" });
  const social = baseEvent({ id: "social", sourceId: "instagram", sourceName: "Instagram", sourceUrl: "https://www.instagram.com/p/ABC/?igsh=tracking" });

  assert.equal(classifySourceEvidence(official, official.source_url).source_kind, "official");
  assert.equal(classifySourceEvidence(institutional, institutional.source_url).source_kind, "institutional");
  assert.equal(classifySourceEvidence(ticketing, ticketing.source_url).source_kind, "ticketing");
  assert.equal(classifySourceEvidence(web, web.source_url).source_kind, "web");
  assert.equal(classifySourceEvidence(social, social.source_url).source_kind, "social_aggregator");

  const evidence = chooseCanonicalSourceEvidence(social, web, ticketing, institutional, official);
  assert.equal(evidence.primary.url, "https://teatro.example/evento");
  assert.deepEqual(evidence.secondary.map((item) => item.source_kind), [
    "institutional", "ticketing", "web", "social_aggregator",
  ]);
});

test("canonicalization is idempotent and aligns links.source", () => {
  const ticketing = baseEvent({ id: "tickets", sourceId: "passline", sourceName: "Passline", sourceUrl: "https://www.passline.com/evento" });
  ticketing.links.tickets = ticketing.source_url;
  const official = baseEvent({
    id: "official",
    sourceId: "teatro",
    sourceName: "Teatro Principal",
    sourceUrl: "https://teatro.example/evento",
    official: true,
  });
  official.links.official = official.source_url;

  const merged = applyCanonicalSourceEvidence(ticketing, official);
  assert.equal(merged.source_url, "https://teatro.example/evento");
  assert.deepEqual(merged.secondary_source_urls, ["https://passline.com/evento"]);
  assert.equal(merged.links.source, merged.source_url);
  assert.deepEqual(applyCanonicalSourceEvidence(merged, official), merged);
});

test("cross-source duplicate becomes explicit secondary evidence", () => {
  const institutional = baseEvent({
    id: "municipal-jazz",
    sourceId: "gijon-agenda",
    sourceName: "Ayuntamiento de Gijón",
    sourceUrl: "https://www.gijon.es/evento/jazz",
  });
  const ticketing = baseEvent({
    id: "ticket-jazz",
    sourceId: "ticketmaster",
    sourceName: "Ticketmaster",
    sourceUrl: "https://www.ticketmaster.es/event/jazz",
  });
  ticketing.links.tickets = ticketing.source_url;

  const deduped = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [ticketing, institutional] });
  assert.equal(deduped.events.length, 1);
  assert.equal(deduped.events[0].editorial.cross_source_deduplicated, true);

  const normalized = normalizeAgendaSourceEvidence(deduped);
  assert.equal(normalized.events[0].source_url, "https://gijon.es/evento/jazz");
  assert.deepEqual(normalized.events[0].secondary_source_urls, ["https://ticketmaster.es/event/jazz"]);
  assert.equal(normalized.events[0].links.tickets, "https://www.ticketmaster.es/event/jazz");
});

test("an explicit official link outranks institutional and ticketing evidence", () => {
  const event = baseEvent({
    id: "mixed",
    sourceId: "ticketmaster",
    sourceName: "Ticketmaster",
    sourceUrl: "https://ticketmaster.es/event/x",
  });
  event.links = {
    source: event.source_url,
    tickets: event.source_url,
    official: "https://teatroprincipal.example/programacion/x",
  };
  event.secondary_source_urls = ["https://www.gijon.es/evento/x"];

  const normalized = applyCanonicalSourceEvidence(event);
  assert.equal(normalized.source_url, "https://teatroprincipal.example/programacion/x");
  assert.deepEqual(normalized.secondary_source_urls, [
    "https://gijon.es/evento/x",
    "https://ticketmaster.es/event/x",
  ]);
});
