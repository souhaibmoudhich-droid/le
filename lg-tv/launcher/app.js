/* Accueil Zen : horloge, dock d'applis et fonds d'écran qui tournent.
   ES5 uniquement (anciens webOS = Chromium 38+). */
(function () {
  var config = { dock: [], rotateSeconds: 40, fadeSeconds: 2.5, /* = durée du fondu dans style.css */ idleSeconds: 15, slowZoom: true, clock24h: true };
  var slides = [];   // { kind: "photo"|"scene", file, index, credit }
  var current = -1;
  var focus = 0;
  var idleTimer = null;
  var wall = document.getElementById("wall");

  var KEY = { LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, ENTER: 13, BACK: 461, ESC: 27 };

  function loadJSON(path, done) {
    // XHR plutôt que fetch : fetch ne lit pas les fichiers locaux sur les anciens webOS.
    var xhr = new XMLHttpRequest();
    xhr.open("GET", path, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      var data = null;
      try { data = JSON.parse(xhr.responseText); } catch (e) {}
      done(data);
    };
    try { xhr.send(); } catch (e) { done(null); }
  }

  function toast(text) {
    var el = document.getElementById("toast");
    el.textContent = text;
    el.className = "show";
    clearTimeout(toast.timer);
    toast.timer = setTimeout(function () { el.className = ""; }, 2600);
  }

  // ---------- lancement d'applis (API Luna de webOS) ----------
  function launch(app) {
    if (!app.id) {
      toast(app.title + " : lance « python lgtv.py dock » pour la relier");
      return;
    }
    if (typeof PalmServiceBridge === "undefined") {
      toast("Lancement de " + app.title + " (aperçu hors TV)");
      return;
    }
    var bridge = new PalmServiceBridge();
    bridge.onservicecallback = function (msg) {
      var res = {};
      try { res = JSON.parse(msg); } catch (e) {}
      if (res.returnValue === false) toast(app.title + " : " + (res.errorText || "lancement impossible"));
    };
    bridge.call("luna://com.webos.applicationManager/launch", JSON.stringify({ id: app.id }));
    launch.bridge = bridge; // garde une référence jusqu'à la réponse
  }

  // ---------- horloge ----------
  var DAYS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
  var MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  function tick() {
    var d = new Date(), h = d.getHours(), suffix = "";
    if (!config.clock24h) { suffix = h < 12 ? " AM" : " PM"; h = h % 12 || 12; }
    document.getElementById("time").textContent = (config.clock24h ? pad(h) : h) + ":" + pad(d.getMinutes()) + suffix;
    var day = DAYS[d.getDay()];
    document.getElementById("date").textContent = day.charAt(0).toUpperCase() + day.slice(1) + " " + d.getDate() + " " + MONTHS[d.getMonth()];
    setTimeout(tick, (60 - d.getSeconds()) * 1000 + 50);
  }

  // ---------- dock ----------
  function initials(title) {
    return title.length <= 12 ? title : title.split(/\s+/).map(function (w) { return w.charAt(0); }).join("");
  }

  function buildDock() {
    var tiles = document.getElementById("tiles");
    tiles.innerHTML = "";
    var n = config.dock.length;
    var width = n > 6 ? Math.floor((1800 - n * 40) / n) : 250;
    config.dock.forEach(function (app, i) {
      var tile = document.createElement("div");
      tile.className = "tile" + (app.id ? "" : " missing");
      tile.style.width = width + "px";
      tile.style.height = Math.round(width * 0.6) + "px";
      tile.style.background = "linear-gradient(145deg, " + app.color + ", " + shade(app.color, -0.35) + ")";
      if (app.id === "com.palm.app.settings") {
        tile.innerHTML = '<span class="gear">⚙︎</span>';
      } else if (app.icon) {
        var img = new Image();
        img.onload = function () { if (img.naturalWidth < 200) img.className = "contain"; };
        img.onerror = function () { tile.removeChild(img); addName(tile, app.title); };
        img.src = app.icon;
        tile.appendChild(img);
      } else {
        addName(tile, app.title);
      }
      tile.onmouseover = function () { setFocus(i); };   // pointeur Magic Remote
      tile.onclick = function () { setFocus(i); launch(app); };
      tiles.appendChild(tile);
    });
    setFocus(Math.min(focus, n - 1));
  }

  function addName(tile, title) {
    var span = document.createElement("span");
    span.className = "name";
    span.textContent = initials(title);
    tile.appendChild(span);
  }

  function shade(hex, amount) {
    var n = parseInt(hex.replace("#", ""), 16);
    var r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    function f(c) { return Math.max(0, Math.min(255, Math.round(c * (1 + amount)))); }
    return "rgb(" + f(r) + "," + f(g) + "," + f(b) + ")";
  }

  function setFocus(i) {
    var tiles = document.getElementById("tiles").children;
    if (!tiles.length) return;
    focus = (i + tiles.length) % tiles.length;
    for (var k = 0; k < tiles.length; k++) tiles[k].className = tiles[k].className.replace(" focus", "");
    tiles[focus].className += " focus";
    document.getElementById("label").textContent = config.dock[focus].title;
  }

  // ---------- fonds d'écran ----------
  function shuffle(a) {
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function buildSlides(photos) {
    slides = (photos || []).map(function (p) { return { kind: "photo", file: p.file, credit: p.credit ? p.titre + " — " + p.credit : p.titre }; });
    // Peu de photos : on complète avec les paysages dessinés.
    if (slides.length < 3) {
      for (var i = 0; i < Scenes.count; i++) slides.push({ kind: "scene", index: i, credit: Scenes.name(i) });
    }
    shuffle(slides);
  }

  function nextSlide() {
    if (!slides.length) return;
    current = (current + 1) % slides.length;
    var s = slides[current];
    var el;
    if (s.kind === "photo") {
      el = new Image();
      el.onload = function () { show(el, s); };
      el.onerror = function () { slides.splice(current, 1); current--; nextSlide(); };
      el.src = s.file;
    } else {
      el = Scenes.render(s.index);
      show(el, s);
    }
    setTimeout(nextSlide, config.rotateSeconds * 1000);
  }

  function show(el, s) {
    el.className = "slide" + (config.slowZoom ? " zoom" : "");
    wall.appendChild(el);
    el.offsetWidth; // force le style initial avant la transition
    el.className += " show";
    document.getElementById("credit").textContent = s.credit || "";
    // retire l'ancienne image une fois le fondu terminé (garde la mémoire basse)
    setTimeout(function () {
      while (wall.children.length > 1) wall.removeChild(wall.firstChild);
    }, config.fadeSeconds * 1000 + 200);
  }

  // ---------- mode repos ----------
  function wake() {
    document.body.className = "";
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function () { document.body.className = "idle"; }, config.idleSeconds * 1000);
  }

  document.addEventListener("keydown", function (e) {
    var wasIdle = document.body.className === "idle";
    wake();
    if (wasIdle && e.keyCode !== KEY.ENTER) { e.preventDefault(); return; } // 1er appui : réveille seulement
    switch (e.keyCode) {
      case KEY.LEFT: setFocus(focus - 1); break;
      case KEY.RIGHT: setFocus(focus + 1); break;
      case KEY.ENTER: if (!wasIdle) launch(config.dock[focus]); break;
      case KEY.BACK: case KEY.ESC: break; // reste sur l'accueil
      default: return;
    }
    e.preventDefault();
  });
  document.addEventListener("mousemove", wake);

  // ---------- démarrage ----------
  loadJSON("config.json", function (data) {
    if (data) for (var k in data) config[k] = data[k];
    tick();
    buildDock();
    wake();
    loadJSON("wallpapers/wallpapers.json", function (photos) {
      buildSlides(photos);
      nextSlide();
    });
  });
})();
