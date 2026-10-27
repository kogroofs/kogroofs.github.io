/* KOG Roofing quick-answer chat.
   Tap-to-answer only: no AI, no outside service, nothing sent anywhere.
   Answers come from KOG's posted prices and policies. To replace it later
   with an AI chat, remove the <script src="kog-chat.js"> line from the pages. */
(function () {
  "use strict";
  if (window.__kogChat) return;
  window.__kogChat = true;

  var PHONE = "+18175502339";
  var PHONE_SHOWN = "(817) 550-2339";
  var SMS = "sms:" + PHONE + "?&body=" + encodeURIComponent("Hi KOG Roofing, I found you online. ");
  var TOWN_PAGES = ["Aledo", "Arlington", "Azle", "Burleson", "Cleburne", "Colleyville", "Dallas", "Fort Worth",
    "Glen Rose", "Granbury", "Grand Prairie", "Grapevine", "Joshua", "Keller", "Mansfield", "Midlothian",
    "North Richland Hills", "Pecan Plantation", "Southlake", "Stephenville", "Waxahachie", "Weatherford", "Willow Park"];

  function townPage(town) {
    for (var i = 0; i < TOWN_PAGES.length; i++) {
      if (TOWN_PAGES[i].toLowerCase() === String(town).toLowerCase()) {
        return TOWN_PAGES[i].toLowerCase().replace(/ /g, "-") + "-roofing.html";
      }
    }
    return null;
  }

  var CALL = { label: "Call " + PHONE_SHOWN, href: "tel:" + PHONE, primary: true };
  var TEXT = { label: "Text us", href: SMS };
  var BOOK = { label: "Request a free inspection", href: "free-inspection.html", primary: true };

  var TOPICS = [
    { id: "leak", q: "My roof is leaking right now",
      a: ["If a ceiling is sagging or water is near anything electrical, stay away from it. Don't go up on a wet roof.",
          "Catch the water with buckets and move your things out of the way.",
          "Then call or text KOG. We offer 24-hour emergency tarping to keep the water out until the repair is done. Tarping runs $150 to $3,300, depending on how much of the roof needs covering, and you'll know the price before we start."],
      links: [{ label: "What to do right now", href: "roof-leak-emergency.html" }],
      ctas: [CALL, TEXT] },
    { id: "cost", q: "What will my roof cost?",
      a: ["KOG posts its prices. Leak repairs run $350 to $1,500. Architectural shingle roofs run $500 to $750 per square (100 square feet of roof), so a typical 20-square roof is about $10,000 to $15,000 before extras.",
          "Metal runs $645 to $860 per square for exposed-fastener panels and $995 to $1,325 for standing seam.",
          "Every job starts with a free inspection, and you get a written price before any work starts."],
      links: [{ label: "Roof cost calculator", href: "roof-cost-calculator.html" }, { label: "All our prices", href: "roof-prices.html" }],
      ctas: [BOOK] },
    { id: "hail", q: "Did hail hit my house?",
      a: ["Our free hail check shows the days NOAA weather radar picked up hail 1 inch or larger near your address.",
          "Hail damage is hard to see from the ground. Dented gutters, vents, and AC fins are the first clue."],
      links: [{ label: "Check your address", href: "hail-check.html" }, { label: "After a storm: what to check", href: "storm-damage-guide.html" }],
      ctas: [BOOK] },
    { id: "insurance", q: "Insurance claim questions",
      a: ["You file the claim with your insurance company, and you choose who fixes your roof. KOG gives you a written report with photos. We don't act as your adjuster.",
          "When insurance is paying, the scope your insurance company approves sets the price, and you pay your deductible. Can't pay the deductible all at once? Ask about our 0% deductible payment plan."],
      links: [{ label: "Will insurance pay after hail?", href: "hail-insurance-claim.html" }, { label: "Claim deadlines", href: "hail-claim-deadline.html" },
              { label: "What a claim will cost you", href: "roof-claim-calculator.html" }, { label: "Deductible payment plan", href: "deductible-payment-plan.html" }],
      ctas: [BOOK] },
    { id: "free", q: "Is the inspection really free?",
      a: ["Yes. You get a written report with photos of what we found, and an honest answer about whether your roof needs a repair, a replacement, or nothing at all.",
          "Want your roof on record before hail season? KOG Storm Ready is a free check with dated photos kept on file."],
      links: [{ label: "KOG Storm Ready", href: "storm-ready.html" }],
      ctas: [BOOK] },
    { id: "letter", q: "I need my roof's condition in writing",
      a: ["A KOG roof certification letter is $175 for most homes. We check the roof and attic, any needed repairs are done first, then we certify in writing that the roof has no active leaks.",
          "If it leaks from normal wear in the next 2 years, we fix the leak at no charge. Storm damage isn't covered; that goes through your insurance company.",
          "Only want your roof on record? KOG Storm Ready is a free check with dated photos kept on file."],
      links: [{ label: "Roof certification letters", href: "roof-letter.html" }, { label: "KOG Storm Ready", href: "storm-ready.html" }],
      ctas: [{ label: "Request a roof letter", href: "free-inspection.html?need=letter", primary: true }] },
    { id: "area", q: "Do you serve my area?", zip: true },
    { id: "pay", q: "Ways to pay",
      a: ["Cash, check, credit and debit cards, Zelle, Bitcoin, and other cryptocurrency.",
          "Paying for it yourself? With the KOG Straight Deal, the first 2 sheets of rotten decking are free and your first year of the Roof Care Plan is on us. Code KOG100 takes $100 off any job of $500 or more (not for work paid by an insurance claim)."],
      links: [{ label: "KOG Straight Deal", href: "straight-deal.html" }, { label: "Deductible payment plan", href: "deductible-payment-plan.html" }],
      ctas: [BOOK] },
    { id: "commercial", q: "I manage a commercial building",
      a: ["We repair, maintain, and replace TPO, EPDM, torch-down, and metal roofs on shops, warehouses, offices, and churches.",
          "Property managers get a written report with photos they can take to an owner. Every commercial roof is priced by quote after we inspect it."],
      links: [{ label: "Commercial roofing", href: "commercial-roofing.html" }],
      ctas: [CALL, BOOK] },
    { id: "person", q: "Talk to a person",
      a: ["Call or text " + PHONE_SHOWN + ". From 7 AM to 7 PM, Monday through Saturday, texts and online requests get an answer within an hour. Emergency tarping is available 24 hours."],
      ctas: [CALL, TEXT] }
  ];

  var css = "" +
    ".kc-btn{position:fixed;right:16px;bottom:20px;z-index:70;display:flex;align-items:center;gap:8px;padding:12px 16px;border:3px solid var(--yellow,#F2DE3A);border-radius:999px;background:var(--navy,#1F2A5C);color:#fff;font:800 1rem/1 Archivo,Arial,sans-serif;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25)}" +
    ".kc-btn svg{width:20px;height:20px;flex:none}" +
    ".kc-btn:focus-visible,.kc-panel :focus-visible{outline:3px solid var(--yellow,#F2DE3A);outline-offset:2px}" +
    ".kc-panel{position:fixed;right:16px;bottom:20px;z-index:80;width:min(380px,calc(100vw - 32px));max-height:min(620px,calc(100vh - 40px));display:flex;flex-direction:column;background:#fff;color:var(--ink,#1C2133);border-radius:10px;box-shadow:0 10px 40px rgba(0,0,0,.3);overflow:hidden;font-family:Archivo,Arial,sans-serif}" +
    ".kc-panel[hidden]{display:none}" +
    ".kc-head{display:flex;align-items:center;justify-content:space-between;gap:10px;background:var(--navy,#1F2A5C);color:#fff;padding:12px 14px;border-bottom:4px solid var(--yellow,#F2DE3A)}" +
    ".kc-head h2{margin:0;color:#fff;font-size:1.05rem;line-height:1.2}" +
    ".kc-close{background:none;border:0;color:#fff;font-size:1.6rem;line-height:1;cursor:pointer;padding:2px 6px}" +
    ".kc-body{overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}" +
    ".kc-msg{background:var(--wash,#EDEFF3);border-radius:10px 10px 10px 2px;padding:10px 12px;font-size:.98rem;line-height:1.45;max-width:94%}" +
    ".kc-msg p{margin:0 0 .5em}.kc-msg p:last-child{margin:0}" +
    ".kc-you{align-self:flex-end;background:var(--navy,#1F2A5C);color:#fff;border-radius:10px 10px 2px 10px}" +
    ".kc-fine{font-size:.82rem;color:var(--steel,#535D73);margin:0}" +
    ".kc-opts{display:flex;flex-wrap:wrap;gap:8px}" +
    ".kc-opt{border:2px solid var(--navy,#1F2A5C);background:#fff;color:var(--navy,#1F2A5C);border-radius:999px;padding:8px 12px;font:700 .95rem/1.15 Archivo,Arial,sans-serif;cursor:pointer;text-align:left}" +
    ".kc-opt:hover{background:var(--wash,#EDEFF3)}" +
    ".kc-links{display:flex;flex-direction:column;gap:6px;margin-top:4px}" +
    ".kc-links a{color:var(--navy,#1F2A5C);font-weight:700}" +
    ".kc-ctas{display:flex;flex-wrap:wrap;gap:8px}" +
    ".kc-cta{display:inline-block;padding:10px 14px;border-radius:3px;font-weight:800;text-decoration:none;border:2px solid var(--navy,#1F2A5C);color:var(--navy,#1F2A5C);background:#fff}" +
    ".kc-cta.kc-primary{background:var(--yellow,#F2DE3A);border-color:var(--yellow,#F2DE3A)}" +
    ".kc-zip{display:flex;gap:8px}.kc-zip input{flex:1;min-width:0;font:inherit;font-size:1rem;padding:9px 10px;border:2px solid var(--line,#CBD0DB);border-radius:3px}" +
    ".kc-zip button{font:800 1rem Archivo,Arial,sans-serif;padding:9px 14px;border:0;border-radius:3px;background:var(--navy,#1F2A5C);color:#fff;cursor:pointer}" +
    "@media (max-width:759px){.kc-btn{bottom:calc(82px + env(safe-area-inset-bottom));padding:10px 14px}.kc-panel{bottom:calc(78px + env(safe-area-inset-bottom));max-height:calc(100vh - 100px - env(safe-area-inset-bottom))}}" +
    "@media print{.kc-btn,.kc-panel{display:none!important}}";

  function u(h) { return /^(tel:|sms:|https?:|#|\/)/.test(h) ? h : "/" + h; }

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "cls") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  function init() {
    var style = el("style"); style.textContent = css; document.head.appendChild(style);

    var btn = el("button", { type: "button", cls: "kc-btn", "aria-expanded": "false", "aria-controls": "kc-panel" });
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg><span>Questions?</span>';

    var panel = el("div", { id: "kc-panel", cls: "kc-panel", role: "dialog", "aria-label": "KOG Roofing quick answers", hidden: "" });
    var title = el("h2", { text: "KOG Roofing quick answers" });
    var close = el("button", { type: "button", cls: "kc-close", "aria-label": "Close" }); close.textContent = "×";
    var body = el("div", { cls: "kc-body", "aria-live": "polite" });
    panel.appendChild(el("div", { cls: "kc-head" }, [title, close]));
    panel.appendChild(body);
    document.body.appendChild(btn);
    document.body.appendChild(panel);

    function scrollDown() { body.scrollTop = body.scrollHeight; }

    function bot(paras) {
      var m = el("div", { cls: "kc-msg" });
      paras.forEach(function (p) { m.appendChild(el("p", { text: p })); });
      body.appendChild(m);
      return m;
    }

    function linkList(links) {
      var box = el("div", { cls: "kc-links" });
      links.forEach(function (l) { box.appendChild(el("a", { href: u(l.href), text: l.label + " →" })); });
      return box;
    }

    function ctaRow(ctas) {
      var row = el("div", { cls: "kc-ctas" });
      ctas.forEach(function (c) { row.appendChild(el("a", { href: u(c.href), cls: "kc-cta" + (c.primary ? " kc-primary" : ""), text: c.label })); });
      return row;
    }

    function menu(label) {
      var wrap = el("div", { cls: "kc-opts", role: "group", "aria-label": label || "Questions" });
      TOPICS.forEach(function (t) {
        var b = el("button", { type: "button", cls: "kc-opt", text: t.q });
        b.addEventListener("click", function () { answer(t); });
        wrap.appendChild(b);
      });
      body.appendChild(wrap);
      return wrap;
    }

    function backButton() {
      var wrap = el("div", { cls: "kc-opts" });
      var b = el("button", { type: "button", cls: "kc-opt", text: "← Other questions" });
      b.addEventListener("click", function () { menu(); scrollDown(); });
      wrap.appendChild(b);
      body.appendChild(wrap);
    }

    function answer(t) {
      body.appendChild(el("div", { cls: "kc-msg kc-you", text: t.q }));
      if (t.zip) { zipAsk(); scrollDown(); return; }
      var m = bot(t.a);
      if (t.links) m.appendChild(linkList(t.links));
      if (t.ctas) body.appendChild(ctaRow(t.ctas));
      backButton();
      scrollDown();
    }

    var zips = null;
    function loadZips() {
      if (zips) return Promise.resolve(zips);
      return fetch("/service-zips.json").then(function (r) { return r.json(); }).then(function (j) {
        zips = {};
        j.forEach(function (row) { zips[row[0]] = { town: row[1], county: row[2] }; });
        return zips;
      });
    }

    function zipAsk() {
      var m = bot(["Type your 5-digit ZIP code and I'll check it against our service area."]);
      var form = el("form", { cls: "kc-zip" });
      var input = el("input", { type: "text", inputmode: "numeric", maxlength: "5", autocomplete: "postal-code", "aria-label": "Your ZIP code", placeholder: "ZIP code" });
      var go = el("button", { type: "submit", text: "Check" });
      form.appendChild(input); form.appendChild(go);
      m.appendChild(form);
      input.addEventListener("input", function () { input.value = input.value.replace(/\D/g, "").slice(0, 5); });
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var z = input.value.trim();
        if (!/^\d{5}$/.test(z)) { input.focus(); return; }
        go.disabled = true;
        body.appendChild(el("div", { cls: "kc-msg kc-you", text: z }));
        loadZips().then(function (list) {
          var hit = list[z];
          var r;
          if (hit) {
            r = bot(["Yes. " + z + " is " + hit.town + ", in " + hit.county + " County, and that's in our service area."]);
            var page = townPage(hit.town);
            if (page) r.appendChild(linkList([{ label: "Roofing in " + hit.town, href: page }]));
            body.appendChild(ctaRow([BOOK, CALL]));
          } else {
            r = bot(["That ZIP isn't on our list. Call or text and ask. If we can do the job right, we'll come."]);
            r.appendChild(linkList([{ label: "Every town we serve", href: "service-areas.html" }]));
            body.appendChild(ctaRow([CALL, TEXT]));
          }
          backButton();
          scrollDown();
        }).catch(function () {
          bot(["Sorry, I couldn't check that just now. Call or text " + PHONE_SHOWN + " and we'll tell you."]);
          body.appendChild(ctaRow([CALL, TEXT]));
          backButton();
          scrollDown();
        });
      });
      setTimeout(function () { input.focus(); }, 50);
    }

    var started = false;
    function open() {
      panel.hidden = false;
      btn.hidden = true;
      btn.setAttribute("aria-expanded", "true");
      if (!started) {
        started = true;
        bot(["Hi! I'm KOG Roofing's quick-answer helper. Tap a question below."]);
        body.appendChild(el("p", { cls: "kc-fine", text: "I'm not a person or an AI. I answer from KOG's posted prices and policies, and I don't collect anything you type. For anything else, call or text " + PHONE_SHOWN + "." }));
        menu();
      }
      var first = body.querySelector("button");
      (first || close).focus();
    }
    function shut() {
      panel.hidden = true;
      btn.hidden = false;
      btn.setAttribute("aria-expanded", "false");
      btn.focus();
    }
    btn.addEventListener("click", open);
    close.addEventListener("click", shut);
    panel.addEventListener("keydown", function (e) { if (e.key === "Escape") shut(); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
