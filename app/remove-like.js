const LIKE_STORAGE_KEYS = [
  "vivamos-global-like-token-v1",
  "vivamos-global-liked-v1",
  "vivamos-global-like-pending-v1",
];

function removeLikeControls() {
  const likes = [...document.querySelectorAll(".source-like-button")];
  for (const like of likes) {
    const parent = like.parentElement;
    like.remove();
    // participation-footer.js expects a marker while moving the comments
    // action into the shared action strip. Keep that marker invisible, but do
    // not select it again here or the MutationObserver would loop forever.
    if (parent && !parent.querySelector("[data-community-like]")) {
      const marker = document.createElement("span");
      marker.dataset.communityLike = "";
      marker.hidden = true;
      marker.setAttribute("aria-hidden", "true");
      parent.append(marker);
    }
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
