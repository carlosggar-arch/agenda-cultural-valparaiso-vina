const release = Number(globalThis.__VIVAMOS_RELEASE__);
if (!Number.isInteger(release) || release < 1) {
  throw new Error("¡Vivamos!: invalid release for root WEB bootstrap");
}
await import(`./agenda.js?v=${release}`);
