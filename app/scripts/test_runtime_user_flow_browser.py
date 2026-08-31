from __future__ import annotations

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

import test_runtime_browser as runtime

DETAIL_MEDIA_TIMEOUT_SECONDS = 8


def loaded_relevant_media(image) -> bool:
    return bool(image and image.get("complete") and int(image.get("naturalWidth") or 0) > 0)


def open_visible_detail_with_loaded_relevant_media(driver) -> str | None:
    """Open a visible event only after its canonical direct card image has loaded.

    The base scenario previously treated the presence of
    `img[data-event-image="relevant"]` as proof that direct media was usable. A
    remote image can exist in the DOM briefly and then fail, at which point the
    shared image-quality policy removes or replaces it. Selecting during that
    interval made the detail-media assertion race the image error handler.

    This owner tightens the precondition: the selected card must have a direct
    relevant image with `complete && naturalWidth > 0`. The detail must then
    expose a loaded direct relevant image for the same event before control
    returns to the original strict assertions.
    """
    opened = driver.execute_async_script(
        r'''
        const done = arguments[arguments.length - 1];
        const visible = (node) => {
          if (!node || node.hidden || node.closest('[hidden]')) return false;
          const style = getComputedStyle(node);
          return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
        };
        Promise.all([
          import('./agenda-runtime-state.mjs'),
          import('./image-resolver-core.mjs'),
        ]).then(([runtime, images]) => {
          const city = document.documentElement.dataset.city || '';
          const snapshot = runtime.getAgendaRuntimeSnapshot(city);
          const indexed = new Map((snapshot?.events || []).map((event) => [String(event?.id || ''), event]));
          const cards = [...document.querySelectorAll('.event-card[data-event-id]')].filter(visible);
          const directMedia = (card) => {
            const event = indexed.get(String(card.dataset.eventId || ''));
            return event ? images.relevantEventImageUrl(event, { baseUrl: location.href }) : null;
          };

          // A legitimate event without direct media must still open a usable
          // detail. Card-only representative/category fallbacks must not turn
          // into invented detail media.
          const noMediaCard = cards.find((candidate) =>
            !directMedia(candidate) && candidate.querySelector('[data-open-event]')
          );
          if (noMediaCard) {
            noMediaCard.querySelector('[data-open-event]').click();
            const noMediaDialog = document.querySelector('dialog[data-event-detail][open]');
            if (!noMediaDialog || noMediaDialog.querySelector('.event-detail-media')
                || !noMediaDialog.querySelector('.event-detail-content')) {
              return done({ error: 'detail without direct media is not renderable' });
            }
            noMediaDialog.remove();
          }

          const card = cards.find((candidate) => {
            const direct = directMedia(candidate);
            const image = candidate.querySelector('img[data-event-image="relevant"]');
            const trigger = candidate.querySelector('[data-open-event]');
            return Boolean(direct && image && trigger && image.src === direct
              && image.complete && image.naturalWidth > 0);
          });
          if (!card) return done({ error: 'no loaded canonical direct card media' });
          const eventId = card.dataset.eventId || null;
          card.querySelector('[data-open-event]').click();
          return done({ eventId });
        }).catch((error) => done({ error: String(error?.stack || error) }));
        '''
    )
    if isinstance(opened, dict) and opened.get("error"):
        raise AssertionError(str(opened["error"]))
    event_id = str((opened or {}).get("eventId") if isinstance(opened, dict) else opened or "").strip()
    if not event_id:
        return None

    try:
        WebDriverWait(driver, DETAIL_MEDIA_TIMEOUT_SECONDS, poll_frequency=0.05).until(
            lambda current: bool(
                current.execute_script(
                    r'''
                    const dialog = document.querySelector('dialog[data-event-detail][open]');
                    if (!dialog || dialog.dataset.eventDetail !== arguments[0]) return false;
                    const image = dialog.querySelector('.event-detail-media img[data-event-image="relevant"]');
                    return Boolean(image && /^(https?:)\/\//i.test(image.src || '') && image.complete && image.naturalWidth > 0);
                    ''',
                    event_id,
                )
            )
        )
    except TimeoutException as exc:
        diagnostics = driver.execute_script(
            r'''
            const dialog = document.querySelector('dialog[data-event-detail][open]');
            const image = dialog?.querySelector('.event-detail-media img[data-event-image="relevant"]');
            return {
              eventId: dialog?.dataset?.eventDetail || null,
              hasMedia: Boolean(image),
              src: image?.src || null,
              complete: Boolean(image?.complete),
              naturalWidth: Number(image?.naturalWidth || 0),
            };
            '''
        )
        raise AssertionError(
            f"loaded canonical direct detail media did not settle for event {event_id} within "
            f"{DETAIL_MEDIA_TIMEOUT_SECONDS}s; diagnostics={diagnostics}"
        ) from exc
    return event_id


def main() -> None:
    runtime.open_visible_detail_with_relevant_media = open_visible_detail_with_loaded_relevant_media
    runtime.main()


if __name__ == "__main__":
    main()
