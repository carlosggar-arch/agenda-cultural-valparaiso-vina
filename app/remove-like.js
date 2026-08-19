const LIKE_STORAGE_KEYS = [
  "vivamos-global-like-token-v1",
  "vivamos-global-liked-v1",
  "vivamos-global-like-pending-v1",
];

function removeLikeControls() {
  for (const like of document.querySelectorAll("[data-community-like], .source-like-button")) {
    like.remove();
  }
}

for (const key of LIKE_STORAGE_KEYS) {
  try { localStorage.removeItem(key); } catch {}
}

removeLikeControls();
new MutationObserver(removeLikeControls).observe(document.documentElement, {
  childList: true,
  subtree: true,
});
