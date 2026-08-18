const styleHref = new URL("./community-source.css?v=20260818-feedback2", import.meta.url).href;
if (![...document.styleSheets].some((sheet) => sheet.href === styleHref)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = styleHref;
  document.head.append(link);
}

const FEEDBACK_API = "https://agenda-cultural-community.carlosggar.workers.dev/community/v1/feedback";
const LIKE_TOKEN_KEY = "vivamos-global-like-token-v1";
const LIKED_KEY = "vivamos-global-liked-v1";
const LIKE_PENDING_KEY = "vivamos-global-like-pending-v1";

function activeCityId() {
  return document.documentElement.dataset.city === "gijon" ? "gijon" : "valparaiso";
}

function syncLink(link) {
  const url = new URL("./proponer-fuente.html", window.location.href);
  url.searchParams.set("city", activeCityId());
  link.href = `${url.pathname}${url.search}`;
}

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch {}
}

function storageRemove(key) {
  try { localStorage.removeItem(key); } catch {}
}

function likeToken() {
  const existing = storageGet(LIKE_TOKEN_KEY);
  if (existing) return existing;
  const token = crypto.randomUUID();
  storageSet(LIKE_TOKEN_KEY, token);
  return token;
}

function currentLikeCount(button) {
  const value = Number(button.querySelector("[data-like-count]")?.textContent || 0);
  return Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0;
}

function renderLike(button, count = 0) {
  const liked = storageGet(LIKED_KEY) === "1";
  const pending = storageGet(LIKE_PENDING_KEY) === "1";
  let numeric = Number.isFinite(Number(count)) ? Math.max(0, Math.trunc(Number(count))) : 0;
  if (liked && pending) numeric = Math.max(1, numeric);
  button.dataset.liked = liked ? "true" : "false";
  button.dataset.likePending = pending ? "true" : "false";
  button.setAttribute("aria-pressed", liked ? "true" : "false");
  button.innerHTML = `<span aria-hidden="true">${liked ? "♥" : "♡"}</span><span data-like-count>${numeric}</span>`;
  const pendingText = pending ? " Pendiente de sincronización." : "";
  button.setAttribute("aria-label", liked
    ? `Te gusta ¡Vivamos!. ${numeric} me gusta.${pendingText}`
    : `Indicar que te gusta ¡Vivamos!. ${numeric} me gusta.`);
  button.title = pending ? "Tu me gusta está guardado y se sincronizará automáticamente." : "";
}

async function syncPendingLike(button, knownCount = null) {
  if (storageGet(LIKED_KEY) !== "1" || storageGet(LIKE_PENDING_KEY) !== "1") return;
  try {
    const response = await fetch(`${FEEDBACK_API}/likes`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ token: likeToken() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "No se pudo sincronizar el me gusta.");
    storageRemove(LIKE_PENDING_KEY);
    renderLike(button, data.count);
  } catch {
    renderLike(button, Math.max(currentLikeCount(button), Number(knownCount) || 0, 1));
  }
}

async function loadLikeCount(button) {
  renderLike(button, storageGet(LIKED_KEY) === "1" ? 1 : 0);
  let serverCount = null;
  try {
    const response = await fetch(`${FEEDBACK_API}/likes`, { headers: { Accept: "application/json" } });
    const data = await response.json();
    if (response.ok && Number.isFinite(Number(data.count))) {
      serverCount = Math.max(0, Math.trunc(Number(data.count)));
      renderLike(button, serverCount);
    }
  } catch {}
  await syncPendingLike(button, serverCount);
}

async function submitLike(button) {
  if (storageGet(LIKED_KEY) === "1") {
    await syncPendingLike(button, currentLikeCount(button));
    return;
  }
  const optimisticCount = currentLikeCount(button) + 1;
  storageSet(LIKED_KEY, "1");
  storageSet(LIKE_PENDING_KEY, "1");
  renderLike(button, optimisticCount);
  button.disabled = true;
  try {
    await syncPendingLike(button, optimisticCount);
  } finally {
    button.disabled = false;
  }
}

