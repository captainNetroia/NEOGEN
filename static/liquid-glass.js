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
    /* v3.7 : intensite de distorsion remontee (0.55 -> 0.85) - a 0.55 l'effet etait trop
       subtil pour se voir sur un fond a faible contraste (theme clair), meme si visible sur
       le Matrix rain vert/noir a fort contraste du dark. Remonter l'intensite aide les 2
       themes sans en degrader aucun (verifie visuellement apres coup). */
    maxScale = Math.max(maxScale * 0.85, 1);
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

  /* v3.8 (reecriture complete, fix bug critique) : l'ancienne version lisait
     `el.style.backdropFilter` juste apres l'appel synchrone a build() pour capturer
     "filterOn" - mais si build() echouait au premier appel (element cache, w/h=0) et
     retentait via requestAnimationFrame (async), cette lecture se faisait AVANT que le
     filtre n'existe reellement : filterOn valait alors '' pour toujours, capture dans la
     closure hoverOnly/IntersectionObserver, et le panel restait bloque sur le blur() simple
     a vie meme apres que le retry ait fini par reussir. Ici, filterOn est calcule a partir
     du filterId (deterministe : 'lg-filter-'+n), jamais lu depuis le style — donc valide
     que build() ait reussi du premier coup ou au 50e retry. */
  function applyLiquidGlass(el, opts) {
    if (!el || el.dataset.liquidGlass) return;
    el.dataset.liquidGlass = '1';
    opts = opts || {};
    const edgeRadius = opts.edgeRadius != null ? opts.edgeRadius : 0.55;
    const filterId = 'lg-filter-' + (_uid++);
    const filterOn = 'url(#' + filterId + ') blur(3px)';
    const filterOff = 'blur(3px)';
    let _built = false;
    let _retryCount = 0;

    function build() {
      const r = el.getBoundingClientRect();
      const w = Math.max(40, Math.round(r.width));
      const h = Math.max(40, Math.round(r.height));
      if (!r.width || !r.height) {
        /* element cache (section display:none) au moment de ce build -> pas de taille
           valide, on reessaie tant que ca n'a pas fonctionne (limite ~200 frames). */
        if (_retryCount++ < 200) requestAnimationFrame(build);
        return;
      }
      _retryCount = 0;
      const { url, scale } = _buildDisplacementDataURL(w, h, edgeRadius);
      const defs = _svgDefs().querySelector('defs');
      let filter = defs.querySelector('#' + filterId);
      let feImage, feDisp;
      if (filter) {
        feImage = filter.querySelector('feImage');
        feDisp = filter.querySelector('feDisplacementMap');
      } else {
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
      }
      filter.setAttribute('width', w); filter.setAttribute('height', h);
      feImage.setAttribute('width', w); feImage.setAttribute('height', h);
      feImage.setAttributeNS('http://www.w3.org/1999/xlink', 'href', url);
      feDisp.setAttribute('scale', scale.toFixed(1));

      if (!_built) {
        _built = true;
        el.dataset.lgFilterOn = filterOn;
        /* Perf (mesure reelle, cf. skill bento-3d-glass v3.5) : le feDisplacementMap SVG
           force le navigateur a recomposer tout ce qu'il y a DERRIERE l'element a CHAQUE
           frame. 9 cartes .layer avec le filtre actif simultanement = 60% des frames video
           perdues (GPU integre) ; filtre desactive = 4%. D'ou hoverOnly sur .layer/.plan-card
           (une seule carte distordue a la fois, jamais toutes en meme temps). */
        if (opts.hoverOnly) {
          el.style.backdropFilter = filterOff; el.style.webkitBackdropFilter = filterOff;
          el.addEventListener('pointerenter', function () {
            el.style.backdropFilter = filterOn; el.style.webkitBackdropFilter = filterOn;
          });
          el.addEventListener('pointerleave', function () {
            el.style.backdropFilter = filterOff; el.style.webkitBackdropFilter = filterOff;
          });
        } else {
          el.style.backdropFilter = filterOn; el.style.webkitBackdropFilter = filterOn;
          if (window.IntersectionObserver) {
            new IntersectionObserver(function (entries) {
              entries.forEach(function (entry) {
                el.style.backdropFilter = entry.isIntersecting ? filterOn : filterOff;
                el.style.webkitBackdropFilter = entry.isIntersecting ? filterOn : filterOff;
              });
            }, { rootMargin: '100px' }).observe(el);
          }
        }
      }
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

  /* Re-scan les panels non encore traites (section qui vient de s'activer peut contenir
     des elements ajoutes pendant qu'elle etait cachee, pas vus par le MutationObserver
     global si le fragment a ete injecte cote serveur au chargement initial). Le vrai fix
     du bug "filtre jamais applique" est dans applyLiquidGlass (filterOn deterministe,
     plus jamais lu depuis un style pas encore pose) ; ceci reste utile en filet de securite. */
  window.refreshLiquidGlass = scanAndApply;

  /* Applique automatiquement sur toutes les cartes bento + panels glass presents/futurs.
     Cible large volontairement restreinte : uniquement .layer et .panel.glass (pas les
     petits elements comme boutons/toggles, ou le cout de generation de texture par element
     serait inutile et le rendu visuel n'y gagnerait rien). */
  function scanAndApply() {
    document.querySelectorAll('.layer:not([data-liquid-glass])').forEach(function (el) {
      applyLiquidGlass(el, { edgeRadius: 0.6, hoverOnly: true });
    });
    /* v3.8 : selecteur elargi a TOUT .glass (pas seulement .panel.glass) - des elements comme
       .glass.integ-category (categories d'integrations) n'avaient ni .panel ni le scan, donc
       jamais aucun filtre pose du tout (juste le blur() de la regle CSS de base, ce qui est
       insuffisant seul, cf. lecon v3). */
    document.querySelectorAll('.glass:not([data-liquid-glass])').forEach(function (el) {
      applyLiquidGlass(el, { edgeRadius: 0.35 });
    });
    /* v3.7 : .plan-card (tarifs) avait seulement un blur() simple, jamais la vraie distorsion
       feDisplacementMap - c'est pour ca que le mode clair paraissait "plat" (le blur seul ne
       PEUT PAS produire de relief visible, peu importe l'opacite du fond derriere - cf. lecon
       deja documentee en v3 : "le blur seul donnait un rendu plat/opaque"). hoverOnly comme
       .layer (plusieurs cartes simultanees, cf. fix perf v3.5). */
    document.querySelectorAll('.plan-card:not([data-liquid-glass])').forEach(function (el) {
      applyLiquidGlass(el, { edgeRadius: 0.4, hoverOnly: true });
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
