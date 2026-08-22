import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";

// C3 compatibility shim. Exhibition visit-hours resolution and every DOM write
// now belong to schedule-display.js. Keep this module temporarily in the shared
// shell so old cached app.js versions can still import it safely during a
// rolling PWA update, but it must not resolve, render or mutate schedule data.
void getAgendaRuntimeSnapshot;

function compatibilityNoop() {}
window.addEventListener("vivamos:agenda-rendered", compatibilityNoop);
