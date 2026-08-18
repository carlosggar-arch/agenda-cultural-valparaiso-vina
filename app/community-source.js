const styleHref = new URL("./community-source.css", import.meta.url).href;
if (![...document.styleSheets].some((sheet) => sheet.href === styleHref)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = styleHref;
  document.head.append(link);
}

const FEEDBACK_API = "https://agenda-cultural-community.carlosggar.workers.dev/community/v1/feedback";
const LIKE_TOKEN_KEY = "vivamos-global-like-token-v1";
const LIKED_KEY = "vivamos-global-liked-v1";

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

function likeToken() {
  const existing = storageGet(LIKE_TOKEN_KEY);
  if (existing) return existing;
  const token = crypto.randomUUID();
  storageSet(LIKE_TOKEN_KEY, token);
  return token;
}

function renderLike(button, count) {
  const liked = storageGet(LIKED_KEY) === "1";
  button.dataset.liked = liked ? "true" : "false";
  button.setAttribute("aria-pressed", liked ? "true" : "false");
  const numeric = Number.isFinite(Number(count)) ? Number(count) : null;
  button.innerHTML = `<span aria-hidden="true">${liked ? "♥" : "♡"}</span><span>${numeric === null ? "" : numeric}</span>`;
  button.setAttribute("aria-label", liked
    ? `Te gusta ¡Vivamos!${numeric === null ? "" : `. ${numeric} me gusta`}`
    : `Indicar que te gusta ¡Vivamos!${numeric === null ? "" : `. ${numeric} me gusta`}`);
}

async function loadLikeCount(button) {
  renderLike(button, null);
  try {
    const response = await fetch(`${FEEDBACK_API}/likes`, { headers: { Accept: "application/json" } });
    const data = await response.json();
    if (response.ok) renderLike(button, data.count);
  } catch {}
}

async function submitLike(button) {
  if (storageGet(LIKED_KEY) === "1") return;
  button.disabled = true;
  try {
    const response = await fetch(`${FEEDBACK_API}/likes`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ token: likeToken() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "No se pudo registrar el me gusta.");
    storageSet(LIKED_KEY, "1");
    renderLike(button, data.count);
  } catch {
    button.title = "No pudimos registrar el me gusta en este momento.";
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
      <button type="button" class="source-like-button" data-community-like aria-pressed="false"><span aria-hidden="true">♡</span><span></span></button>
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