function buildCommentDialog() {
  const existing = document.querySelector("[data-community-comment-dialog]");
  if (existing) return existing;
  const dialog = document.createElement("dialog");
  dialog.className = "community-comment-dialog";
  dialog.dataset.communityCommentDialog = "";
  dialog.innerHTML = `
    <form class="community-comment-form" data-community-comment-form>
      <button type="button" class="community-comment-close" data-comment-close aria-label="Cerrar">×</button>
      <p class="eyebrow">Tu opinión</p>
      <h2>Comentarios sobre ¡Vivamos!</h2>
      <p class="community-comment-intro">Cuéntanos qué mejorarías, qué echas de menos o qué te está resultando útil.</p>
      <label>Comentario
        <textarea name="comment" required maxlength="2400" rows="6" placeholder="Escribe aquí tu comentario…"></textarea>
      </label>
      <div class="community-comment-optional">
        <label>Nombre <span>(opcional)</span><input name="contact_name" maxlength="160" autocomplete="name"></label>
        <label>Correo <span>(opcional)</span><input name="contact_email" maxlength="254" type="email" autocomplete="email"></label>
      </div>
      <label class="honeypot" aria-hidden="true">Sitio web<input name="website" tabindex="-1" autocomplete="off"></label>
      <p class="community-comment-privacy">El comentario se recibe de forma privada y queda pendiente de revisión. El correo, si lo indicas, sólo se usa para poder responderte.</p>
      <p class="community-comment-status" data-comment-status role="status" aria-live="polite"></p>
      <div class="community-comment-actions">
        <button type="button" class="community-comment-cancel" data-comment-close>Cancelar</button>
        <button type="submit" class="community-comment-submit">Enviar comentario</button>
      </div>
    </form>
  `;
  document.body.append(dialog);
  const close = () => { if (dialog.open) dialog.close(); };
  dialog.querySelectorAll("[data-comment-close]").forEach((button) => button.addEventListener("click", close));
  dialog.addEventListener("click", (event) => { if (event.target === dialog) close(); });

  const form = dialog.querySelector("[data-community-comment-form]");
  const status = dialog.querySelector("[data-comment-status]");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const submit = form.querySelector('button[type="submit"]');
    const values = Object.fromEntries(new FormData(form));
    if (submit) submit.disabled = true;
    if (status) status.textContent = "Enviando comentario…";
    try {
      const response = await fetch(`${FEEDBACK_API}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          city: activeCityId(),
          comment: values.comment || "",
          contact_name: values.contact_name || "",
          contact_email: values.contact_email || "",
          website: values.website || "",
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "No se pudo enviar el comentario.");
      form.reset();
      if (status) status.textContent = "Comentario recibido. Gracias por ayudarnos a mejorar ¡Vivamos!";
    } catch (error) {
      if (status) status.textContent = error instanceof Error ? error.message : "No se pudo enviar el comentario.";
    } finally {
      if (submit) submit.disabled = false;
    }
  });
  return dialog;
}

function openComments() {
  const dialog = buildCommentDialog();
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
  requestAnimationFrame(() => dialog.querySelector("textarea")?.focus());
}

function mountSourceProposal() {
  const section = document.querySelector("[data-sources-section]");
  const grid = section?.querySelector("[data-sources-grid]");
  if (!section || !grid || section.querySelector("[data-source-proposal-cta]")) return;

  const cta = document.createElement("aside");
  cta.className = "source-proposal-cta";
  cta.dataset.sourceProposalCta = "";
  cta.innerHTML = `
    <div class="source-proposal-copy">
      <strong>¿Conoces una fuente que debería estar aquí?</strong>
      <p>Propón una fuente o cuéntanos qué mejorarías.</p>
    </div>
    <div class="source-proposal-actions" aria-label="Participa en ¡Vivamos!">
      <a class="source-proposal-link" data-source-proposal-link><span class="source-action-long">+ Aportar fuente</span><span class="source-action-short">+ Fuente</span></a>
      <button type="button" class="source-feedback-button" data-community-comments>💬 <span>Comentarios</span></button>
      <button type="button" class="source-like-button" data-community-like aria-pressed="false"><span aria-hidden="true">♡</span><span data-like-count>0</span></button>
    </div>
  `;
  grid.insertAdjacentElement("afterend", cta);
  const link = cta.querySelector("[data-source-proposal-link]");
  if (link) syncLink(link);
  cta.querySelector("[data-community-comments]")?.addEventListener("click", openComments);
  const like = cta.querySelector("[data-community-like]");
  if (like) {
    like.addEventListener("click", () => submitLike(like));
    loadLikeCount(like);
  }
}

mountSourceProposal();
new MutationObserver(() => {
  mountSourceProposal();
  const link = document.querySelector("[data-source-proposal-link]");
  if (link) syncLink(link);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
