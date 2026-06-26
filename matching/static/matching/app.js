document.addEventListener("click", async (event) => {
  const trigger = event.target.closest("[data-copy-trigger]");
  if (!trigger) return;
  const panel = trigger.closest("div");
  const source = panel ? panel.querySelector("[data-copy-text]") : null;
  if (!source) return;
  const text = source.innerText.trim();
  try {
    await navigator.clipboard.writeText(text);
    const original = trigger.innerText;
    trigger.innerText = "Copied";
    setTimeout(() => {
      trigger.innerText = original;
    }, 1400);
  } catch {
    trigger.innerText = "Select text";
  }
});
