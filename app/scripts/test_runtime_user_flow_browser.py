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
    opened = driver.execute_script(
        r'''
        const visible = (node) => {
          if (!node || node.hidden || node.closest('[hidden]')) return false;
          const style = getComputedStyle(node);
          return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
        };
        const cards = [...document.querySelectorAll('.event-card[data-event-id]')].filter(visible);
        const card = cards.find((candidate) => {
          const image = candidate.querySelector('img[data-event-image="relevant"]');
          const trigger = candidate.querySelector('[data-open-event]');
          return Boolean(image && trigger && image.complete && image.naturalWidth > 0);
        });
        if (!card) return null;
        const trigger = card.querySelector('[data-open-event]');
        const eventId = card.dataset.eventId || null;
        trigger.click();
        return eventId;
        '''
    )
    event_id = str(opened or "").strip()
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
