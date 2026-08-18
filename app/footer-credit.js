const footer = document.querySelector("body > footer");

const CONTACT_ENDPOINT = "https://formsubmit.co/ajax/carlosggar@gmail.com";
const CONTACT_CC = "carlos.garcia@usm.cl";

function buildContactDialog() {
  const dialog = document.createElement("dialog");
  dialog.className = "vivamos-contact-dialog";
  dialog.setAttribute("aria-labelledby", "vivamos-contact-title");

  const panel = document.createElement("div");
  panel.className = "vivamos-contact-panel";

  const close = document.createElement("button");
  close.type = "button";
  close.className = "vivamos-contact-close";
  close.setAttribute("aria-label", "Cerrar formulario de contacto");
  close.textContent = "×";

  const eyebrow = document.createElement("p");
  eyebrow.className = "vivamos-contact-eyebrow";
  eyebrow.textContent = "Contacto";

  const title = document.createElement("h2");
  title.id = "vivamos-contact-title";
  title.textContent = "Escríbeme sobre ¡Vivamos!";

  const intro = document.createElement("p");
  intro.className = "vivamos-contact-intro";
  intro.textContent = "¿Tienes una sugerencia, una corrección o quieres comentar algo sobre la agenda? Envíame un mensaje.";

  const form = document.createElement("form");
  form.className = "vivamos-contact-form";

  const fields = [
    ["nombre", "Nombre", "text", "Tu nombre"],
    ["email", "Correo electrónico", "email", "tu@correo.com"],
    ["asunto", "Asunto", "text", "¿Sobre qué quieres escribir?"],
  ];

  for (const [name, labelText, type, placeholder] of fields) {
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.name = name;
    input.type = type;
    input.placeholder = placeholder;
    input.required = true;
    input.autocomplete = name === "nombre" ? "name" : name === "email" ? "email" : "off";
    label.append(input);
    form.append(label);
  }

  const messageLabel = document.createElement("label");
  messageLabel.textContent = "Mensaje";
  const message = document.createElement("textarea");
  message.name = "mensaje";
  message.rows = 6;
  message.placeholder = "Escribe aquí tu mensaje…";
  message.required = true;
  message.maxLength = 4000;
  messageLabel.append(message);
  form.append(messageLabel);

  const honey = document.createElement("input");
  honey.type = "text";
  honey.name = "_honey";
  honey.className = "vivamos-contact-honey";
  honey.tabIndex = -1;
  honey.autocomplete = "off";
  honey.setAttribute("aria-hidden", "true");
  form.append(honey);

  const privacy = document.createElement("p");
  privacy.className = "vivamos-contact-privacy";
  privacy.textContent = "Tu correo se utilizará únicamente para poder responder a este mensaje.";

  const status = document.createElement("p");
  status.className = "vivamos-contact-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  const actions = document.createElement("div");
  actions.className = "vivamos-contact-actions";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "vivamos-contact-cancel";
  cancel.textContent = "Cancelar";

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "vivamos-contact-submit";
  submit.textContent = "Enviar mensaje";

  actions.append(cancel, submit);
  form.append(privacy, status, actions);
  panel.append(close, eyebrow, title, intro, form);
  dialog.append(panel);
  document.body.append(dialog);

  const closeDialog = () => {
    if (dialog.open) dialog.close();
  };
  close.addEventListener("click", closeDialog);
  cancel.addEventListener("click", closeDialog);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    submit.disabled = true;
    submit.textContent = "Enviando…";
    status.className = "vivamos-contact-status";
    status.textContent = "Enviando tu mensaje…";

    try {
      const data = new FormData(form);
      data.set("_subject", `¡Vivamos! · ${String(data.get("asunto") || "Mensaje de contacto")}`);
      data.set("_cc", CONTACT_CC);
      data.set("_replyto", String(data.get("email") || ""));
      data.set("_template", "table");
      data.set("_url", window.location.href);

      const response = await fetch(CONTACT_ENDPOINT, {
        method: "POST",
        body: data,
        headers: { Accept: "application/json" },
      });
      let payload = null;
      try { payload = await response.json(); } catch {}
      if (!response.ok || payload?.success === false) throw new Error("contact-submit-failed");

      form.reset();
      status.className = "vivamos-contact-status is-success";
      status.textContent = "Mensaje enviado. Gracias por escribir.";
    } catch {
      status.className = "vivamos-contact-status is-error";
      status.textContent = "No pudimos enviar el mensaje. Inténtalo nuevamente en unos momentos.";
    } finally {
      submit.disabled = false;
      submit.textContent = "Enviar mensaje";
    }
  });

  return dialog;
}

