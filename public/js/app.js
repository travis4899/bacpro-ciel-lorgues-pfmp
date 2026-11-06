/* Carte des stages CIEL — application (Leaflet + MarkerCluster, sans autre dépendance).
   Données chargées depuis data/*.json, exportées depuis la base SQLite. */
(function () {
  "use strict";

  // ------------------------------------------------------------ constantes
  const REL = { 3: "Forte", 2: "Moyenne", 1: "À vérifier" };
  const DEPS = { "83": "Var", "HA": "Hors département" };
  // Référentiel du bac pro CIEL (annexe II) : pôles, activités et niveau de lien calculé par scripts/referentiel.py
  const POLES = { E: "Électronique", R: "Réseaux", D: "Cyber & données" };
  const ACTS = { E1: "Étude et conception de produits électroniques", E2: "Tests et essais", E3: "Production et assemblage d'ensembles électroniques",
    E4: "Intégration matérielle et logicielle", E5: "Maintenance et réparation de produits électroniques", R1: "Accompagnement du client",
    R2: "Installation et qualification", R3: "Exploitation et maintien en condition opérationnelle", R5: "Maintenance des réseaux informatiques",
    D1: "Élaboration et appropriation d'un cahier des charges", D2: "Développement et validation de solutions logicielles", D3: "Gestion d'incidents" };
  const FAMILLES = { SI: "Systèmes d'information & DSI", RT: "Réseaux & télécoms", CF: "Courants faibles & sûreté",
    EL: "Électronique & bureau d'études", CY: "Cybersécurité" };
  const FAM_COURT = { SI: "SI & DSI", RT: "Réseaux & télécoms", CF: "Courants faibles & sûreté", EL: "Électronique & BE", CY: "Cybersécurité" };
  const ADEQ = { 4: "Stage CIEL déjà réalisé", 3: "Cœur du référentiel CIEL", 2: "Activités CIEL possibles", 1: "Lien partiel", 0: "Hors référentiel" };
  const SIZES = { "1-9": "1 à 9", "10-49": "10 à 49", "50-249": "50 à 249", "250+": "250 et +", "0": "0 salarié", "?": "Non renseignée" };
  const VILLE_LYCEE = "Lorgues";          // proposée en tête de la liste « Près de chez moi »
  const PAGE = 80;                        // lignes affichées par lot dans la liste
  const STORE_FILTERS = "ciel-filters-v4", STORE_FAVS = "ciel-favs";

  // ------------------------------------------------------------ utilitaires
  const $ = (id) => document.getElementById(id);
  const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const css = getComputedStyle(document.documentElement);
  const token = (name) => css.getPropertyValue(name).trim();
  const col = (cat) => token("--c-" + cat) || "#888";
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* stockage indisponible */ } },
  };
  const sizeOf = (t) => t === "00" ? "0" : ["01", "02", "03"].includes(t) ? "1-9" : ["11", "12"].includes(t) ? "10-49"
    : ["21", "22", "31"].includes(t) ? "50-249" : /^\d\d$/.test(t) ? "250+" : "?";
  function dist(a, b, c, d) { const p = Math.PI / 180, x = (d - b) * p * Math.cos((a + c) / 2 * p), y = (c - a) * p; return Math.sqrt(x * x + y * y) * 6371; }
  function toast(msg) { const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 1800); }
  function copy(txt, msg) {
    const fallback = () => {
      const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); toast(msg); } catch (e) { toast("Sélectionne le texte pour le copier"); }
      ta.remove();
    };
    try { navigator.clipboard.writeText(txt).then(() => toast(msg), fallback); } catch (e) { fallback(); }
  }
  const getJSON = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(p + " : " + r.status); return r.json(); });

  // Fenêtre « À propos » (indépendante du chargement des données)
  const about = $("about");
  $("about-open").addEventListener("click", () => { if (about.showModal) about.showModal(); else about.setAttribute("open", ""); });
  about.addEventListener("click", (e) => { if (e.target === about) about.close(); });

  // Panneau de filtres (tablette / téléphone) et onglets Liste / Carte
  const panel = $("filters"), scrim = $("scrim"), appEl = $("app");
  const narrow = () => matchMedia("(max-width: 1179px)").matches;
  const phone = () => matchMedia("(max-width: 759px)").matches;
  function openFilters(on) {
    panel.classList.toggle("open", on); scrim.hidden = !on; $("filters-open").setAttribute("aria-expanded", on);
    if (on) panel.querySelector("summary")?.focus();
  }
  $("filters-open").addEventListener("click", () => openFilters(true));
  $("filters-close").addEventListener("click", () => openFilters(false));
  scrim.addEventListener("click", () => openFilters(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && panel.classList.contains("open")) openFilters(false); });
  let onView = () => {};
  function setView(v) {
    appEl.dataset.view = v;
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.view === v));
    onView(v);
  }
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));

  // lieux.json est produit à partir du tableau Grist par scripts/grist_sync.py
  Promise.all(["data/lieux.json", "data/meta.json", "data/naf.json", "data/departements.json", "data/villes.json"].map(getJSON))
    .then(start)
    .catch((e) => { $("list").innerHTML = `<div class="empty">Impossible de charger les données (${esc(e.message)}). Ouvre la carte depuis un serveur web (GitLab Pages, ou <span class="mono">python3 -m http.server</span> dans le dossier public).</div>`; });

  function start([LIEUX, META, NAF, BASE, TOWNS]) {
    const CATS = META.categories, TR = META.tranches;
    $("maj").textContent = new Date(META.date).toLocaleDateString("fr-FR", { year: "numeric", month: "long", day: "numeric" });

    // ---------------------------------------------------------- données
    const F = Object.fromEntries(LIEUX.champs.map((c, i) => [c, i]));
    const base = LIEUX.lieux.map((a) => { const r = {}; for (const k in F) r[k] = a[F[k]]; return r; });
    const rows = base.map((r, i) => {
      r.i = i;
      const d2 = String(r.cp).slice(0, 2); r.dep = d2 in DEPS && d2 !== "HA" ? d2 : "HA";
      r.size = sizeOf(r.t); r.rel = +r.rel; r.adeq = +r.adeq || 0; r.poles = r.poles || ""; r.acts = r.acts || ""; r.fam = r.fam || "";
      r.title = r.ens || r.nom; r.osm = /^(osm|grist)/.test(String(r.siret));
      r.label = NAF[r.naf] || r.osm_type || CATS[r.cat];
      r.hasContact = !!(r.tel || r.mail);
      r.txt = norm([r.nom, r.ens, r.ville, r.cp, r.naf, String(r.naf).replace(".", ""), r.label, CATS[r.cat]].join(" "));
      return r;
    });
    let favs = new Set(store.get(STORE_FAVS, []));

    // ---------------------------------------------------------- état des filtres
    // au premier lancement : pertinence forte, cœur du référentiel ou stage déjà réalisé, avec téléphone ou e-mail, tous les métiers
    const DEF_REL = ["3"], DEF_ADEQ = ["4", "3"];
    const state = { rel: new Set(DEF_REL), dep: new Set(Object.keys(DEPS)), cat: new Set(Object.keys(CATS)),
      size: new Set(Object.keys(SIZES)), naf: "", q: "", town: "", km: 30,
      onlyfav: false, contact: true, stage: false, poles: new Set(), fam: new Set(), adeq: new Set(DEF_ADEQ) };
    const saved = store.get(STORE_FILTERS, null);
    if (saved) {
      for (const k of ["rel", "dep", "cat", "size", "poles", "fam", "adeq"]) if (Array.isArray(saved[k])) state[k] = new Set(saved[k]);
      // secteurs / départements apparus depuis la dernière visite : cochés par défaut
      for (const [k, all] of [["cat", CATS], ["dep", DEPS]]) for (const v of Object.keys(all)) if (!(saved.known?.[k] || []).includes(v)) state[k].add(v);
      for (const k of ["naf", "town", "km", "contact", "stage"]) if (saved[k] != null) state[k] = saved[k];
    }
    const saveState = () => store.set(STORE_FILTERS, { rel: [...state.rel], dep: [...state.dep], cat: [...state.cat], poles: [...state.poles], fam: [...state.fam], adeq: [...state.adeq],
      size: [...state.size], naf: state.naf, town: state.town, km: state.km, contact: state.contact, stage: state.stage,
      known: { cat: Object.keys(CATS), dep: Object.keys(DEPS) } });

    // ---------------------------------------------------------- filtres (UI)
    function counts(key) { const c = {}; rows.forEach((r) => { const v = String(r[key]); c[v] = (c[v] || 0) + 1; }); return c; }
    function chips(id, key, entries, dotFn) {
      const el = $(id), c = counts(key);
      el.innerHTML = entries.filter(([k]) => c[k]).map(([k, l]) => `<label class="chip ${key === "rel" ? "relchip" : ""}">
        <input type="checkbox" value="${k}" ${state[key].has(k) ? "checked" : ""}>${dotFn ? dotFn(k) : ""}${esc(l)} <span class="n">${c[k]}</span></label>`).join("");
      el.addEventListener("change", (e) => { const v = e.target.value; e.target.checked ? state[key].add(v) : state[key].delete(v); apply(); });
    }
    chips("f-rel", "rel", [["3", REL[3]], ["2", REL[2]], ["1", REL[1]]],
      (k) => `<span class="bar" style="color:var(${k == 3 ? "--forte" : k == 2 ? "--moyenne" : "--verif"})">${[1, 2, 3].map((n) => `<i class="${n <= k ? "on" : ""}"></i>`).join("")}</span>`);
    chips("f-dep", "dep", Object.entries(DEPS).map(([k, v]) => [k, k === "HA" ? v : k + " · " + v]));
    chips("f-adeq", "adeq", [["4", ADEQ[4]], ["3", ADEQ[3]], ["2", ADEQ[2]], ["1", ADEQ[1]], ["0", ADEQ[0]]],
      (k) => `<span class="bar" style="color:var(--accent)">${[1, 2, 3, 4].map((n) => `<i class="${n <= k ? "on" : ""}"></i>`).join("")}</span>`);
    chips("f-cat", "cat", Object.entries(CATS), (k) => `<span class="dot" style="background:${col(k)}"></span>`);
    chips("f-size", "size", Object.entries(SIZES));
    // Boutons rapides du bandeau : même état que le filtre « Secteur » du panneau.
    // Tout est coché -> un clic isole l'activité ; ensuite chaque clic ajoute / retire ; « Tout » réinitialise.
    const COURT = { info: "Informatique", cyber: "Cyber", tele: "Réseaux / fibre", elec: "Électronique", maint: "Dépannage",
      secu: "Alarmes / vidéo", grande: "Sièges & DSI", elecb: "Électricité", comm: "Vente info", etudes: "Bureaux d'études",
      public: "Collectivités", sante: "Santé", media: "Médias", sport: "Sport", autre: "Autres" };
    const catCount = counts("cat");
    const qcEl = $("quickcats");
    const famCount = {}; rows.forEach((r) => r.fam.split(" ").filter(Boolean).forEach((f) => (famCount[f] = (famCount[f] || 0) + 1)));
    qcEl.innerHTML = `<button type="button" class="qc qc-all" data-fam="*">Tous les métiers</button>`
      + Object.keys(FAMILLES).filter((k) => famCount[k]).map((k) => `<button type="button" class="qc" data-fam="${k}" title="${esc(FAMILLES[k])} (${famCount[k]})">${esc(FAM_COURT[k])}</button>`).join("")
      + `<span class="qc-sep" aria-hidden="true"></span>`
      + Object.entries(POLES).map(([k, v]) => `<button type="button" class="qc qp" data-pole="${k}" title="Pôle du référentiel CIEL"><span class="pole pole-${k}">${k}</span>${esc(v)}</button>`).join("");
    qcEl.addEventListener("click", (e) => {
      const b = e.target.closest(".qc"); if (!b) return;
      if (b.dataset.pole) { const p = b.dataset.pole; state.poles.has(p) ? state.poles.delete(p) : state.poles.add(p); apply(); return; }
      if (b.dataset.fam) { const f = b.dataset.fam; if (f === "*") state.fam.clear(); else state.fam.has(f) ? state.fam.delete(f) : state.fam.add(f); apply(); return; }
      const k = b.dataset.cat, all = Object.keys(CATS);
      if (k === "*") state.cat = new Set(all);
      else if (state.cat.size === all.length) state.cat = new Set([k]);
      else { state.cat.has(k) ? state.cat.delete(k) : state.cat.add(k); if (!state.cat.size) state.cat = new Set(all); }
      apply();
    });
    function syncCats() {
      const all = state.cat.size === Object.keys(CATS).length;
      qcEl.classList.toggle("some", !all);
      qcEl.querySelectorAll(".qc[data-fam]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.fam === "*" ? !state.fam.size : state.fam.has(b.dataset.fam)));
      qcEl.querySelectorAll(".qp").forEach((b) => b.setAttribute("aria-pressed", state.poles.has(b.dataset.pole)));
      document.querySelectorAll("#f-cat input").forEach((i) => (i.checked = state.cat.has(i.value)));
    }
    function setAllCats(on) { state.cat = on ? new Set(Object.keys(CATS)) : new Set(); document.querySelectorAll("#f-cat input").forEach((i) => (i.checked = on)); apply(); }
    $("cat-all").onclick = () => setAllCats(true);
    $("cat-none").onclick = () => setAllCats(false);

    $("n-contact").textContent = rows.filter((r) => r.hasContact).length;
    $("n-stage").textContent = rows.filter((r) => r.stage).length;
    $("withcontact").checked = state.contact; $("withstage").checked = state.stage;
    $("withcontact").onchange = (e) => { state.contact = e.target.checked; apply(); };
    $("withstage").onchange = (e) => { state.stage = e.target.checked; apply(); };

    const nafSel = $("naf-sel"), nafC = counts("naf");
    Object.keys(nafC).filter(Boolean).sort().forEach((c) => nafSel.add(new Option(`${c} · ${NAF[c] || ""} (${nafC[c]})`, c)));
    nafSel.value = state.naf; nafSel.onchange = () => { state.naf = nafSel.value; apply(); };

    const townSel = $("town");
    const lycee = TOWNS.find((t) => t[0] === VILLE_LYCEE);
    if (lycee) townSel.add(new Option(`${VILLE_LYCEE} (lycée)`, VILLE_LYCEE));
    [...TOWNS].sort((a, b) => a[0].localeCompare(b[0], "fr")).forEach((t) => { if (t[0] !== VILLE_LYCEE) townSel.add(new Option(t[0], t[0])); });
    townSel.value = state.town;
    const km = $("km"), kmo = $("kmo"); km.value = state.km; kmo.textContent = state.km + " km";
    townSel.onchange = () => { state.town = townSel.value; apply(true); if (narrow() && state.town) openFilters(false); };
    km.oninput = () => { state.km = +km.value; kmo.textContent = km.value + " km"; apply(); };
    km.onchange = () => apply(true);
    let qt; $("q").addEventListener("input", (e) => { clearTimeout(qt); qt = setTimeout(() => { state.q = e.target.value; apply(); }, 150); });
    $("onlyfav").onchange = (e) => { state.onlyfav = e.target.checked; apply(); };
    $("reset").onclick = () => { try { localStorage.removeItem(STORE_FILTERS); } catch (e) { /* rien */ } location.reload(); };

    // ---------------------------------------------------------- carte
    const map = L.map("map", { preferCanvas: true, zoomSnap: 0.5, minZoom: 7, maxZoom: 19 }).setView([46.1, -0.2], 8);
    map.attributionControl.setPrefix(false);
    onView = (v) => { if (v === "map") setTimeout(() => map.invalidateSize(), 0); };
    matchMedia("(max-width: 759px)").addEventListener("change", () => setTimeout(() => map.invalidateSize(), 0));
    // Fond de carte : tuiles OpenStreetMap. Le fond vectoriel embarqué (contours + villes) ne s'affiche
    // que si les tuiles ne se chargent pas (hors ligne, réseau filtré…), pour ne jamais se superposer à OSM.
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">contributeurs OpenStreetMap</a>' }).addTo(map);
    let tileOk = false, tileErr = 0, fallbackOn = false;
    tiles.on("tileload", () => { tileOk = true; });
    tiles.on("tileerror", () => { if (++tileErr > 3 && !tileOk) useFallback(); });
    setTimeout(() => { if (!tileOk) useFallback(); }, 6000);
    const townLayer = L.layerGroup();
    const depLbl = L.layerGroup([[45.72, 0.2, "Charente"], [45.83, -0.6, "Charente-Maritime"], [46.5, -0.35, "Deux-Sèvres"], [46.55, 0.55, "Vienne"]]
      .map(([a, b, n]) => L.marker([a, b], { interactive: false, keyboard: false, icon: L.divIcon({ className: "dep-lbl", html: n, iconSize: null }) })));
    function drawTowns() {
      townLayer.clearLayers(); const z = map.getZoom(); const min = z < 8.5 ? 25000 : z < 9.5 ? 9000 : z < 10.5 ? 4000 : 2500;
      TOWNS.filter((t) => t[3] >= min).forEach((t) => L.marker([t[1], t[2]], { interactive: false, keyboard: false,
        icon: L.divIcon({ className: "town-lbl" + (t[3] > 40000 ? " big" : ""), html: esc(t[0]), iconSize: null, iconAnchor: [-4, 8] }) }).addTo(townLayer));
      map.getZoom() < 8.5 ? depLbl.addTo(map) : depLbl.remove();
    }
    function useFallback() {
      if (fallbackOn) return; fallbackOn = true;
      map.removeLayer(tiles);
      L.geoJSON(BASE, { interactive: false, style: (f) => {
        const ours = f.properties.code in DEPS;
        return { color: token("--dep-line"), weight: ours ? 1.6 : 0.8, fillColor: token(ours ? "--land-in" : "--land"), fillOpacity: 1, opacity: ours ? 1 : 0.5 };
      } }).addTo(map).bringToBack();
      townLayer.addTo(map); drawTowns(); map.on("zoomend", drawTowns);
    }

    const cluster = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: (z) => (z < 10 ? 50 : 35), disableClusteringAtZoom: 14,
      spiderfyOnMaxZoom: true, chunkedLoading: true,
      iconCreateFunction: (c) => { const n = c.getChildCount(); const s = n < 10 ? 28 : n < 100 ? 34 : n < 500 ? 40 : 46;
        return L.divIcon({ html: `<div class="clu" style="width:${s}px;height:${s}px">${n}</div>`, className: "", iconSize: [s, s] }); } });
    map.addLayer(cluster);
    const radius = { 3: 8, 2: 6, 1: 4.5 };
    rows.forEach((r) => {
      r.m = L.circleMarker([r.lat, r.lon], r.stage
        ? { radius: 10, color: token("--stage"), weight: 3, fillColor: col(r.cat), fillOpacity: 1 }
        : { radius: radius[r.rel], color: r.rel == 3 ? token("--ink") : col(r.cat), weight: r.rel == 3 ? 1.5 : 1, fillColor: col(r.cat), fillOpacity: r.rel == 1 ? 0.55 : 0.9 });
      r.m.on("click", () => openFiche(r));
    });
    let townCircle = null;
    // Une seule fiche, posée sur la carte et non liée au point : MarkerCluster retire et remet les points
    // pendant ses animations, ce qui refermait aussitôt une fiche liée au point (surtout sur téléphone).
    const fiche = L.popup({ maxWidth: 330 });
    let ficheRow = null;
    function openFiche(r) { ficheRow = r; fiche.setLatLng(r.m.getLatLng()).setContent(popup(r)); map.openPopup(fiche); highlight(r); }

    // ---------------------------------------------------------- fiche (popup)
    function contactBlock(r) {
      if (!r.hasContact && !r.web) return `<div class="nocontact">Pas de contact trouvé automatiquement : utilise les recherches ci-dessous.</div>`;
      const line = (label, href, val) => `<div class="ln"><span class="src">${label}</span><a href="${href}" ${href.startsWith("http") ? 'target="_blank" rel="noopener"' : ""}>${esc(val)}</a>
        <button type="button" class="cp" data-copytxt="${esc(val)}">Copier</button></div>`;
      return `<div class="contact">
        ${r.tel ? line("Tél.", "tel:" + r.tel.replace(/\s/g, ""), r.tel) : ""}
        ${r.mail ? line("E-mail", "mailto:" + r.mail, r.mail) : ""}
        ${r.web ? line("Site", r.web, r.web.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")) : ""}
        ${r.csrc ? `<div class="src">Source : ${esc(r.csrc.split("|").join(", "))}</div>` : ""}</div>`;
    }
    function ciel(r) {
      const acts = r.acts ? r.acts.split(" ") : [];
      return `<div class="ciel"><div class="ciel-h"><span class="bar">${[1, 2, 3, 4].map((n) => `<i class="${n <= r.adeq ? "on" : ""}"></i>`).join("")}</span>
        <b>${esc(ADEQ[r.adeq])}</b>${r.poles ? " · " + r.poles.split(" ").map((p) => `<span class="pole pole-${p}">${p}</span>${esc(POLES[p])}`).join(" ") : ""}</div>
        ${r.fam ? `<div class="fams">${r.fam.split(" ").map((f) => `<span class="tag">${esc(FAMILLES[f])}</span>`).join("")}</div>` : ""}
        ${acts.length ? `<ul>${acts.map((a) => `<li><span class="mono">${a}</span> ${esc(ACTS[a] || "")}</li>`).join("")}</ul>` : ""}</div>`;
    }
    function popup(r) {
      const q = encodeURIComponent(`${r.title} ${r.ville}`), fav = favs.has(r.siret);
      return `<div class="pop"><h3>${esc(r.title)}</h3>${r.ens ? `<div class="ens">${esc(r.nom)}</div>` : ""}
      ${r.stage ? `<div class="stage">★ ${esc(r.stage)}</div>` : ""}
      <div class="tags"><span class="tag" style="border-color:${col(r.cat)}">${esc(CATS[r.cat])}</span><span class="tag">Pertinence : ${REL[r.rel]}</span>${r.siege == 1 ? '<span class="tag">Siège</span>' : ""}</div>
      ${ciel(r)}
      ${r.note ? `<div class="note">${esc(r.note)}</div>` : ""}
      ${contactBlock(r)}
      <dl><dt>Activité</dt><dd>${esc(r.label)}</dd>
      <dt>Adresse</dt><dd>${esc(r.adr)}<br>${esc(r.cp)} ${esc(r.ville)}</dd>
      <dt>Salariés</dt><dd>${esc(TR[r.t] || "non renseigné")} sur ce site${r.tu && r.tu !== r.t ? `<br>${esc(TR[r.tu] || "?")} dans l'entreprise` : ""}</dd>
      ${r.osm ? "" : `<dt>SIRET</dt><dd class="mono">${esc(r.siret)}</dd>`}</dl>
      ${r.approx == 1 ? '<div class="warn">Position approximative (centre de la commune ou de la rue)</div>' : ""}
      <div class="links">${r.osm ? "" : `<a class="main" href="https://annuaire-entreprises.data.gouv.fr/etablissement/${r.siret}" target="_blank" rel="noopener">Fiche officielle</a>`}
      <a href="https://www.google.com/maps/search/?api=1&query=${q}" target="_blank" rel="noopener">Google Maps</a>
      <a href="https://www.pagesjaunes.fr/annuaire/chercherlespros?quoiqui=${encodeURIComponent(r.title)}&ou=${encodeURIComponent(r.ville)}" target="_blank" rel="noopener">PagesJaunes</a>
      <button type="button" data-copy="${r.i}">Copier la fiche</button>
      <button type="button" data-fav="${r.i}" aria-pressed="${fav}">${fav ? "★ Retirer" : "☆ Garder"}</button></div></div>`;
    }
    const ficheTexte = (r) => [r.title, r.ens ? r.nom : "", r.adr, `${r.cp} ${r.ville}`, r.tel && "Tél. " + r.tel, r.mail, r.web, r.osm ? "" : "SIRET " + r.siret].filter(Boolean).join("\n");
    document.addEventListener("click", (e) => {
      const t = e.target.closest("[data-copytxt]"); if (t) { copy(t.dataset.copytxt, "Copié"); return; }
      const c = e.target.closest("[data-copy]"); if (c) { copy(ficheTexte(rows[+c.dataset.copy]), "Fiche copiée"); return; }
      const f = e.target.closest("[data-fav]");
      if (f) {
        e.stopPropagation(); const r = rows[+f.dataset.fav]; toggleFav(r);
        if (f.closest(".pop")) { const on = favs.has(r.siret); f.setAttribute("aria-pressed", on); f.textContent = on ? "★ Retirer" : "☆ Garder"; }
      }
    });
    function toggleFav(r) {
      favs.has(r.siret) ? favs.delete(r.siret) : favs.add(r.siret); store.set(STORE_FAVS, [...favs]); $("nfav").textContent = favs.size;
      const b = document.querySelector(`.item[data-i="${r.i}"] .fav`); if (b) b.setAttribute("aria-pressed", favs.has(r.siret));
      if (state.onlyfav) apply();
    }
    $("nfav").textContent = favs.size;
    $("copyfav").onclick = () => {
      const l = rows.filter((r) => favs.has(r.siret)); if (!l.length) { toast("Aucune ★ pour l'instant"); return; }
      copy(l.map((r) => [r.title, `${r.adr}, ${r.cp} ${r.ville}`, r.tel, r.mail, r.label].filter(Boolean).join(" — ")).join("\n"), `${l.length} fiche(s) copiée(s)`);
    };
    $("copylist").onclick = () => {
      if (!current.length) { toast("La liste est vide"); return; }
      const h = ["Nom", "Enseigne", "Adresse", "Code postal", "Commune", "Téléphone", "E-mail", "Site web", "Code NAF", "Activité", "Salariés", "Pertinence", "SIRET"];
      const lines = current.map((r) => [r.nom, r.ens, r.adr, r.cp, r.ville, r.tel, r.mail, r.web, r.naf, r.label, TR[r.t] || "", REL[r.rel], r.osm ? "" : r.siret]
        .map((v) => String(v ?? "").replace(/[\t\n]/g, " ")).join("\t"));
      copy([h.join("\t")].concat(lines).join("\n"), `${current.length} lignes copiées — colle-les dans un tableur`);
    };

    // ---------------------------------------------------------- filtrage + liste
    let current = [], shown = 0;
    const listEl = $("list");
    const hint = (id, set, all) => { $(id).textContent = set.size === Object.keys(all).length ? "tout" : set.size + " / " + Object.keys(all).length; };
    function apply(fit) {
      const terms = norm(state.q).split(/\s+/).filter(Boolean);
      const t = TOWNS.find((x) => x[0] === state.town);
      current = rows.filter((r) => state.rel.has(String(r.rel)) && state.dep.has(r.dep) && state.cat.has(r.cat) && state.size.has(r.size)
        && (!state.naf || r.naf === state.naf) && (!state.onlyfav || favs.has(r.siret))
        && (!state.contact || r.hasContact) && (!state.stage || r.stage) && state.adeq.has(String(r.adeq))
        && (!state.poles.size || [...state.poles].some((p) => r.poles.includes(p)))
        && (!state.fam.size || [...state.fam].some((f) => r.fam.includes(f)))
        && terms.every((w) => r.txt.includes(w)) && (!t || (r.d = dist(t[1], t[2], r.lat, r.lon)) <= state.km));
      // tri : lien avec le référentiel CIEL (stages réalisés d'abord), puis pertinence, puis contact disponible
      current.sort(t ? (a, b) => a.d - b.d || b.adeq - a.adeq
        : (a, b) => b.adeq - a.adeq || b.rel - a.rel || b.hasContact - a.hasContact || a.ville.localeCompare(b.ville, "fr") || a.title.localeCompare(b.title, "fr"));
      $("nres").textContent = current.length.toLocaleString("fr-FR");
      syncCats();
      hint("h-rel", state.rel, REL); hint("h-adeq", state.adeq, ADEQ); hint("h-dep", state.dep, DEPS); hint("h-cat", state.cat, CATS); hint("h-size", state.size, SIZES);
      $("h-naf").textContent = state.naf || "tous";
      $("h-contact").textContent = [state.contact && "avec contact", state.stage && "stages"].filter(Boolean).join(", ");
      $("h-dist").textContent = t ? `${state.km} km autour de ${t[0]}` : "toutes distances";
      $("sortinfo").textContent = t ? `· du plus proche au plus loin de ${t[0]}` : "· triés par lien avec le référentiel CIEL";
      const full = (set, all) => set.size === Object.keys(all).length;
      const same = (set, def) => set.size === def.length && def.every((v) => set.has(v));
      const actifs = [!same(state.rel, DEF_REL), !full(state.dep, DEPS), !full(state.cat, CATS),
        !full(state.size, SIZES), !!state.naf, !!t, !state.contact, state.stage,
        state.poles.size > 0, state.fam.size > 0, !same(state.adeq, DEF_ADEQ)].filter(Boolean).length;
      $("nactive").hidden = !actifs; $("nactive").textContent = actifs;
      cluster.clearLayers(); cluster.addLayers(current.map((r) => r.m));
      if (ficheRow && !current.includes(ficheRow)) map.closePopup(fiche);
      if (townCircle) { map.removeLayer(townCircle); townCircle = null; }
      if (t) {
        townCircle = L.circle([t[1], t[2]], { radius: state.km * 1000, color: token("--accent"), weight: 1.5, fill: false, dashArray: "4 4", interactive: false }).addTo(map);
        if (fit) map.fitBounds(townCircle.getBounds(), { padding: [20, 20] });
      }
      shown = 0; listEl.innerHTML = ""; renderMore(); saveState();
    }
    function renderMore() {
      listEl.querySelector(".more")?.remove();
      if (!current.length) { listEl.innerHTML = '<div class="empty">Aucun lieu ne correspond. Élargis la pertinence, le secteur ou le rayon.</div>'; return; }
      const html = current.slice(shown, shown + PAGE).map((r) => `<div class="item" role="listitem" tabindex="0" data-i="${r.i}">
        <span class="sw" style="background:${col(r.cat)}"></span>
        <div class="t">${esc(r.title)}${r.ens ? ` <em>· ${esc(r.nom)}</em>` : ""}</div>
        <button class="fav" type="button" data-fav="${r.i}" aria-pressed="${favs.has(r.siret)}" aria-label="Garder en favori"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 1.5l1.9 4 4.3.5-3.2 3 .9 4.3L8 11.2 4.1 13.3l.9-4.3-3.2-3 4.3-.5z" fill="currentColor"/></svg></button>
        <div class="m"><span>${esc(r.ville)} (${r.dep})</span><span>${esc(r.label)}</span><span>${REL[r.rel]}</span>
          ${r.hasContact ? `<span class="ic" title="Contact disponible">${r.tel ? "☎" : ""}${r.mail ? "✉" : ""}</span>` : ""}
          ${r.poles ? `<span class="poles">${r.poles.split(" ").map((p) => `<span class="pole pole-${p}" title="${esc(POLES[p])}">${p}</span>`).join("")}</span>` : ""}
          ${r.stage ? '<span class="stage">★ stage réalisé</span>' : ""}
          ${r.d != null && state.town ? `<span class="d">${r.d.toFixed(1).replace(".", ",")} km</span>` : ""}</div>
      </div>`).join("");
      listEl.insertAdjacentHTML("beforeend", html); shown += PAGE;
      if (shown < current.length) listEl.insertAdjacentHTML("beforeend", `<div class="more"><button type="button">Afficher ${Math.min(PAGE, current.length - shown)} de plus (${current.length - shown} restants)</button></div>`);
    }
    listEl.addEventListener("click", (e) => {
      if (e.target.closest(".more button")) { renderMore(); return; }
      if (e.target.closest(".fav")) return;
      const it = e.target.closest(".item"); if (it) focusRow(rows[+it.dataset.i]);
    });
    listEl.addEventListener("keydown", (e) => { if (e.key === "Enter") { const it = e.target.closest(".item"); if (it) focusRow(rows[+it.dataset.i]); } });
    function focusRow(r) {
      if (phone()) setView("map");
      setTimeout(() => cluster.zoomToShowLayer(r.m, () => openFiche(r)), phone() ? 60 : 0);
    }
    function highlight(r) {
      document.querySelectorAll(".item.sel").forEach((x) => x.classList.remove("sel"));
      const it = document.querySelector(`.item[data-i="${r.i}"]`); if (it) { it.classList.add("sel"); if (!phone()) it.scrollIntoView({ block: "nearest" }); }
    }
    apply(!!state.town);
  }
})();
