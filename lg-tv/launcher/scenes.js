/* Paysages nature dessinés sur canvas : toujours disponibles, même sans photos
   ni Internet. Chaque scène est dessinée une seule fois (aucune animation
   continue) pour ne pas solliciter le processeur de la TV. Code ES5 pour
   rester compatible avec les anciens webOS. */
var Scenes = (function () {
  var W = 1920, H = 1080;

  function rng(seed) {
    return function () {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };
  }

  function gradient(ctx, y0, y1, stops) {
    var g = ctx.createLinearGradient(0, y0, 0, y1);
    for (var i = 0; i < stops.length; i++) g.addColorStop(stops[i][0], stops[i][1]);
    return g;
  }

  function sky(ctx, stops) {
    ctx.fillStyle = gradient(ctx, 0, H, stops);
    ctx.fillRect(0, 0, W, H);
  }

  // rgb = "255,214,150" : le dégradé s'estompe vers la même teinte, sans halo gris.
  function glow(ctx, x, y, r, rgb, alpha) {
    var g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, "rgba(" + rgb + "," + alpha + ")");
    g.addColorStop(1, "rgba(" + rgb + ",0)");
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }

  // Ligne de crête par déplacement du point milieu.
  function ridge(rand, base, rough, steps) {
    var pts = [base + (rand() - 0.5) * rough, base + (rand() - 0.5) * rough];
    var amp = rough;
    for (var s = 0; s < steps; s++) {
      var next = [];
      for (var i = 0; i < pts.length - 1; i++) {
        next.push(pts[i], (pts[i] + pts[i + 1]) / 2 + (rand() - 0.5) * amp);
      }
      next.push(pts[pts.length - 1]);
      pts = next;
      amp *= 0.55;
    }
    return pts;
  }

  function fillRidge(ctx, pts, fill) {
    ctx.beginPath();
    ctx.moveTo(0, H);
    for (var i = 0; i < pts.length; i++) ctx.lineTo((i / (pts.length - 1)) * W, pts[i]);
    ctx.lineTo(W, H);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
  }

  function smoothHills(ctx, rand, base, amp, fill) {
    var a = rand() * 6, b = rand() * 6, f1 = 1.5 + rand() * 2, f2 = 4 + rand() * 3;
    ctx.beginPath();
    ctx.moveTo(0, H);
    for (var x = 0; x <= W; x += 16) {
      var t = x / W;
      ctx.lineTo(x, base + Math.sin(t * f1 * Math.PI + a) * amp + Math.sin(t * f2 * Math.PI + b) * amp * 0.35);
    }
    ctx.lineTo(W, H);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
  }

  function pines(ctx, rand, baseY, count, minH, maxH, color) {
    ctx.fillStyle = color;
    for (var i = 0; i < count; i++) {
      var x = rand() * W, h = minH + rand() * (maxH - minH), w = h * 0.28;
      var y = baseY + rand() * 18;
      ctx.beginPath();
      for (var k = 0; k < 4; k++) { // étages de branches
        var top = y - h + (h * k) / 4.6, wid = w * (0.45 + k * 0.2);
        ctx.moveTo(x, top);
        ctx.lineTo(x - wid, top + h * 0.34);
        ctx.lineTo(x + wid, top + h * 0.34);
        ctx.closePath();
      }
      ctx.fill();
      ctx.fillRect(x - w * 0.05, y - h * 0.15, w * 0.1, h * 0.17);
    }
  }

  function stars(ctx, rand, n, maxY) {
    for (var i = 0; i < n; i++) {
      ctx.fillStyle = "rgba(255,255,255," + (0.3 + rand() * 0.7).toFixed(2) + ")";
      var r = rand() < 0.08 ? 1.8 : 1;
      ctx.fillRect(rand() * W, rand() * maxY, r, r);
    }
  }

  function mist(ctx, y, h, color) {
    ctx.fillStyle = gradient(ctx, y - h, y + h, [[0, "rgba(0,0,0,0)"], [0.5, color], [1, "rgba(0,0,0,0)"]]);
    ctx.fillRect(0, y - h, W, h * 2);
  }

  var list = [
    { name: "Montagnes à l'aube", draw: function (ctx, rand) {
      sky(ctx, [[0, "#2b3a67"], [0.38, "#c56b84"], [0.62, "#f6a96b"], [1, "#fde2b8"]]);
      glow(ctx, 1240, 560, 420, "255,214,150", .75);
      var layers = [["#7b5a7e", 520, 260], ["#5d4570", 600, 230], ["#3f3159", 690, 200], ["#271f3d", 790, 170], ["#15122a", 900, 120]];
      for (var i = 0; i < layers.length; i++) {
        fillRidge(ctx, ridge(rand, layers[i][1], layers[i][2], 7), layers[i][0]);
        if (i < 3) mist(ctx, layers[i][1] + 120, 70, "rgba(255,200,170,.18)");
      }
    }},
    { name: "Lac en forêt", draw: function (ctx, rand) {
      sky(ctx, [[0, "#0f2a44"], [0.45, "#3d6f8f"], [0.6, "#9cc3c9"], [1, "#0b1c26"]]);
      fillRidge(ctx, ridge(rand, 470, 160, 7), "#2f5568");
      mist(ctx, 560, 60, "rgba(220,235,240,.25)");
      pines(ctx, rand, 640, 140, 60, 150, "#173342");
      var shore = Math.floor(rand() * 1e6) + 1;
      pines(ctx, rng(shore), 660, 70, 120, 260, "#0d2230");
      // lac et reflet
      ctx.fillStyle = gradient(ctx, 660, H, [[0, "#2a5266"], [1, "#07141c"]]);
      ctx.fillRect(0, 660, W, H - 660);
      ctx.save();
      ctx.globalAlpha = 0.28;
      ctx.translate(0, 1320);
      ctx.scale(1, -1);
      pines(ctx, rng(shore), 660, 70, 120, 260, "#0d2230");
      ctx.restore();
      for (var i = 0; i < 160; i++) {
        ctx.fillStyle = "rgba(200,225,235," + (rand() * 0.18).toFixed(2) + ")";
        ctx.fillRect(rand() * W, 680 + rand() * 400, 40 + rand() * 160, 2);
      }
    }},
    { name: "Océan au couchant", draw: function (ctx, rand) {
      sky(ctx, [[0, "#1d2b53"], [0.35, "#7e4a88"], [0.55, "#ff8a5b"], [0.62, "#ffcf8a"], [1, "#0d1730"]]);
      glow(ctx, 960, 640, 520, "255,190,120", .55);
      ctx.fillStyle = "#ffe2b0";
      ctx.beginPath(); ctx.arc(960, 650, 70, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = gradient(ctx, 660, H, [[0, "#3c3e6e"], [0.4, "#1d2448"], [1, "#0a0f24"]]);
      ctx.fillRect(0, 660, W, H - 660);
      for (var i = 0; i < 260; i++) {
        var y = 665 + Math.pow(rand(), 1.6) * 415, spread = 80 + (y - 660) * 1.1;
        var x = 960 + (rand() - 0.5) * spread * 2, w = 10 + rand() * 60 * (y - 640) / 200;
        ctx.fillStyle = "rgba(255,200,140," + (0.15 + rand() * 0.5).toFixed(2) + ")";
        ctx.fillRect(x, y, w, 2 + (y - 660) / 160);
      }
      fillRidge(ctx, ridge(rand, 980, 40, 6), "#05070f");
    }},
    { name: "Aurore boréale", draw: function (ctx, rand) {
      sky(ctx, [[0, "#020611"], [0.6, "#0a1c2e"], [1, "#122a3a"]]);
      stars(ctx, rand, 700, 760);
      ctx.globalCompositeOperation = "lighter";
      for (var band = 0; band < 3; band++) {
        var y0 = 230 + band * 90, ph = rand() * 6;
        for (var x = 0; x < W; x += 6) {
          var y = y0 + Math.sin(x / 260 + ph) * 70 + Math.sin(x / 90 + ph * 2) * 18;
          var h = 160 + Math.sin(x / 140 + ph) * 90;
          var g = ctx.createLinearGradient(0, y - h, 0, y + 40);
          g.addColorStop(0, "rgba(120,80,200,0)");
          g.addColorStop(0.6, "rgba(60,230,160,.13)");
          g.addColorStop(1, "rgba(80,255,170,0)");
          ctx.fillStyle = g;
          ctx.fillRect(x, y - h, 6, h + 40);
        }
      }
      ctx.globalCompositeOperation = "source-over";
      fillRidge(ctx, ridge(rand, 760, 160, 7), "#1d3346");
      smoothHills(ctx, rand, 880, 40, "#b9cad6");
      smoothHills(ctx, rand, 960, 30, "#e3edf2");
      pines(ctx, rand, 950, 40, 80, 180, "#0a1520");
    }},
    { name: "Dunes", draw: function (ctx, rand) {
      sky(ctx, [[0, "#3f7fb5"], [0.5, "#a9cbe0"], [0.62, "#f4d9b0"], [1, "#e9a868"]]);
      glow(ctx, 1500, 380, 300, "255,245,220", .6);
      var cols = [["#e8b47c", "#c98a52"], ["#dca069", "#b47240"], ["#cf8d55", "#9c5d31"], ["#c07a44", "#7f4724"]];
      for (var i = 0; i < cols.length; i++) {
        smoothHills(ctx, rand, 620 + i * 110, 70 - i * 8, gradient(ctx, 520 + i * 110, H, [[0, cols[i][0]], [1, cols[i][1]]]));
      }
    }},
    { name: "Collines dans la brume", draw: function (ctx, rand) {
      sky(ctx, [[0, "#a7c4cf"], [0.6, "#e6eee9"], [1, "#d7e4da"]]);
      var cols = ["#9fb8b0", "#7f9e93", "#5f8476", "#456b5b", "#2f5141", "#1f3a2d"];
      for (var i = 0; i < cols.length; i++) {
        smoothHills(ctx, rand, 480 + i * 100, 60 + i * 6, cols[i]);
        mist(ctx, 560 + i * 100, 50, "rgba(240,245,240,.35)");
        if (i >= 3) pines(ctx, rand, 520 + i * 105, 16, 40 + i * 10, 90 + i * 20, cols[i]);
      }
    }}
  ];

  function render(index) {
    var canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    list[index].draw(canvas.getContext("2d"), rng(1009 * (index + 1)));
    return canvas;
  }

  return { count: list.length, name: function (i) { return list[i].name; }, render: render };
})();
