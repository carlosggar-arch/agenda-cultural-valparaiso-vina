# Mobile experience acceptance criteria

This layer improves the first-open and one-hand PWA experience without changing city datasets or editorial pipelines.

- First visit requires an explicit city choice unless a supported city is already saved or geolocation permission was previously granted.
- At phone widths the city chooser is presented as a bottom sheet with large touch targets.
- The active city is visibly marked in the chooser.
- Mobile actions remain usable without reintroducing the retired bottom tabbar.
- Primary mobile controls meet a 44px minimum touch target.
- Standalone mode respects safe-area insets.
- Valparaiso/Viña and Gijón retain their own visual identity through the existing city theme variables and illustrations.
- Installation metadata identifies the app as ¡Vivamos! on supported mobile browsers.
- Header and mobile CSS are loaded from `app/index.html` inside `<head>` before first paint.
- Hydration must not rewrite the href of an already loaded header/mobile stylesheet.
- The static search control must remain bound and interactive after hydration.
- `release-version.js` is the single source of truth for the visible PWA version and service-worker cache release.
- The release guard and first-render browser probe must pass on the final release commit before publication.
