export const SUPPORT_VIVAMOS = Object.freeze({
  enabled: true,
  label: "❤️ Apoya ¡Vivamos!",
  placement: "footer-near-sources",
  methods: Object.freeze([
    Object.freeze({
      id: "paypal",
      audience: "Todos",
      provider: "PayPal",
      url: "https://www.paypal.com/ncp/payment/MMR5A78JMY5VL",
      enabled: true,
    }),
  ]),
});

export function getEnabledSupportMethods(config = SUPPORT_VIVAMOS) {
  if (!config?.enabled) return [];
  return (config.methods || []).filter(
    (method) => method?.enabled && /^https:\/\//i.test(String(method?.url || "")),
  );
}
