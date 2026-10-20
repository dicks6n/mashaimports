/* Masha Imports live chat. One class drives the customer widget, the customer
   chat page and the staff inbox; they differ only in endpoints. Messages are
   rendered with textContent, so nothing a user types is ever run as HTML. */
(() => {
  const csrf = () => (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || "";
  const fmtTime = (iso) => {
    const d = new Date(iso), now = new Date();
    const t = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return d.toDateString() === now.toDateString() ? t : d.toLocaleDateString([], { month: "short", day: "numeric" }) + " · " + t;
  };

  class Chat {
    constructor(root) {
      this.root = root;
      this.list = root.querySelector("[data-chat-list]");
      this.form = root.querySelector("[data-chat-form]");
      this.input = root.querySelector("[data-chat-input]");
      this.file = root.querySelector("[data-chat-file]");
      this.fileLabel = root.querySelector("[data-chat-file-name]");
      this.error = root.querySelector("[data-chat-error]");
      this.urls = { list: root.dataset.listUrl, send: root.dataset.sendUrl };
      this.viewerIsStaff = root.dataset.viewer === "staff";
      this.lastId = 0;
      this.timer = null;
      this.busy = false;
      this.form.addEventListener("submit", (e) => { e.preventDefault(); this.send(); });
      this.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.send(); }
      });
      this.input.addEventListener("input", () => {
        this.input.style.height = "auto"; this.input.style.height = Math.min(140, this.input.scrollHeight) + "px";
      });
      if (this.file) this.file.addEventListener("change", () => {
        this.fileLabel.textContent = this.file.files[0] ? "📎 " + this.file.files[0].name : "";
      });
    }

    start(interval = 3500) { this.stop(); this.poll(true); this.timer = setInterval(() => this.poll(true), interval); }
    stop() { clearInterval(this.timer); this.timer = null; }

    async poll(seen = false) {
      if (this.busy) return;
      this.busy = true;
      try {
        const url = `${this.urls.list}?after=${this.lastId}${seen ? "&seen=1" : ""}`;
        const res = await fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" });
        if (res.ok) {
          const data = await res.json();
          (data.messages || []).forEach((m) => this.render(m));
          this.root.dispatchEvent(new CustomEvent("chat:polled", { detail: data }));
        }
      } catch (_) { /* offline: try again next tick */ }
      this.busy = false;
    }

    render(m) {
      if (m.id <= this.lastId) return;
      this.lastId = m.id;
      const empty = this.list.querySelector("[data-chat-empty]");
      if (empty) empty.remove();
      const mine = this.viewerIsStaff ? m.from_staff : !m.from_staff;
      const row = document.createElement("div");
      row.className = "chat-msg " + (mine ? "mine" : "theirs");
      const bubble = document.createElement("div");
      bubble.className = "chat-bubble";
      if (!mine) {
        const who = document.createElement("div");
        who.className = "chat-who";
        who.textContent = m.from_staff ? (m.sender ? `${m.sender} · Masha Imports` : "Masha Imports") : m.sender;
        bubble.appendChild(who);
      }
      if (m.body) {
        const p = document.createElement("div");
        p.className = "chat-text";
        p.textContent = m.body;
        bubble.appendChild(p);
      }
      if (m.attachment) {
        const a = document.createElement("a");
        a.href = m.attachment; a.target = "_blank"; a.rel = "noopener";
        if (m.is_image) {
          const img = document.createElement("img"); img.src = m.attachment; img.alt = "attachment"; img.loading = "lazy";
          a.appendChild(img); a.className = "chat-img";
        } else { a.textContent = "📎 " + m.attachment_name; a.className = "chat-file"; }
        bubble.appendChild(a);
      }
      const time = document.createElement("div");
      time.className = "chat-time"; time.textContent = fmtTime(m.time);
      bubble.appendChild(time);
      row.appendChild(bubble);
      const nearBottom = this.list.scrollTop + this.list.clientHeight >= this.list.scrollHeight - 80;
      this.list.appendChild(row);
      if (nearBottom || mine) this.list.scrollTop = this.list.scrollHeight;
    }

    async send() {
      const body = this.input.value.trim();
      const hasFile = this.file && this.file.files.length;
      if (!body && !hasFile) return;
      const fd = new FormData();
      fd.append("body", body);
      fd.append("page", location.pathname);
      if (hasFile) fd.append("attachment", this.file.files[0]);
      const btn = this.form.querySelector("button[type=submit]");
      btn.disabled = true; this.showError("");
      try {
        const res = await fetch(this.urls.send, { method: "POST", body: fd, headers: { "X-CSRFToken": csrf() }, credentials: "same-origin" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { this.showError(data.error || "Message not sent. Please try again."); return; }
        this.input.value = ""; this.input.style.height = "auto";
        if (this.file) { this.file.value = ""; this.fileLabel.textContent = ""; }
        this.render(data.message);
      } catch (_) {
        this.showError("You seem to be offline. Message not sent.");
      } finally { btn.disabled = false; this.input.focus(); }
    }

    showError(text) { if (this.error) { this.error.textContent = text; this.error.hidden = !text; } }
  }
  window.MashaChat = Chat;

  // ---- Customer floating widget ---------------------------------------------
  const widget = document.querySelector("[data-chat-widget]");
  if (widget) {
    const toggle = widget.querySelector("[data-chat-toggle]");
    const panel = widget.querySelector("[data-chat-panel]");
    const badge = widget.querySelector("[data-chat-badge]");
    const root = widget.querySelector("[data-chat]");
    const chat = root ? new Chat(root) : null;
    let bgTimer = null;
    const setBadge = (n) => { if (badge) { badge.textContent = n; badge.hidden = !n; } };
    const open = () => {
      widget.classList.add("open"); panel.hidden = false; toggle.setAttribute("aria-expanded", "true");
      if (chat) { clearInterval(bgTimer); chat.start(3500); setBadge(0); setTimeout(() => chat.input.focus(), 250); }
      try { sessionStorage.setItem("chat-open", "1"); } catch (_) {}
    };
    const close = () => {
      widget.classList.remove("open"); toggle.setAttribute("aria-expanded", "false");
      setTimeout(() => { if (!widget.classList.contains("open")) panel.hidden = true; }, 300);
      if (chat) { chat.stop(); bgTimer = setInterval(() => backgroundCheck(), 20000); }
      try { sessionStorage.removeItem("chat-open"); } catch (_) {}
    };
    const backgroundCheck = async () => {
      if (!chat) return;
      try {
        const res = await fetch(`${chat.urls.list}?after=${chat.lastId || 999999999}`, { credentials: "same-origin" });
        if (res.ok) setBadge((await res.json()).unread || 0);
      } catch (_) {}
    };
    toggle.addEventListener("click", () => (widget.classList.contains("open") ? close() : open()));
    widget.querySelectorAll("[data-chat-close]").forEach((b) => b.addEventListener("click", close));
    document.querySelectorAll("[data-open-chat]").forEach((b) => b.addEventListener("click", (e) => {
      e.preventDefault(); open();
      if (chat && b.dataset.openChat) { chat.input.value = b.dataset.openChat; }
    }));
    if (chat) bgTimer = setInterval(backgroundCheck, 20000);
    let wasOpen = false;
    try { wasOpen = sessionStorage.getItem("chat-open") === "1"; } catch (_) {}
    if (wasOpen) open();
  }

  // ---- Full-page chats (customer page and staff inbox) ----------------------
  document.querySelectorAll("[data-chat][data-autostart]").forEach((root) => {
    const chat = new Chat(root);
    chat.start(+root.dataset.autostart || 3000);
  });
})();
