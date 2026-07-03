/* ===== VRAI LIQUID GLASS : distorsion refractive SVG (feDisplacementMap) =====
   Port fidele du mecanisme de shuding/liquid-glass (SDF de bord arrondi -> texture de
   deplacement -> feDisplacementMap applique via backdrop-filter). Ce n'est PAS juste du
   flou (blur/saturate ne peuvent pas deformer geometriquement le pixel) : ici le fond
   derriere la carte est vraiment refracte/grossi pres des bords, comme un vrai verre.
   Applique sur .layer (cartes bento) et .glass (panels) sans toucher a preserve-3d ni a
   la parallaxe existante (le filtre SVG est un backdrop-filter EN PLUS, sur l'element,
   il ne touche pas au transform du parent .bento-3d).
   Cree : Jordan VINCENT (NetroIA) avec Claude. 2026-07-03. */
(function () {
  'use strict';

  function smoothStep(a, b, t) {
    t = Math.max(0, Math.min(1, (t - a) / (b - a)));
    return t * t * (3 - 2 * t);
  }
  function length(x, y) { return Math.sqrt(x * x + y * y); }
  function roundedRectSDF(x, y, width, height, radius) {
    const qx = Math.abs(x) - width + radius;
    const qy = Math.abs(y) - height + radius;
    return Math.min(Math.max(qx, qy), 0) + length(Math.max(qx, 0), Math.max(qy, 0)) - radius;
  }

  let _uid = 0;

  /* Genere la texture de deplacement (canvas -> dataURL) pour UNE taille donnee,
     avec un rayon de bord relatif ~ border-radius de l'element. */
  function _buildDisplacementDataURL(w, h, edgeRadius) {
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d');
    const data = new Uint8ClampedArray(w * h * 4);
    let maxScale = 0;
    const raw = [];
    for (let i = 0; i < data.length; i += 4) {
      const x = (i / 4) % w;
      const y = Math.floor(i / 4 / w);
      const ix = (x / w) - 0.5, iy = (y / h) - 0.5;
      const dist = roundedRectSDF(ix, iy, 0.32, 0.32, edgeRadius);
      const displacement = smoothStep(0.72, 0, dist - 0.14);
      const scaled = smoothStep(0, 1, displacement);
      const px = ix * scaled + 0.5, py = iy * scaled + 0.5;
      const dx = px * w - x, dy = py * h - y;
      maxScale = Math.max(maxScale, Math.abs(dx), Math.abs(dy));
      raw.push(dx, dy);
    }
    maxScale = Math.max(maxScale * 0.55, 1);
    let idx = 0;
    for (let i = 0; i < data.length; i += 4) {
      const r = raw[idx++] / maxScale + 0.5;
      const g = raw[idx++] / maxScale + 0.5;
      data[i] = r * 255; data[i + 1] = g * 255; data[i + 2] = 0; data[i + 3] = 255;
    }
    ctx.putImageData(new ImageData(data, w, h), 0, 0);
    return { url: canvas.toDataURL(), scale: maxScale };
  }

  /* Cree un <filter> SVG unique dans un <svg> global cache, retourne son id. */
  let _svgRoot = null;
  function _svgDefs() {
    if (_svgRoot) return _svgRoot;
    _svgRoot = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    _svgRoot.setAttribute('width', '0');
    _svgRoot.setAttribute('height', '0');
    _svgRoot.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;pointer-events:none';
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    _svgRoot.appendChild(defs);
    document.body.appendChild(_svgRoot);
    return _svgRoot;
  }

  function applyLiquidGlass(el, opts) {
    if (!el || el.dataset.liquidGlass) return;
    el.dataset.liquidGlass = '1';
    opts = opts || {};
    const edgeRadius = opts.edgeRadius != null ? opts.edgeRadius : 0.55;

    function build() {
      const r = el.getBoundingClientRect();
      const w = Math.max(40, Math.round(r.width));
      const h = Math.max(40, Math.round(r.height));
      if (!w || !h) return;
      const { url, scale } = _buildDisplacementDataURL(w, h, edgeRadius);

      const defs = _svgDefs().querySelector('defs');
      let filterId = el.dataset.liquidGlassFilterId;
      let filter, feImage, feDisp;
      if (filterId) {
        filter = defs.querySelector('#' + filterId);
        feImage = filter.querySelector('feImage');
        feDisp = filter.querySelector('feDisplacementMap');
      } else {
        filterId = 'lg-filter-' + (_uid++);
        el.dataset.liquidGlassFilterId = filterId;
        filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.setAttribute('id', filterId);
        filter.setAttribute('filterUnits', 'userSpaceOnUse');
        filter.setAttribute('colorInterpolationFilters', 'sRGB');
        filter.setAttribute('x', '0'); filter.setAttribute('y', '0');
        feImage = document.createElementNS('http://www.w3.org/2000/svg', 'feImage');
        feDisp = document.createElementNS('http://www.w3.org/2000/svg', 'feDisplacementMap');
        feDisp.setAttribute('in', 'SourceGraphic');
        feDisp.setAttribute('in2', filterId + '_map');
        feDisp.setAttribute('xChannelSelector', 'R');
        feDisp.setAttribute('yChannelSelector', 'G');
        feImage.setAttribute('id', filterId + '_map');
        filter.appendChild(feImage);
        filter.appendChild(feDisp);
        defs.appendChild(filter);
        el.style.backdropFilter = 'url(#' + filterId + ') blur(3px) saturate(150%)';
        el.style.webkitBackdropFilter = 'url(#' + filterId + ') blur(3px) saturate(150%)';
      }
      filter.setAttribute('width', w); filter.setAttribute('height', h);
      feImage.setAttribute('width', w); feImage.setAttribute('height', h);
      feImage.setAttributeNS('http://www.w3.org/1999/xlink', 'href', url);
      feDisp.setAttribute('scale', scale.toFixed(1));
    }

    build();
    let raf = null;
    const onResize = function () {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(build);
    };
    window.addEventListener('resize', onResize, { passive: true });
    if (window.ResizeObserver) {
      new ResizeObserver(onResize).observe(el);
    }
  }

  /* Applique automatiquement sur toutes les cartes bento + panels glass presents/futurs.
     Cible large volontairement restreinte : uniquement .layer et .panel.glass (pas les
     petits elements comme boutons/toggles, ou le cout de generation de texture par element
     serait inutile et le rendu visuel n'y gagnerait rien). */
  function scanAndApply() {
    document.querySelectorAll('.layer:not([data-liquid-glass])').forEach(function (el) {
      applyLiquidGlass(el, { edgeRadius: 0.6 });
    });
    document.querySelectorAll('.panel.glass:not([data-liquid-glass]), .glass.panel:not([data-liquid-glass])').forEach(function (el) {
      applyLiquidGlass(el, { edgeRadius: 0.35 });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scanAndApply);
  } else {
    scanAndApply();
  }
  /* Nouvelles cartes/panels ajoutes dynamiquement (SPA sans reload) */
  new MutationObserver(function () { scanAndApply(); })
    .observe(document.body, { childList: true, subtree: true });
})();
