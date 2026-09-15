// Pointer-reactive particle field behind the app, ported from the Claude Design
// redesign's own canvas logic. Purely decorative: the canvas is aria-hidden and
// pointer-events:none, and the whole animation collapses to a static grid when
// the visitor asks for reduced motion.
//
// Dash serves everything in assets/ automatically, and re-runs this file only on
// a full page load -- client-side navigation between /, and /dashboard keeps the
// same canvas, so the loop is started once and left alone.
(function () {
  'use strict';

  var started = false;

  function start(canvas) {
    if (started) return;
    started = true;

    var ctx = canvas.getContext('2d');
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var w = 0, h = 0, dpr = 1;
    var pointer = { x: -9999, y: -9999, ex: -9999, ey: -9999, seen: false };
    var ripples = [];
    var last = { x: -9999, y: -9999 };
    var t = 0;

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function onMove(e) {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
      if (!pointer.seen) { pointer.ex = pointer.x; pointer.ey = pointer.y; pointer.seen = true; }
      var d = Math.hypot(pointer.x - last.x, pointer.y - last.y);
      if (d > 110 && ripples.length < 22) {
        ripples.push({ x: pointer.x, y: pointer.y, r: 6, max: 190 + Math.random() * 120,
                       warm: Math.random() < 0.32 });
        last = { x: pointer.x, y: pointer.y };
      }
    }

    function onDown(e) {
      ripples.push({ x: e.clientX, y: e.clientY, r: 8, max: 420, warm: true });
      ripples.push({ x: e.clientX, y: e.clientY, r: 8, max: 260, warm: false });
    }

    function onLeave() { pointer.x = -9999; pointer.y = -9999; }

    var SPACING = 46, REACH = 190;

    function draw() {
      t += 1;
      ctx.clearRect(0, 0, w, h);
      pointer.ex += (pointer.x - pointer.ex) * 0.085;
      pointer.ey += (pointer.y - pointer.ey) * 0.085;

      if (pointer.seen && pointer.x > -9000) {
        var g = ctx.createRadialGradient(pointer.ex, pointer.ey, 0, pointer.ex, pointer.ey, 340);
        g.addColorStop(0, 'rgba(122, 86, 170, 0.16)');
        g.addColorStop(0.45, 'rgba(96, 66, 138, 0.06)');
        g.addColorStop(1, 'rgba(19, 16, 25, 0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }

      var cols = Math.ceil(w / SPACING) + 1;
      var rowsN = Math.ceil(h / SPACING) + 1;
      for (var i = 0; i < cols; i++) {
        for (var j = 0; j < rowsN; j++) {
          var bx = i * SPACING, by = j * SPACING;
          var drift = reduce ? 0 : Math.sin(t * 0.012 + i * 0.5 + j * 0.32) * 1.6;
          var dx = bx - pointer.ex, dy = by - pointer.ey;
          var dist = Math.hypot(dx, dy);
          var px = bx, py = by + drift, r = 1, a = 0.16, warm = 0;
          if (dist < REACH) {
            var f = 1 - dist / REACH;
            var push = f * f * 16;
            var inv = dist || 1;
            px = bx + (dx / inv) * push;
            py = by + drift + (dy / inv) * push;
            r = 1 + f * 1.7;
            a = 0.16 + f * 0.5;
            warm = f;
          }
          ctx.beginPath();
          ctx.arc(px, py, r, 0, Math.PI * 2);
          ctx.fillStyle = warm > 0.02
            ? 'rgba(' + Math.round(181 + (217 - 181) * warm) + ',' +
                        Math.round(140 + (163 - 140) * warm) + ',' +
                        Math.round(232 + (95 - 232) * warm) + ',' + a.toFixed(3) + ')'
            : 'rgba(181,140,232,' + a.toFixed(3) + ')';
          ctx.fill();
        }
      }

      for (var k = ripples.length - 1; k >= 0; k--) {
        var rp = ripples[k];
        rp.r += reduce ? 4.5 : 2.4;
        var life = 1 - rp.r / rp.max;
        if (life <= 0) { ripples.splice(k, 1); continue; }
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, rp.r, 0, Math.PI * 2);
        ctx.lineWidth = 1;
        ctx.strokeStyle = rp.warm
          ? 'rgba(217,163,95,' + (life * 0.3).toFixed(3) + ')'
          : 'rgba(181,140,232,' + (life * 0.26).toFixed(3) + ')';
        ctx.stroke();
      }

      window.requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
    document.addEventListener('pointerleave', onLeave);
    window.requestAnimationFrame(draw);
  }

  // Dash renders the layout after this script runs, so wait for the canvas.
  function poll() {
    var canvas = document.getElementById('backdrop');
    if (canvas) { start(canvas); return; }
    window.setTimeout(poll, 120);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', poll);
  } else {
    poll();
  }
})();