const contactDialog = buildContactDialog();

if (footer) {
  footer.classList.add("vivamos-footer");
  footer.replaceChildren();

  const identity = document.createElement("div");
  identity.className = "vivamos-footer-identity";
  identity.innerHTML = "<strong>¡Vivamos!</strong><span>Agenda cultural independiente</span>";

  const credit = document.createElement("p");
  credit.className = "vivamos-footer-credit";
  credit.append("Creado y mantenido por ");
  const author = document.createElement("strong");
  author.textContent = "Carlos García García";
  credit.append(author);

  const contact = document.createElement("button");
  contact.type = "button";
  contact.className = "vivamos-footer-contact";
  contact.textContent = "Contacto";
  contact.setAttribute("aria-haspopup", "dialog");
  contact.addEventListener("click", () => {
    if (typeof contactDialog.showModal === "function") contactDialog.showModal();
    else contactDialog.setAttribute("open", "");
    requestAnimationFrame(() => contactDialog.querySelector('input[name="nombre"]')?.focus());
  });

  const version = document.createElement("small");
  version.dataset.appVersion = "";
  version.textContent = "PWA";

  footer.append(identity, credit, contact, version);
}

const STYLE_ID = "vivamos-footer-credit-style";
if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .vivamos-footer {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto auto;
      align-items: center;
      gap: .7rem 1.15rem;
      width: min(1120px, calc(100% - 2rem));
      margin: 0 auto;
      padding: 1.35rem 0 1.7rem;
      border-top: 1px solid rgba(255,255,255,.16);
      color: rgba(255,255,255,.82);
      font-size: .84rem;
    }
    .vivamos-footer-identity {
      display: flex;
      align-items: baseline;
      gap: .45rem;
      white-space: nowrap;
    }
    .vivamos-footer-identity strong,
    .vivamos-footer-credit strong { color: #fff !important; }
    .vivamos-footer-credit {
      margin: 0;
      min-width: 0;
      color: rgba(255,255,255,.82);
    }
    .vivamos-footer-contact {
      min-height: 2.35rem;
      padding: .5rem .85rem;
      border: 1px solid #f4d16d;
      border-radius: 999px;
      background: #f4d16d;
      color: #103c36;
      font: inherit;
      font-weight: 850;
      cursor: pointer;
    }
    .vivamos-footer-contact:hover,
    .vivamos-footer-contact:focus-visible {
      background: #fff;
      border-color: #fff;
      outline: 2px solid rgba(255,255,255,.72);
      outline-offset: 2px;
    }
    .vivamos-footer [data-app-version] {
      white-space: nowrap;
      color: rgba(255,255,255,.76) !important;
    }

    .vivamos-contact-dialog {
      width: min(610px, calc(100% - 1.5rem));
      max-height: min(90vh, 820px);
      padding: 0;
      border: 0;
      border-radius: 1.4rem;
      background: transparent;
      color: #17342f;
      box-shadow: 0 30px 100px rgba(6,35,31,.34);
    }
    .vivamos-contact-dialog::backdrop {
      background: rgba(7,31,28,.64);
      backdrop-filter: blur(4px);
    }
    .vivamos-contact-panel {
      position: relative;
      overflow: auto;
      max-height: min(90vh, 820px);
      padding: clamp(1.25rem, 4vw, 2rem);
      border: 1px solid rgba(23,79,70,.14);
      border-radius: 1.4rem;
      background: #fffdf9;
    }
    .vivamos-contact-close {
      position: absolute;
      top: .85rem;
      right: .85rem;
      width: 2.45rem;
      height: 2.45rem;
      border: 1px solid #d7e2de;
      border-radius: 999px;
      background: #fff;
      color: #174f46;
      font: 700 1.45rem/1 system-ui;
      cursor: pointer;
    }
    .vivamos-contact-eyebrow {
      margin: 0 0 .4rem;
      color: #a9562f;
      font-size: .75rem;
      font-weight: 850;
      letter-spacing: .1em;
      text-transform: uppercase;
    }
    .vivamos-contact-panel h2 {
      margin: 0 3rem .6rem 0;
      color: #103c36;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: clamp(1.65rem, 5vw, 2.2rem);
      line-height: 1.08;
    }
    .vivamos-contact-intro {
      margin: 0 0 1.15rem;
      color: #61746f;
      line-height: 1.5;
    }
    .vivamos-contact-form {
      display: grid;
      gap: .85rem;
    }
    .vivamos-contact-form label {
      display: grid;
      gap: .35rem;
      color: #244b43;
      font-size: .83rem;
      font-weight: 800;
    }
    .vivamos-contact-form input,
    .vivamos-contact-form textarea {
      width: 100%;
      padding: .72rem .78rem;
      border: 1px solid #cbd9d5;
      border-radius: .75rem;
      background: #fff;
      color: #17342f;
      font: 500 .92rem/1.4 Inter, system-ui, sans-serif;
      resize: vertical;
    }
    .vivamos-contact-form input:focus,
    .vivamos-contact-form textarea:focus {
      outline: 3px solid rgba(21,89,79,.14);
      border-color: #15594f;
    }
    .vivamos-contact-honey {
      position: absolute !important;
      left: -10000px !important;
      width: 1px !important;
      height: 1px !important;
      opacity: 0 !important;
      pointer-events: none !important;
    }
    .vivamos-contact-privacy,
    .vivamos-contact-status {
      margin: 0;
      color: #6b7d78;
      font-size: .78rem;
      line-height: 1.45;
    }
    .vivamos-contact-status { min-height: 1.2em; font-weight: 750; }
    .vivamos-contact-status.is-success { color: #17604a; }
    .vivamos-contact-status.is-error { color: #a33e2d; }
    .vivamos-contact-actions {
      display: flex;
      justify-content: flex-end;
      gap: .55rem;
      margin-top: .15rem;
    }
    .vivamos-contact-actions button {
      min-height: 2.55rem;
      padding: .62rem .9rem;
      border-radius: .78rem;
      font: inherit;
      font-weight: 850;
      cursor: pointer;
    }
    .vivamos-contact-cancel {
      border: 1px solid #c8d7d2;
      background: #fff;
      color: #174f46;
    }
    .vivamos-contact-submit {
      border: 1px solid #15594f;
      background: #15594f;
      color: #fff;
    }
    .vivamos-contact-submit:disabled { opacity: .6; cursor: wait; }

    @media (max-width: 900px) {
      .vivamos-footer {
        grid-template-columns: 1fr auto;
        align-items: start;
        gap: .6rem .8rem;
      }
      .vivamos-footer-identity,
      .vivamos-footer-credit,
      .vivamos-footer-contact { grid-column: 1; }
      .vivamos-footer-contact { width: max-content; }
      .vivamos-footer [data-app-version] {
        grid-column: 2;
        grid-row: 1;
      }
    }
    @media (max-width: 560px) {
      .vivamos-footer { width: calc(100% - 1.4rem); }
      .vivamos-footer-identity {
        align-items: flex-start;
        flex-direction: column;
        gap: .15rem;
        white-space: normal;
      }
      .vivamos-contact-actions { flex-direction: column-reverse; }
      .vivamos-contact-actions button { width: 100%; }
    }
  `;
  document.head.append(style);
}
