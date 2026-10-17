// Registered before the asynchronous Turnstile script can report an error.
(() => {
  function message() { return document.querySelector("[data-form-message]"); }
  window.communityVerificationError = (code) => {
    const node = message();
    if (node) {
      node.dataset.verificationError = String(code);
      node.textContent = String(code) === "110200"
        ? "El envío está temporalmente bloqueado por la configuración de seguridad del sitio. Conserva los datos y vuelve a intentarlo cuando se restablezca."
        : "No se pudo completar la verificación de seguridad. Tus datos se conservan; vuelve a intentarlo.";
    }
    return true;
  };
  window.communityVerificationReady = () => {
    const node = message();
    if (node?.dataset.verificationError) { delete node.dataset.verificationError; node.textContent = ""; }
  };
  window.communityVerificationExpired = () => {
    const node = message();
    if (node) {
      node.dataset.verificationError = "expired";
      node.textContent = "La verificación de seguridad ha caducado. Complétala de nuevo antes de enviar.";
    }
  };
})();
