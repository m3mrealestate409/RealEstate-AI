/*!
 * PropX Estate — embeddable chat widget.
 * Add to any site (e.g. WordPress) with:
 *   <script src="http://localhost:8001/static/widget.js"
 *           data-api-url="http://localhost:8001"
 *           data-api-key="px_your_key"
 *           data-title="Ask about our projects"
 *           data-accent="#6b46ff"></script>
 * NOTE: putting the API key in the page is fine for LOCAL testing; in production
 * point data-api-url at a small server-side proxy that adds the key.
 */
(function () {
  var s = document.currentScript || (function () {
    var all = document.getElementsByTagName("script");
    return all[all.length - 1];
  })();
  var API_URL = (s && s.getAttribute("data-api-url")) || "http://localhost:8001";
  var API_KEY = (s && s.getAttribute("data-api-key")) || "";
  var TITLE = (s && s.getAttribute("data-title")) || "Ask about our projects";
  var ACCENT = (s && s.getAttribute("data-accent")) || "#6b46ff";
  // Persist the session id for the whole browsing session so the conversation
  // continues across page navigations (per-session memory).
  var SESSION = (function () {
    try {
      var s = sessionStorage.getItem("pxSession");
      if (!s) { s = "web-" + Math.random().toString(36).slice(2, 10); sessionStorage.setItem("pxSession", s); }
      return s;
    } catch (e) { return "web-" + Math.random().toString(36).slice(2, 10); }
  })();
  var GREETING = "Hi! Ask me about any project — price, payment plan, amenities, or compare two.";
  if (window.__propxWidgetLoaded) return;
  window.__propxWidgetLoaded = true;

  var css =
    ".px-btn{position:fixed;right:22px;bottom:22px;width:58px;height:58px;border-radius:50%;" +
    "background:" + ACCENT + ";color:#fff;border:none;cursor:pointer;font-size:26px;box-shadow:0 8px 24px rgba(0,0,0,.22);" +
    "z-index:2147483000;display:flex;align-items:center;justify-content:center;transition:transform .15s}" +
    ".px-btn:hover{transform:scale(1.06)}" +
    ".px-panel{position:fixed;right:22px;bottom:92px;width:370px;max-width:calc(100vw - 44px);height:540px;" +
    "max-height:calc(100vh - 130px);background:#fff;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.28);" +
    "z-index:2147483000;display:none;flex-direction:column;overflow:hidden;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}" +
    ".px-panel.open{display:flex}" +
    ".px-head{background:" + ACCENT + ";color:#fff;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:8px}" +
    ".px-head-id{display:flex;align-items:center;gap:10px;min-width:0}" +
    ".px-avatar{width:40px;height:40px;border-radius:50%;flex-shrink:0;background:rgba(255,255,255,.22) center/cover no-repeat;" +
    "display:flex;align-items:center;justify-content:center;font-weight:700;font-size:17px;color:#fff;box-shadow:0 0 0 2px rgba(255,255,255,.35)}" +
    ".px-head-txt{min-width:0}" +
    ".px-name{font-size:15px;font-weight:700;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
    ".px-status{font-size:11px;font-weight:500;opacity:.9;display:flex;align-items:center;gap:5px;margin-top:1px}" +
    ".px-status i{width:7px;height:7px;border-radius:50%;background:#4ade80;display:inline-block;box-shadow:0 0 0 2px rgba(74,222,128,.35)}" +
    ".px-x{cursor:pointer;font-size:22px;line-height:1;opacity:.85;padding:0 2px}.px-x:hover{opacity:1}" +
    ".px-msgs{flex:1;overflow-y:auto;padding:14px;background:#f6f7fb;display:flex;flex-direction:column;gap:10px}" +
    ".px-bubble{max-width:82%;padding:10px 13px;border-radius:14px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}" +
    ".px-user{align-self:flex-end;background:" + ACCENT + ";color:#fff;border-bottom-right-radius:4px}" +
    ".px-bot{align-self:flex-start;background:#fff;color:#1a1a1a;border:1px solid #e6e8ef;border-bottom-left-radius:4px}" +
    ".px-bot strong{font-weight:700}" +
    ".px-foot{display:flex;gap:8px;padding:10px;border-top:1px solid #eee;background:#fff}" +
    ".px-foot input{flex:1;padding:10px 12px;border:1px solid #d7dae5;border-radius:10px;font-size:14px;outline:none}" +
    ".px-foot button{background:" + ACCENT + ";color:#fff;border:none;border-radius:10px;padding:0 16px;cursor:pointer;font-weight:600}" +
    ".px-foot button:disabled{opacity:.5;cursor:default}" +
    ".px-dots{display:inline-block}.px-dots i{display:inline-block;width:6px;height:6px;margin:0 1px;border-radius:50%;background:#b3b8c8;animation:pxb 1s infinite}" +
    ".px-dots i:nth-child(2){animation-delay:.2s}.px-dots i:nth-child(3){animation-delay:.4s}" +
    "@keyframes pxb{0%,60%,100%{opacity:.3}30%{opacity:1}}" +
    // Quick-reply chips.
    ".px-chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 2px 2px}" +
    ".px-chip{border:1px solid " + ACCENT + ";color:" + ACCENT + ";background:#fff;border-radius:15px;" +
    "padding:6px 12px;font-size:12.5px;font-weight:600;cursor:pointer;transition:.12s;font-family:inherit}" +
    ".px-chip:hover{background:" + ACCENT + ";color:#fff}" +
    ".px-teaser{position:fixed;right:24px;bottom:92px;max-width:250px;background:#fff;color:#1a1a1a;" +
    "border:1px solid #e6e8ef;border-radius:14px;border-bottom-right-radius:4px;box-shadow:0 10px 30px rgba(0,0,0,.18);" +
    "padding:12px 30px 12px 14px;font-size:14px;line-height:1.45;z-index:2147482999;cursor:pointer;display:none}" +
    ".px-teaser.show{display:block;animation:pxpop .2s}" +
    ".px-teaser-x{position:absolute;top:5px;right:9px;font-size:16px;color:#aaa;cursor:pointer;line-height:1}" +
    "@keyframes pxpop{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}" +
    // Header actions + premium callback button + lead form.
    ".px-head-actions{display:flex;align-items:center;gap:8px;flex-shrink:0}" +
    ".px-cb{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.18);border:none;color:#fff;" +
    "border-radius:20px;padding:7px 12px 7px 11px;font-size:12.5px;font-weight:600;cursor:pointer;white-space:nowrap;" +
    "font-family:inherit;transition:background .15s,transform .15s;backdrop-filter:blur(2px)}" +
    ".px-cb:hover{background:rgba(255,255,255,.3);transform:translateY(-1px)}" +
    ".px-cb-ico{width:15px;height:15px;flex-shrink:0;background:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='%23fff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z'/%3E%3C/svg%3E\") center/15px no-repeat}" +
    ".px-lead{display:none;flex-direction:column;gap:9px;padding:14px;background:#fff;border-top:1px solid #eee}" +
    ".px-lead.show{display:flex}" +
    ".px-lead h4{margin:0;font-size:15px;color:#1a1a1a}" +
    ".px-lead p{margin:0;font-size:12.5px;color:#6b7280}" +
    ".px-lead input,.px-lead textarea{padding:9px 11px;border:1px solid #d7dae5;border-radius:9px;font-size:14px;outline:none;font-family:inherit}" +
    ".px-lead textarea{resize:vertical;min-height:44px}" +
    ".px-lead-row{display:flex;gap:8px}" +
    ".px-lead-row button{flex:1;border:none;border-radius:9px;padding:10px;cursor:pointer;font-weight:600;font-size:14px}" +
    ".px-lead-send{background:" + ACCENT + ";color:#fff}" +
    ".px-lead-send:disabled{opacity:.5;cursor:default}" +
    ".px-lead-cancel{background:#eef0f6;color:#444}" +
    ".px-lead-ok{font-size:13px;color:#0a7d34}.px-lead-err{font-size:13px;color:#c0392b}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  // Icons as CSS background data-URIs (NOT child <svg>) so a host theme's own
  // svg rules can't override/hide them.
  var BG_CHAT = ACCENT + " url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='%23fff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'/%3E%3C/svg%3E\") center/26px no-repeat";
  var BG_CLOSE = ACCENT + " url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%23fff' stroke-width='2.4' stroke-linecap='round'%3E%3Cline x1='18' y1='6' x2='6' y2='18'/%3E%3Cline x1='6' y1='6' x2='18' y2='18'/%3E%3C/svg%3E\") center/22px no-repeat";
  var btn = document.createElement("button");
  btn.className = "px-btn"; btn.title = TITLE; btn.style.background = BG_CHAT;
  var panel = document.createElement("div"); panel.className = "px-panel";
  panel.innerHTML =
    '<div class="px-head">' +
      '<div class="px-head-id">' +
        '<div class="px-avatar" data-avatar><span data-initial></span></div>' +
        '<div class="px-head-txt">' +
          '<div class="px-name" data-name>' + esc(TITLE) + '</div>' +
          '<div class="px-status"><i></i>Online</div>' +
        '</div>' +
      '</div>' +
      '<div class="px-head-actions">' +
        '<button class="px-cb" data-cb title="Request a callback"><span class="px-cb-ico"></span>Callback</button>' +
        '<span class="px-x" data-close>&times;</span>' +
      '</div>' +
    '</div>' +
    '<div class="px-msgs"></div>' +
    '<div class="px-lead">' +
      '<h4>Request a callback</h4>' +
      '<p>Leave your details and our team will reach out.</p>' +
      '<input class="px-lead-name" placeholder="Your name" />' +
      '<input class="px-lead-phone" placeholder="Phone / WhatsApp number*" />' +
      '<textarea class="px-lead-msg" placeholder="What are you looking for? (optional)"></textarea>' +
      '<div class="px-lead-row"><button class="px-lead-cancel" data-lead-cancel>Cancel</button>' +
      '<button class="px-lead-send" data-lead-send>Send</button></div>' +
      '<div class="px-lead-status"></div>' +
    '</div>' +
    '<div class="px-foot"><input placeholder="Type your question…" /><button>Send</button></div>';
  var teaser = document.createElement("div");
  teaser.className = "px-teaser";
  teaser.innerHTML = '<span class="px-teaser-x">&times;</span><span class="px-teaser-txt"></span>';
  document.body.appendChild(btn); document.body.appendChild(panel); document.body.appendChild(teaser);

  var msgs = panel.querySelector(".px-msgs");
  // Scope to the footer — the lead form also has inputs/buttons that appear
  // earlier in the DOM, so an unscoped querySelector would grab the wrong one.
  var input = panel.querySelector(".px-foot input");
  var sendBtn = panel.querySelector(".px-foot button");
  var busy = false;

  btn.onclick = function () {
    teaser.classList.remove("show");
    var open = panel.classList.toggle("open");
    btn.style.background = open ? BG_CLOSE : BG_CHAT;
    if (open) {
      if (!msgs.dataset.greeted) { addBot(GREETING); msgs.dataset.greeted = "1"; }
      input.focus();
    }
  };
  panel.querySelector("[data-close]").onclick = function () { panel.classList.remove("open"); btn.style.background = BG_CHAT; };
  teaser.querySelector(".px-teaser-txt").onclick = function () { teaser.classList.remove("show"); btn.onclick(); };
  teaser.querySelector(".px-teaser-x").onclick = function (e) { e.stopPropagation(); teaser.classList.remove("show"); try { sessionStorage.setItem("pxTeaser", "0"); } catch (x) {} };
  sendBtn.onclick = send;
  input.addEventListener("keydown", function (e) { if (e.key === "Enter") send(); });

  // ---- Lead capture (callback) form ----------------------------------------
  var lead = panel.querySelector(".px-lead");
  var leadStatus = panel.querySelector(".px-lead-status");
  function openLeadForm() {
    if (leadStatus.classList.contains("px-lead-ok")) return; // already submitted this round
    leadStatus.textContent = ""; leadStatus.className = "px-lead-status";
    lead.classList.add("show"); scroll();
    panel.querySelector(".px-lead-name").focus();
  }
  panel.querySelector("[data-cb]").onclick = openLeadForm;
  panel.querySelector("[data-lead-cancel]").onclick = function () { lead.classList.remove("show"); };
  panel.querySelector("[data-lead-send]").onclick = submitLead;

  function submitLead() {
    var name = panel.querySelector(".px-lead-name").value.trim();
    var phone = panel.querySelector(".px-lead-phone").value.trim();
    var message = panel.querySelector(".px-lead-msg").value.trim();
    if (!phone) {
      leadStatus.textContent = "Please add a phone number so we can reach you.";
      leadStatus.className = "px-lead-status px-lead-err"; return;
    }
    var sendLeadBtn = panel.querySelector("[data-lead-send]");
    sendLeadBtn.disabled = true; leadStatus.textContent = "Sending…"; leadStatus.className = "px-lead-status";
    fetch(API_URL + "/v1/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
      body: JSON.stringify({
        name: name, phone: phone, message: message,
        source: "widget", session_id: SESSION, page_url: location.href,
      }),
    })
      .then(function (r) {
        if (r.status === 429) throw new Error("Too many requests — please wait a moment and try again.");
        if (!r.ok) throw new Error(r.status === 401 ? "Auth failed — check the API key." : "Could not send");
        return r.json();
      })
      .then(function () {
        leadStatus.textContent = "✓ Thanks! Our team will call you shortly.";
        leadStatus.className = "px-lead-status px-lead-ok";
        panel.querySelector(".px-lead-name").value = "";
        panel.querySelector(".px-lead-phone").value = "";
        panel.querySelector(".px-lead-msg").value = "";
        setTimeout(function () { lead.classList.remove("show"); }, 2000);
      })
      .catch(function (e) { leadStatus.textContent = e.message || "Something went wrong."; leadStatus.className = "px-lead-status px-lead-err"; })
      .finally(function () { sendLeadBtn.disabled = false; });
  }

  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function md(t) { return esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>"); }
  function addUser(t) { var d = document.createElement("div"); d.className = "px-bubble px-user"; d.textContent = t; msgs.appendChild(d); scroll(); saveHistory(); }
  function addBot(t) { var d = document.createElement("div"); d.className = "px-bubble px-bot"; d.innerHTML = md(t); msgs.appendChild(d); scroll(); saveHistory(); return d; }
  function addLoader() { var d = document.createElement("div"); d.className = "px-bubble px-bot"; d.innerHTML = '<span class="px-dots"><i></i><i></i><i></i></span>'; msgs.appendChild(d); scroll(); return d; }
  function scroll() { msgs.scrollTop = msgs.scrollHeight; }

  // Quick-reply chips (ephemeral — not saved to history). Shown only AFTER an
  // answer (from the engine's suggestions), never under the first greeting.
  function clearChips() { var c = msgs.querySelector(".px-chips"); if (c) c.remove(); }
  function renderChips(list) {
    clearChips();
    if (!list || !list.length) return;
    var wrap = document.createElement("div"); wrap.className = "px-chips";
    list.slice(0, 4).forEach(function (t) {
      var b = document.createElement("button"); b.className = "px-chip"; b.type = "button";
      b.textContent = t;
      b.onclick = function () { if (busy) return; input.value = t; send(); };
      wrap.appendChild(b);
    });
    msgs.appendChild(wrap); scroll();
  }

  // Cosmetic "typing" reveal (feels like streaming). Purely visual and safe:
  // the full answer is rendered by the caller FIRST, so nothing depends on this
  // finishing — if the tab is backgrounded (timers throttled) it just snaps to
  // the full text on the next tick.
  function typewriter(el, full) {
    var plain = (full || "").replace(/\*\*/g, "");
    var tokens = plain.match(/\S+\s*/g) || [];
    if (plain.length > 350 || tokens.length < 2 || document.hidden) return; // skip: long/hidden
    var i = 0, start = Date.now(); el.textContent = "";
    (function step() {
      if (i >= tokens.length || Date.now() - start > 1500) { el.innerHTML = md(full); scroll(); return; }
      el.textContent += tokens[i]; i++; scroll();
      setTimeout(step, 18);
    })();
  }

  // Persist the visible conversation for this browsing session so it survives
  // page navigations/reloads (restored when the widget loads on the next page).
  function saveHistory() {
    try {
      var items = [].slice.call(msgs.querySelectorAll(".px-bubble"))
        .filter(function (b) { return !b.querySelector(".px-dots"); })
        .map(function (b) { return { r: b.classList.contains("px-user") ? "u" : "b", h: b.innerHTML }; });
      sessionStorage.setItem("pxMsgs", JSON.stringify(items.slice(-30)));
    } catch (e) {}
  }
  function restoreHistory() {
    try {
      var items = JSON.parse(sessionStorage.getItem("pxMsgs") || "[]");
      if (!items.length) return false;
      items.forEach(function (m) {
        var d = document.createElement("div");
        d.className = "px-bubble " + (m.r === "u" ? "px-user" : "px-bot");
        d.innerHTML = m.h; msgs.appendChild(d);
      });
      scroll(); return true;
    } catch (e) { return false; }
  }
  if (restoreHistory()) msgs.dataset.greeted = "1";

  function send() {
    var q = input.value.trim();
    if (!q || busy) return;
    clearChips();
    input.value = ""; addUser(q); busy = true; sendBtn.disabled = true;
    var loader = addLoader();
    fetch(API_URL + "/v1/query", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
      body: JSON.stringify({ query: q, session_id: SESSION, format: "text" }),
    })
      .then(function (r) {
        if (r.status === 429) throw new Error("You're sending messages too quickly — please wait a moment. 🙏");
        if (!r.ok) throw new Error(r.status === 401 ? "Auth failed — check the API key." : "Request failed");
        return r.json();
      })
      .then(function (d) {
        var full = d.answer_text || "Information not available.";
        // Render the full answer + run all logic IMMEDIATELY (not gated on the
        // cosmetic typewriter, so it works even if the tab is backgrounded).
        loader.innerHTML = md(full); scroll(); saveHistory();
        // Offer relevant follow-ups as tappable chips.
        if (d.suggestions && d.suggestions.length) renderChips(d.suggestions);
        // A phone number was just auto-captured, or the visitor asked to be
        // contacted → surface the callback form at the right moment.
        if (d.suggest_callback && !d.lead_captured) openLeadForm();
        typewriter(loader, full); // cosmetic reveal, best-effort
      })
      .catch(function (e) { loader.innerHTML = esc(e.message || "Something went wrong."); saveHistory(); })
      .finally(function () { busy = false; sendBtn.disabled = false; input.focus(); });
  }

  // Load the (admin-editable) greeting and show it as a teaser next to the bubble.
  function showTeaser(text) {
    try { if (sessionStorage.getItem("pxTeaser") === "0") return; } catch (x) {}
    teaser.querySelector(".px-teaser-txt").textContent = text;
    setTimeout(function () { if (!panel.classList.contains("open")) teaser.classList.add("show"); }, 1200);
  }
  // Apply the assistant's identity (name + avatar) to the header. Falls back to
  // an initials circle when no photo is set.
  function applyIdentity(name, avatarUrl) {
    var display = (name || TITLE || "Assistant");
    var nameEl = panel.querySelector("[data-name]");
    if (name) nameEl.textContent = name;
    var av = panel.querySelector("[data-avatar]");
    var ini = panel.querySelector("[data-initial]");
    if (avatarUrl) {
      var full = /^https?:/.test(avatarUrl) ? avatarUrl : API_URL + avatarUrl;
      av.style.backgroundImage = "url('" + full + "')";
      ini.textContent = "";
    } else {
      ini.textContent = display.trim().charAt(0).toUpperCase() || "A";
    }
  }
  applyIdentity(null, null); // initials from TITLE until config loads

  fetch(API_URL + "/v1/widget/config", { headers: { "X-API-Key": API_KEY } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (c) {
      if (c) {
        if (c.greeting) GREETING = c.greeting;
        applyIdentity(c.name, c.avatar_url);
      }
      showTeaser(GREETING);
    })
    .catch(function () { showTeaser(GREETING); });
})();
