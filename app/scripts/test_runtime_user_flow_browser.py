from __future__ import annotations

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

import test_runtime_browser as runtime

DETAIL_MEDIA_TIMEOUT_SECONDS = 8
BASE_OPEN_VISIBLE_DETAIL = runtime.open_visible_detail_with_relevant_media


def detail_media_ready(driver, event_id: str) -> bool:
    return bool(
        driver.execute_script(
            r'''
            const dialog = document.querySelector('dialog[data-event-detail][open]');
            if (!dialog || dialog.dataset.eventDetail !== arguments[0]) return false;
            const image = dialog.querySelector('.event-detail-media img[data-event-image="relevant"]');
            return Boolean(image && /^(https?:)\/\//i.test(image.src || ''));
            ''',
            event_id,
        )
    )


def open_visible_detail_after_media_runtime_is_ready(driver) -> str | None:
    """Open one canonical-media event and return only after detail media settles.

    The base runtime scenario deliberately exercises the real async presentation
    pipeline. On fast runners the dialog shell can open one task before the
    detail-media enhancer commits the canonical direct image. Treating shell-open
    as detail-ready produced false failures. This owner keeps the assertion strict
    and changes only readiness: the event id is returned after the same direct
    relevant media is observable on the open dialog.
    """
    open_event_id = driver.execute_script(
        "return document.querySelector('dialog[data-event-detail][open]')?.dataset?.eventDetail || null;"
    )
    event_id = str(open_event_id or BASE_OPEN_VISIBLE_DETAIL(driver) or "").strip()
    if not event_id:
        return None

    try:
        WebDriverWait(driver, DETAIL_MEDIA_TIMEOUT_SECONDS, poll_frequency=0.05).until(
            lambda current: detail_media_ready(current, event_id)
        )
    except TimeoutException as exc:
        raise AssertionError(
            f"canonical direct detail media did not settle for event {event_id} within "
            f"{DETAIL_MEDIA_TIMEOUT_SECONDS}s"
        ) from exc
    return event_id


def main() -> None:
    runtime.open_visible_detail_with_relevant_media = open_visible_detail_after_media_runtime_is_ready
    runtime.main()


if __name__ == "__main__":
    main()
