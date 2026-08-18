# Mobile experience acceptance criteria

This layer improves the first-open and one-hand PWA experience without changing city datasets or editorial pipelines.

- First visit requires an explicit city choice unless a supported city is already saved or geolocation permission was previously granted.
- At phone widths the city chooser is presented as a bottom sheet with large touch targets.
- The active city is visibly marked in the chooser.
- The genuine header controls remain in their designed top-header position on mobile; the retired Agenda/Search/My plans/City tabbar must not return.
- Primary mobile controls meet a 44px minimum touch target.
- Standalone mode respects safe-area insets.
- Valparaiso/Viña and Gijón retain their own visual identity through the existing city theme variables and illustrations.
- Installation metadata identifies the app as ¡Vivamos! on supported mobile browsers.
- `mobile-experience.css` is loaded from `app/index.html` inside `<head>` before first paint.
- JavaScript must not rewrite the existing `mobile-experience.css` href after startup; doing so can trigger a second stylesheet load and visible layout movement.
- The mobile asset revision used by `index.html`, `pwa.js`, `mobile-experience.js`, and `service-worker.js` must stay synchronized.
- The visible PWA version, JavaScript app version, service-worker registration version, and service-worker cache version must stay synchronized.
