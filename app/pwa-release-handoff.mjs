export function createReleaseHandoff(initiallyControlled = false) {
  let controlled = Boolean(initiallyControlled);
  let reloadStarted = false;

  return {
    controllerChanged() {
      const shouldReload = controlled && !reloadStarted;
      controlled = true;
      if (shouldReload) reloadStarted = true;
      return shouldReload;
    },
  };
}
