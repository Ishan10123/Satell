(() => {
  const root = document.documentElement;
  const shell = document.querySelector("[data-app-shell]");
  const themeButtons = document.querySelectorAll("[data-theme-toggle]");
  const themeLabel = document.querySelector("[data-theme-label]");

  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    if (themeLabel) themeLabel.textContent = theme === "dark" ? "Light appearance" : "Dark appearance";
    themeButtons.forEach((button) => {
      button.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} appearance`);
    });
  };

  const preferredTheme = ["light", "dark", "system"].includes(root.dataset.theme) ? root.dataset.theme : "system";
  const systemTheme = window.matchMedia?.("(prefers-color-scheme: dark)");
  const resolveTheme = () => preferredTheme === "system" && systemTheme ? (systemTheme.matches ? "dark" : "light") : preferredTheme;
  applyTheme(resolveTheme());
  systemTheme?.addEventListener?.("change", () => { if (preferredTheme === "system") applyTheme(resolveTheme()); });
  themeButtons.forEach((button) => button.addEventListener("click", () => {
    applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
  }));

  let activeDropdown = null;
  const menuItems = (panel) => [...panel.querySelectorAll('[role="menuitem"]:not(:disabled)')];
  const closeDropdown = (restoreFocus = false) => {
    if (!activeDropdown) return;
    const { trigger, panel } = activeDropdown;
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    activeDropdown = null;
    if (restoreFocus) trigger.focus();
  };
  const placeDropdown = (trigger, panel) => {
    const rect = trigger.getBoundingClientRect();
    const margin = 8;
    panel.style.position = "fixed";
    panel.style.visibility = "hidden";
    panel.style.maxHeight = `${Math.max(120, window.innerHeight - margin * 2)}px`;
    panel.style.overflowY = "auto";
    const box = panel.getBoundingClientRect();
    const maxLeft = Math.max(margin, window.innerWidth - box.width - margin);
    const maxTop = Math.max(margin, window.innerHeight - box.height - margin);
    const clamp = (value, max) => Math.max(margin, Math.min(value, max));
    const leftCandidates = [
      rect.right + 4,
      rect.left - box.width - 4,
      rect.right - box.width,
      rect.left,
    ].map((value) => clamp(value, maxLeft));
    const topCandidates = [
      rect.bottom + 4,
      rect.top - box.height - 4,
      rect.top,
      rect.bottom - box.height,
    ].map((value) => clamp(value, maxTop));
    const otherTriggers = [...document.querySelectorAll("[data-dropdown-trigger]")]
      .filter((candidate) => candidate !== trigger)
      .map((candidate) => candidate.getBoundingClientRect());
    let best = { overlap: Number.POSITIVE_INFINITY, left: leftCandidates[0], top: topCandidates[0] };
    for (const left of leftCandidates) {
      for (const top of topCandidates) {
        const overlap = otherTriggers.reduce((area, candidate) => {
          const width = Math.max(0, Math.min(left + box.width, candidate.right) - Math.max(left, candidate.left));
          const height = Math.max(0, Math.min(top + box.height, candidate.bottom) - Math.max(top, candidate.top));
          return area + width * height;
        }, 0);
        if (overlap < best.overlap) best = { overlap, left, top };
      }
    }
    panel.style.left = `${best.left}px`;
    panel.style.top = `${best.top}px`;
    panel.style.visibility = "visible";
  };
  document.querySelectorAll("[data-dropdown-trigger]").forEach((trigger) => {
    const panel = document.getElementById(trigger.getAttribute("aria-controls"));
    if (!panel) return;
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (activeDropdown?.trigger === trigger) { closeDropdown(); return; }
      closeDropdown();
      panel.hidden = false;
      document.body.append(panel);
      trigger.setAttribute("aria-expanded", "true");
      placeDropdown(trigger, panel);
      activeDropdown = { trigger, panel };
      menuItems(panel)[0]?.focus({ preventScroll: true });
    });
    panel.addEventListener("keydown", (event) => {
      const items = menuItems(panel);
      const current = items.indexOf(document.activeElement);
      let next = null;
      if (event.key === "ArrowDown") next = (current + 1) % items.length;
      if (event.key === "ArrowUp") next = (current - 1 + items.length) % items.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = items.length - 1;
      if (next !== null && items.length) { event.preventDefault(); items[next].focus(); }
    });
    panel.addEventListener("click", (event) => {
      if (event.target.closest('[role="menuitem"]')) closeDropdown();
    });
  });
  document.addEventListener("click", (event) => {
    if (activeDropdown && !activeDropdown.trigger.contains(event.target) && !activeDropdown.panel.contains(event.target)) closeDropdown();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && activeDropdown) { event.preventDefault(); closeDropdown(true); }
  });
  document.addEventListener("focusin", (event) => {
    if (activeDropdown && !activeDropdown.trigger.contains(event.target) && !activeDropdown.panel.contains(event.target)) closeDropdown();
  });
  document.addEventListener("scroll", (event) => {
    if (!activeDropdown || activeDropdown.panel.contains(event.target)) return;
    const rect = activeDropdown.trigger.getBoundingClientRect();
    const outsideViewport = rect.bottom <= 0 || rect.top >= window.innerHeight
      || rect.right <= 0 || rect.left >= window.innerWidth;
    if (outsideViewport) closeDropdown();
    else placeDropdown(activeDropdown.trigger, activeDropdown.panel);
  }, true);
  window.addEventListener("resize", () => closeDropdown());

  const menuButton = document.querySelector("[data-menu-toggle]");
  const closeMenu = () => {
    if (!shell) return;
    shell.classList.remove("menu-open");
    if (menuButton) menuButton.setAttribute("aria-expanded", "false");
  };
  if (menuButton && shell) menuButton.addEventListener("click", () => {
    const open = shell.classList.toggle("menu-open");
    menuButton.setAttribute("aria-expanded", String(open));
    if (open) shell.querySelector(".conversation-link")?.focus();
  });
  document.querySelectorAll("[data-menu-close]").forEach((element) => element.addEventListener("click", closeMenu));
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeMenu(); });

  const appendInlineMarkdown = (container, text) => {
    const token = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))/g;
    let offset = 0;
    for (const match of text.matchAll(token)) {
      if (match.index > offset) container.append(document.createTextNode(text.slice(offset, match.index)));
      const value = match[0];
      let node;
      if (value.startsWith("`")) {
        node = document.createElement("code");
        node.textContent = value.slice(1, -1);
      } else if (value.startsWith("**")) {
        node = document.createElement("strong");
        node.textContent = value.slice(2, -2);
      } else if (value.startsWith("*")) {
        node = document.createElement("em");
        node.textContent = value.slice(1, -1);
      } else {
        const link = value.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
        let url = null;
        try { if (link) url = new URL(link[2]); } catch (_) { url = null; }
        if (!url || !["https:", "http:"].includes(url.protocol)) {
          container.append(document.createTextNode(value));
          offset = match.index + value.length;
          continue;
        }
        node = document.createElement("a");
        node.href = url.href;
        node.rel = "noopener noreferrer";
        node.target = "_blank";
        node.textContent = link[1];
      }
      container.append(node);
      offset = match.index + value.length;
    }
    if (offset < text.length) container.append(document.createTextNode(text.slice(offset)));
  };

  const copyText = async (text) => {
    if (!text) return false;
    if (navigator.clipboard?.writeText) {
      try { await navigator.clipboard.writeText(text); return true; } catch (_) { }
    }
    const field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_) { copied = false; }
    field.remove();
    return copied;
  };

  const bindCopyControl = (button, value, copiedLabel) => button.addEventListener("click", async () => {
    const copied = await copyText(value);
    button.textContent = copied ? copiedLabel : "Copy unavailable";
    if (copied) window.setTimeout(() => { button.textContent = button.dataset.defaultLabel; }, 1600);
  });

  const renderMarkdown = (container) => {
    const source = container.textContent || "";
    const fragment = document.createDocumentFragment();
    const lines = source.replace(/\r\n?/g, "\n").split("\n");
    let paragraph = [];
    let list = null;
    let codeLines = null;
    const flushParagraph = () => {
      if (!paragraph.length) return;
      const p = document.createElement("p");
      appendInlineMarkdown(p, paragraph.join(" "));
      fragment.append(p);
      paragraph = [];
    };
    const flushList = () => { if (list) fragment.append(list); list = null; };
    for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
      const line = lines[lineIndex];
      if (line.trimStart().startsWith("```")) {
        flushParagraph(); flushList();
        if (codeLines) {
          const wrapper = document.createElement("div");
          wrapper.className = "markdown-code-block";
          const pre = document.createElement("pre");
          const code = document.createElement("code");
          code.textContent = codeLines.join("\n");
          const copyCode = document.createElement("button");
          copyCode.type = "button";
          copyCode.className = "copy-code";
          copyCode.dataset.copyCode = "true";
          copyCode.dataset.defaultLabel = "Copy code";
          copyCode.textContent = copyCode.dataset.defaultLabel;
          pre.append(code); wrapper.append(copyCode, pre); fragment.append(wrapper);
          bindCopyControl(copyCode, code.textContent, "Copied");
          codeLines = null;
        } else codeLines = [];
        continue;
      }
      if (codeLines) { codeLines.push(line); continue; }
      const tableSeparator = lines[lineIndex + 1] || "";
      if (line.includes("|") && /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(tableSeparator)) {
        flushParagraph(); flushList();
        const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
        const wrapper = document.createElement("div"); wrapper.className = "markdown-table-wrap";
        const table = document.createElement("table"); table.className = "markdown-table";
        const head = document.createElement("thead"); const headRow = document.createElement("tr");
        cells(line).forEach((value) => { const th = document.createElement("th"); appendInlineMarkdown(th, value); headRow.append(th); });
        head.append(headRow); table.append(head);
        const body = document.createElement("tbody");
        lineIndex += 2;
        while (lineIndex < lines.length && lines[lineIndex].includes("|") && lines[lineIndex].trim()) {
          const row = document.createElement("tr");
          cells(lines[lineIndex]).forEach((value) => { const td = document.createElement("td"); appendInlineMarkdown(td, value); row.append(td); });
          body.append(row); lineIndex += 1;
        }
        table.append(body); wrapper.append(table); fragment.append(wrapper); lineIndex -= 1;
        continue;
      }
      const item = line.match(/^\s*[-*+]\s+(.+)$/);
      if (item) {
        flushParagraph();
        if (!list || list.tagName !== "UL") { flushList(); list = document.createElement("ul"); }
        const li = document.createElement("li"); appendInlineMarkdown(li, item[1]); list.append(li);
      } else if (/^\s*\d+[.)]\s+/.test(line)) {
        flushParagraph();
        if (!list || list.tagName !== "OL") { flushList(); list = document.createElement("ol"); }
        const li = document.createElement("li"); appendInlineMarkdown(li, line.replace(/^\s*\d+[.)]\s+/, "")); list.append(li);
      } else if (/^\s*#{1,6}\s+/.test(line)) {
        flushParagraph(); flushList();
        const heading = line.match(/^\s*(#{1,6})\s+(.+)$/);
        const h = document.createElement(`h${heading[1].length}`);
        appendInlineMarkdown(h, heading[2]); fragment.append(h);
      } else if (!line.trim()) { flushParagraph(); flushList(); }
      else { flushList(); paragraph.push(line.trim()); }
    }
    if (codeLines) {
      const wrapper = document.createElement("div");
      wrapper.className = "markdown-code-block";
      const pre = document.createElement("pre"); const code = document.createElement("code");
      code.textContent = codeLines.join("\n");
      const copyCode = document.createElement("button");
      copyCode.type = "button";
      copyCode.className = "copy-code";
      copyCode.dataset.copyCode = "true";
      copyCode.dataset.defaultLabel = "Copy code";
      copyCode.textContent = copyCode.dataset.defaultLabel;
      pre.append(code); wrapper.append(copyCode, pre); fragment.append(wrapper);
      bindCopyControl(copyCode, code.textContent, "Copied");
    }
    flushParagraph(); flushList();
    container.replaceChildren(fragment);
  };
  document.querySelectorAll("[data-markdown-content]").forEach(renderMarkdown);

  document.querySelectorAll("[data-copy-response]").forEach((button) => button.addEventListener("click", async () => {
    const content = button.parentElement?.querySelector("[data-markdown-content]");
    if (!content) { button.textContent = "Copy unavailable"; return; }
    const copy = content.cloneNode(true);
    copy.querySelectorAll("[data-copy-code]").forEach((control) => control.remove());
    const copied = await copyText(copy.innerText || copy.textContent || "");
    button.textContent = copied ? "Copied" : "Copy unavailable";
    if (copied) window.setTimeout(() => { button.textContent = "Copy response"; }, 1600);
  }));

  document.querySelectorAll("[data-copy-citation]").forEach((button) => {
    button.dataset.defaultLabel = "Copy citation";
    bindCopyControl(button, button.dataset.copyCitation, "Copied");
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm || "Continue?")) event.preventDefault();
  }));

  const form = document.querySelector("[data-message-form]");
  const input = document.querySelector("[data-message-input]");
  const sendButton = document.querySelector("[data-send-button]");
  const sendLabel = document.querySelector("[data-send-label]");
  const charCount = document.querySelector("[data-char-count]");
  if (form && input && sendButton) {
    const maxChars = Number(input.dataset.maxChars || charCount?.dataset.maxChars || 5000);
    // HTML maxlength measures UTF-16 code units. Permit the largest representation
    // of maxChars Unicode code points, then validate/count code points below.
    input.maxLength = maxChars * 2;
    const updateComposer = () => {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
      const count = Array.from(input.value).length;
      if (charCount) charCount.textContent = `${count.toLocaleString()} / ${maxChars.toLocaleString()}`;
      input.setCustomValidity(!input.value.trim() ? "Enter a message before sending."
        : count > maxChars ? `Keep your message within ${maxChars.toLocaleString()} characters.` : "");
    };
    input.addEventListener("input", updateComposer);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        if (form.reportValidity()) form.requestSubmit();
      }
    });
    form.addEventListener("submit", (event) => {
      if (!form.reportValidity()) { event.preventDefault(); return; }
      if (sendButton.disabled) { event.preventDefault(); return; }
      sendButton.disabled = true;
      sendButton.setAttribute("aria-busy", "true");
      if (sendLabel) sendLabel.textContent = "Sending…";
      input.readOnly = true;
    });
    updateComposer();
  }

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const field = button.closest(".password-field")?.querySelector("input");
    const label = button.querySelector("[data-password-toggle-label]");
    if (!field) return;
    button.addEventListener("click", () => {
      const visible = field.type === "password";
      field.type = visible ? "text" : "password";
      button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
      button.setAttribute("aria-pressed", String(visible));
      if (label) label.textContent = visible ? "Hide" : "Show";
      field.focus();
    });
  });

  const renameDialog = document.querySelector("[data-rename-dialog]");
  const renameForm = document.querySelector("[data-rename-form]");
  const renameInput = document.querySelector("#rename-title");
  document.querySelectorAll("[data-rename-conversation]").forEach((button) => button.addEventListener("click", () => {
    closeDropdown();
    if (!renameDialog || !renameForm || !renameInput) return;
    renameForm.action = button.dataset.url;
    renameInput.value = button.dataset.title || "";
    renameDialog.showModal();
    renameInput.focus(); renameInput.select();
  }));
  document.querySelectorAll("[data-dialog-close]").forEach((button) => button.addEventListener("click", () => renameDialog?.close()));
  renameDialog?.addEventListener("click", (event) => { if (event.target === renameDialog) renameDialog.close(); });

  document.querySelectorAll("[data-copy-share]").forEach((button) => button.addEventListener("click", async () => {
    const input = document.querySelector("[data-share-link]");
    const copied = await copyText(input?.value || "");
    button.textContent = copied ? "Copied" : "Copy unavailable";
    if (copied) window.setTimeout(() => { button.textContent = "Copy link"; }, 1600);
  }));
})();
