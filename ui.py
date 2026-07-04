"""
NEOGEN - UI : Bento 3D interactif + shader WebGL

Fond  : fragment shader GLSL (domain-warped fBm, pastels fluides), fallback gradient.
Bento : 6 onglets de nav en VRAI 3D (perspective + preserve-3d), depths varies,
        parallaxe a la souris (rotation du plan vers le curseur + float idle).
Verre : frosted SIMULE (gradients translucides + reflet specular suivant la souris).
        PAS de backdrop-filter sur les cartes : il casse preserve-3d. Sur le fond
        shader doux, rend comme du verre depoli (style UI Bento).
        Aucune dependance externe, aucun CDN.
Nav   : clic carte -> showSection(). Sections en Liquid Glass (.glass, panels 2D).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-19.
"""


def _head() -> str:
    import pathlib as _pl
    import os as _os
    _css = _pl.Path(__file__).parent / "static" / "app.css"
    _vc = int(_css.stat().st_mtime) if _css.exists() else 0
    _est_instance_perso = _os.environ.get("NEOGEN_OWNER_UNLIMITED", "").strip().lower() in ("1", "true", "yes", "on")
    # Statut Docker : utile en dev local (verifier que le moteur tourne), sans interet pour
    # un visiteur du site public - et source de confusion la ou le socket-proxy de securite
    # bloque volontairement certaines routes (INFO=0), affichant a tort "indisponible" alors
    # que l'appli fonctionne normalement (fallback isolation process).
    _docker_status_html = (
        '<div id="docker-status"><span class="dot off"></span>chargement...</div>'
        if _est_instance_perso else ''
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEOGEN</title>
<link rel="stylesheet" href="/static/app.css?v={_vc}">
<script>localStorage.setItem('neogen_ob_done','1');</script>
</head>
<body class="dark">

<!-- VIDEO BACKGROUND (fond fixe, Matrix) — dark = vert/noir, light = vert/blanc -->
<video id="bg-video" autoplay loop muted playsinline>
  <source src="/static/video-logo-matrix.mp4" type="video/mp4">
</video>
<video id="bg-video-light-1" autoplay loop muted playsinline>
  <source src="/static/video-matrix-light.mp4" type="video/mp4">
</video>
<video id="bg-video-light-2" autoplay loop muted playsinline>
  <source src="/static/video-matrix-light-2.mp4" type="video/mp4">
</video>
<img id="bg-logo-light" src="/static/Logo-Neogen-transparent.png" alt="" aria-hidden="true">
<div id="bg-vignette"></div>

<header>
  <h1 onclick="showLanding()">NEO<b>GEN</b></h1>
  {_docker_status_html}
</header>

<div id="breadcrumb" class="breadcrumb" onclick="showLanding()">
  <span style="font-size:16px">←</span>
  <span id="bc-label">Accueil</span>
</div>
"""


def _sidebar() -> str:
    return r"""<!-- SIDEBAR (flottant, visible en mode section) -->
<nav class="sidebar" id="sidebar">
  <!-- Cascade Matrix (derriere les nav items) -->
  <video id="cascade-video" autoplay loop muted playsinline>
    <source src="/static/video-cascade-matrix.mp4" type="video/mp4">
  </video>
  <div class="side-home" onclick="showLanding()">
    <span class="side-back">←</span>
    <span class="side-title">NEO<b>GEN</b></span>
  </div>
  <div class="side-item" style="--lc:#a855f7" onclick="showSection('cerveau')" id="side-cerveau">
    <span class="side-dot"></span>Cerveaux
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-creation)" onclick="showSection('creation')" id="side-creation">
    <span class="side-dot"></span>Creation
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-production)" onclick="showSection('production')" id="side-production">
    <span class="side-dot"></span>Production
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-compte)" onclick="showSection('compte')" id="side-compte">
    <span class="side-dot"></span>Compte
    <span class="side-badge live">live</span>
    <span id="gen-wallet-nav" style="display:none;margin-left:auto;font-size:11px;font-weight:700;color:#f59e0b;background:rgba(245,158,11,.12);border-radius:99px;padding:1px 8px">0 GEN</span>
  </div>
  <div class="side-item" style="--lc:var(--c-analyse)" onclick="showSection('analyse')" id="side-analyse">
    <span class="side-dot"></span>Dev &amp; Analyse
    <span class="side-badge live">live</span>
    <span id="ing-rebuild-nav" style="display:none;margin-left:auto;font-size:11px;font-weight:700;color:#f59e0b;background:rgba(245,158,11,.14);border-radius:99px;padding:1px 8px">rebuild</span>
  </div>
  <div class="side-item" style="--lc:#10b981" onclick="showSection('evolution')" id="side-evolution">
    <span class="side-dot"></span>Evolution
    <span class="side-badge live">live</span>
    <span id="evo-badge-nav" style="display:none;margin-left:auto;font-size:11px;font-weight:700;color:#10b981;background:rgba(16,185,129,.12);border-radius:99px;padding:1px 8px">0</span>
  </div>
  <div class="side-item" style="--lc:var(--c-marketing)" onclick="showSection('marketing')" id="side-marketing">
    <span class="side-dot"></span>Marketing
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-integration)" onclick="showSection('integrations')" id="side-integrations">
    <span class="side-dot"></span>Integrations
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:var(--c-don)" onclick="showSection('don')" id="side-don">
    <span class="side-dot"></span>Soutenir
    <span class="side-badge live">live</span>
  </div>
</nav>
"""


def _landing() -> str:
    return r"""<!-- LANDING -->
<div id="landing" style="visibility:hidden">
  <div class="landing-title">
    <img src="/static/Logo-Neogen-transparent.png" alt="NEOGEN" class="neogen-logo">
    <h2>NEO<b>GEN</b></h2>
    <p>Une intention devient une application gouvernee, generee et executee en conteneur durci.</p>
  </div>

  <div class="bento">
    <div class="bento-3d">

    <div class="layer" onclick="showSection('cerveau')">
      <span class="layer-marker" style="--lc:#16c65e"></span>
      <div class="layer-label"><h3>Cerveaux</h3><p>Le super-agent qui coordonne les autres et agit pour toi</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('creation')">
      <span class="layer-marker" style="--lc:var(--c-creation)"></span>
      <div class="layer-label"><h3>Creation</h3><p>Nouvelle intention, ADN co-construit, fabrication</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('production')">
      <span class="layer-marker" style="--lc:var(--c-production)"></span>
      <div class="layer-label"><h3>Production</h3><p>Catalogue des produits generes et promus</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('compte')">
      <span class="layer-marker" style="--lc:var(--c-compte)"></span>
      <div class="layer-label"><h3>Compte</h3><p>Profil, modele actif, historique, retours</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('analyse')">
      <span class="layer-marker" style="--lc:var(--c-analyse)"></span>
      <div class="layer-label"><h3>Dev &amp; Analyse</h3><p>Metriques temps reel, agent developpeur, diagnostic et forge</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('evolution')">
      <span class="layer-marker" style="--lc:#10b981"></span>
      <div class="layer-label"><h3>Evolution</h3><p>Hub du savoir : 5 silos unifies, propositions d'amelioration</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('marketing')">
      <span class="layer-marker" style="--lc:var(--c-marketing)"></span>
      <div class="layer-label"><h3>Marketing</h3><p>Strategie reseaux, copywriting, campagnes, visuels et videos IA</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('integrations')">
      <span class="layer-marker" style="--lc:var(--c-integration)"></span>
      <div class="layer-label"><h3>Integrations</h3><p>Modele IA, outils tiers, API personnalisees</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('don')">
      <span class="layer-marker" style="--lc:var(--c-don)"></span>
      <div class="layer-label"><h3>Soutenir</h3><p>Financer le calcul et le developpement</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    </div>
  </div>
</div>
"""


def _section_creation() -> str:
    return r"""<!-- CREATION : Studio A->Z -->
<div id="section-creation" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-creation)"></span>Creation</h2>
    <p>Construis ton produit etape par etape : intention, ADN, capacites, forge en direct.</p>
  </div>
  <div class="agent-chat-mount" data-agent="createur" data-titre="🔨 Le Forgeron" data-sub="Decris ton projet (app, SaaS, gadget), je le cree de A a Z."></div>

  <!-- Rail des etapes -->
  <div class="studio-rail" id="studio-rail">
    <div class="srail-step active" data-step="1"><span class="srail-num">1</span><span class="srail-lbl">Intention</span></div>
    <div class="srail-step" data-step="2"><span class="srail-num">2</span><span class="srail-lbl">ADN</span></div>
    <div class="srail-step" data-step="3"><span class="srail-num">3</span><span class="srail-lbl">Composition</span></div>
    <div class="srail-step" data-step="4"><span class="srail-num">4</span><span class="srail-lbl">Production</span></div>
    <div class="srail-step" data-step="5"><span class="srail-num">5</span><span class="srail-lbl">Forge</span></div>
  </div>

  <!-- ETAPE 1 : Intention + discernement -->
  <div class="studio-step active panel glass" data-step="1">
    <div class="step-title">Decris ton intention</div>
    <textarea id="intention" placeholder="Ex : un convertisseur de temperature celsius / fahrenheit"></textarea>
    <div class="row" style="margin-top:14px">
      <button id="btn-scan">Scanner l'intention</button>
      <button id="btn-conseils">Conseils (conformite)</button>
    </div>
    <div class="row" style="margin-top:8px;gap:8px">
      <button id="btn-openlegi" class="ghost" style="font-size:12px;padding:6px 12px">⊜ OpenLegi (Legifrance)</button>
      <button id="btn-notebooklm" class="ghost" style="font-size:12px;padding:6px 12px" onclick="ouvrirNotebookLM()">◫ NotebookLM</button>
    </div>
    <div id="outils-actifs-banner" class="outils-actifs hidden"></div>
    <div id="stale-notice" class="hidden" style="margin-top:8px;padding:5px 12px;border-radius:8px;
      background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.25);
      font-size:12px;color:var(--warn);display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      Intention modifiee &mdash; resultats anterieurs ci-dessous
      <button id="btn-reanalyse" style="padding:3px 10px;font-size:12px">&#8635; Refaire l'analyse</button>
    </div>
    <div id="discernement" class="hidden"></div>
    <div id="conseil-box" class="hidden"></div>
    <div id="openlegi-box" class="hidden"></div>
    <div id="scan-status"></div>
    <div class="step-nav">
      <span></span>
      <button id="to-step2" class="hidden">Composer l'ADN &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 2 : Bulles de murs (ADN) -->
  <div class="studio-step panel glass" data-step="2">
    <div class="step-title">Genere l'ADN : choisis les murs de gouvernance</div>
    <p class="step-help">L'organisme propose des murs. Garde les indispensables, ajoute ou retire selon ton projet.</p>
    <div class="bulle-zone" id="bulles-murs"></div>
    <div class="bulle-add">
      <span class="bulle-add-lbl">Ajouter un mur :</span>
      <div id="bulles-dispo" class="bulle-dispo-row"></div>
      <div class="bulle-custom-add">
        <input type="text" id="mur-custom-input" placeholder="Definir un mur personnalise...">
        <button class="ghost" id="btn-add-custom-mur">+ Ajouter</button>
      </div>
    </div>
    <div class="caps-bulles" id="bulles-caps"></div>
    <div class="step-nav">
      <button class="ghost" data-goto="1">&lsaquo; Retour</button>
      <button id="to-step3">Valider l'ADN &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 3 : Composition -->
  <div class="studio-step panel glass" data-step="3">
    <div class="step-title">Composition de l'ADN</div>
    <div id="composition-box"><div class="step-help">Chargement...</div></div>
    <div class="step-nav">
      <button class="ghost" data-goto="2">&lsaquo; Retour</button>
      <button id="to-step4">Configurer la production &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 4 : Production (capacites) -->
  <div class="studio-step panel glass" data-step="4">
    <div class="step-title">Production : capacites et puissance</div>
    <p class="step-help">Active uniquement ce dont le projet a besoin. Plus de puissance = plus de cout.</p>
    <div class="cap-choices">
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="juger" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Mode juge</span>
          <span class="cap-useful" id="useful-juger"></span>
        </div>
        <div class="cap-card-desc">Genere 2 strategies et garde la meilleure. Plus lent, plus robuste.</div>
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="deleguer" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Mode delegation</span>
          <span class="cap-useful" id="useful-deleguer"></span>
        </div>
        <div class="cap-card-desc">L'orchestrateur decompose en organes et delegue chacun a un sous-agent au tier adapte (fort/moyen/leger). Gouverne, visible en direct.</div>
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="persistance" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Persistance</span>
          <span class="cap-useful" id="useful-persistance"></span>
        </div>
        <div class="cap-card-desc">Un espace disque isole et jetable (volume dedie). Pour coffre, journal, sauvegarde.</div>
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="reseau" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Reseau</span>
          <span class="cap-useful" id="useful-reseau"></span>
        </div>
        <div class="cap-card-desc">Sortie reseau limitee a une liste blanche de domaines. Aucun autre acces.</div>
        <input type="text" id="domaines" class="hidden" placeholder="domaines autorises, separes par virgule">
      </div>
      <div class="cap-card">
        <div class="cap-card-head">
          <label class="toggle-wrap"><input type="checkbox" id="bureau" class="toggle-inp"><span class="toggle-pill"></span></label>
          <span class="cap-card-name">Bureau (RPA)</span>
          <span class="cap-useful" id="useful-bureau"></span>
        </div>
        <div class="cap-card-desc">Piloter le clavier et la souris de l'hote via l'agent local (RPA / computer-use).</div>
      </div>
    </div>
    <div class="row" style="margin-top:6px">
      <label style="color:var(--mut);font-size:13px;display:flex;align-items:center;gap:6px">
        tentatives d'auto-reparation <input type="number" id="max" value="2" min="1" max="5">
      </label>
      <span class="power-gauge" id="power-gauge"></span>
    </div>
    <div class="step-nav">
      <button class="ghost" data-goto="3">&lsaquo; Retour</button>
      <button id="btn-forger">Lancer la forge (ultracode) &rsaquo;</button>
    </div>
  </div>

  <!-- ETAPE 5 : Forge en direct (SSE) -->
  <div class="studio-step panel glass" data-step="5">
    <div class="step-title">Forge en direct</div>
    <div class="forge-flow" id="forge-flow"></div>
    <div id="deleg-flow" class="deleg-flow hidden"></div>
    <div id="strategies-dual" class="strategies-dual hidden"></div>
    <div id="forge-result"></div>
    <pre id="code-creation" class="code hidden"></pre>
    <div class="step-nav">
      <button class="ghost" id="btn-recommencer">Produire</button>
      <button id="btn-voir-catalogue" class="hidden">Archiver &rsaquo;</button>
    </div>
  </div>
</div>
"""


def _section_cerveau() -> str:
    """Marqueur vide : le contenu est genere en JS par renderCerveau() (static/app.js),
    appele depuis showSection('cerveau'), pour permettre la traduction via t(). Le
    marqueur <div id="section-cerveau"> reste ici pour que forge_fragments.py puisse
    toujours y injecter des fragments generes (systeme d'ancres, cf. ui.py::rendre_page)."""
    return r"""<!-- CERVEAUX : super-agent orchestrateur (contenu injecte par renderCerveau() en JS) -->
<div id="section-cerveau" class="section"></div>
"""


def _section_production() -> str:
    """Marqueur vide : le contenu est genere en JS par renderProduction() (static/app.js),
    appele depuis showSection('production'), pour permettre la traduction via t()."""
    return r"""<!-- PRODUCTION (contenu injecte par renderProduction() en JS) -->
<div id="section-production" class="section"></div>
"""


def _section_compte() -> str:
    return r"""<!-- COMPTE -->
<div id="section-compte" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-compte)"></span>Compte</h2>
    <p>Ton profil, modele actif et historique de production.</p>
  </div>
  <!-- Wallet Genyte (GEN) -->
  <div class="panel glass" style="margin-bottom:18px" id="gen-wallet-panel">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Portefeuille Genyte</div>
      <span id="gen-wallet-badge" style="font-size:18px;font-weight:800;color:#f59e0b">— GEN</span>
    </div>
    <div id="gen-wallet-detail" style="font-size:12px;color:var(--mut)">Connecte-toi pour voir ton solde.</div>
    <div id="gen-wallet-history" style="margin-top:10px"></div>
  </div>

  <!-- Quotas freemium : compteurs visibles -->
  <div class="panel glass" style="margin-bottom:18px" id="quotas-panel">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Ton plan</div>
      <span id="quotas-badge"></span>
    </div>
    <div id="quotas-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
    <div id="quotas-cta" style="margin-top:12px"></div>
  </div>

  <!-- Tarifs multi-paliers -->
  <div class="panel glass" style="margin-bottom:18px" id="tarifs-panel">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Passer au niveau superieur</div>
    <div style="display:flex;gap:6px;margin-bottom:14px" id="tarif-period-toggle">
      <button class="ghost tarif-period active" data-period="mensuel" style="flex:1;font-size:12px;padding:5px 0">Mensuel</button>
      <button class="ghost tarif-period" data-period="annuel" style="flex:1;font-size:12px;padding:5px 0">Annuel <span style="color:#10b981;font-size:10px;font-weight:700">-30%</span></button>
    </div>
    <div id="tarifs-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px"></div>
    <div style="font-size:11px;color:var(--mut);margin-top:10px;text-align:center">Essai 7j gratuit avec CB. Annulable a tout moment.</div>
  </div>

  <!-- Packs GEN -->
  <div class="panel glass" style="margin-bottom:18px" id="packs-gen-panel">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Recharger des Genyte (GEN)</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px" id="packs-grid">
      <button class="ghost pack-btn" data-pack="starter" style="display:flex;flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">100 GEN</span><span style="font-size:11px;opacity:.7">Starter — 2&#8364;</span></button>
      <button class="ghost pack-btn" data-pack="pro" style="display:flex;flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">500 GEN</span><span style="font-size:11px;opacity:.7">Pro — 8&#8364; <span style="color:#10b981">-20%</span></span></button>
      <button class="ghost pack-btn" data-pack="power" style="display:flex;flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">1 500 GEN</span><span style="font-size:11px;opacity:.7">Power — 20&#8364; <span style="color:#10b981">-33%</span></span></button>
      <button class="ghost pack-btn" data-pack="ultimate" style="display:flex;flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">5 000 GEN</span><span style="font-size:11px;opacity:.7">Ultimate — 50&#8364; <span style="color:#10b981">-50%</span></span></button>
    </div>
  </div>

  <!-- Telemetrie RGPD -->
  <div class="panel glass" style="margin-bottom:18px" id="telemetrie-panel">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:10px">Amelioration communautaire (opt-in)</div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">Contribue a rendre NEOGEN plus intelligent. Donnees anonymisees. <b style="color:#f59e0b">+200 GEN/mois</b> si tu participes.</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap" id="tele-consent-btns">
      <button class="ghost tele-btn" data-niveau="aucun" style="font-size:12px;padding:5px 12px">Aucun</button>
      <button class="ghost tele-btn" data-niveau="erreurs" style="font-size:12px;padding:5px 12px">Erreurs only</button>
      <button class="ghost tele-btn" data-niveau="usage" style="font-size:12px;padding:5px 12px">Erreurs + usage</button>
      <button class="ghost tele-btn" data-niveau="tout" style="font-size:12px;padding:5px 12px">Tout contribuer</button>
    </div>
    <div id="tele-status" style="font-size:11px;color:var(--mut);margin-top:8px"></div>
  </div>

  <div class="agent-chat-mount" data-agent="secretaire" data-titre="📋 Le Secretaire" data-sub="Ton conseiller, administrateur et assistant au quotidien."></div>

  <!-- Mes skills : espace personnel de creation (visible a tout user connecte) -->
  <div class="panel glass" style="margin-bottom:18px;display:none" id="mes-skills-panel">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
      <span style="width:8px;height:8px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981"></span>
      <div style="font-size:13px;font-weight:700">Mes skills</div>
      <span style="font-size:11px;opacity:.5;font-weight:400">code forge, teste en sandbox, isole dans ton espace</span>
    </div>
    <div style="margin-bottom:14px;padding:12px;background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.2);border-radius:10px">
      <div style="font-size:12px;font-weight:600;margin-bottom:8px;color:#10b981">Forge un nouveau skill</div>
      <textarea id="ms-besoin" placeholder="Decris ce que tu veux que ton skill fasse (ex: convertir des dates en francais, calculer une TVA, formater du texte...)" style="width:100%;resize:vertical;min-height:64px;font-size:12px;padding:8px 10px;background:rgba(0,0,0,.25);border:1px solid rgba(16,185,129,.2);color:#e8ffe8;border-radius:8px;box-sizing:border-box" rows="3"></textarea>
      <input type="text" id="ms-titre" placeholder="Titre court (optionnel)" style="width:100%;margin-top:6px;font-size:12px;padding:7px 10px;background:rgba(0,0,0,.25);border:1px solid rgba(16,185,129,.2);color:#e8ffe8;border-radius:8px;box-sizing:border-box">
      <div style="display:flex;align-items:center;gap:8px;margin-top:8px">
        <button id="ms-forge-btn" onclick="forgerMonSkill(this)" style="font-size:12px;padding:7px 18px;background:rgba(16,185,129,.18);border:1px solid rgba(16,185,129,.5);color:#10b981;font-weight:600">Forger</button>
        <span style="font-size:10px;opacity:.45">Cle IA requise — configure-la dans Integrations</span>
      </div>
      <div id="ms-forge-erreur" style="font-size:11px;color:#ef4444;margin-top:6px;display:none"></div>
    </div>
    <div id="mes-skills-liste">
      <div style="text-align:center;padding:14px;opacity:.4;font-size:12px">Aucun skill forge. Decris un besoin ci-dessus pour commencer.</div>
    </div>
  </div>

  <div id="compte-root"></div>
</div>
"""


def _section_analyse() -> str:
    """Marqueur vide : le contenu est genere en JS par renderAnalyse() (static/app.js),
    appele depuis showSection('analyse'), pour permettre la traduction via t()."""
    return r"""<!-- DEV & ANALYSE (contenu injecte par renderAnalyse() en JS) -->
<div id="section-analyse" class="section"></div>
"""


def _section_integrations() -> str:
    """Marqueur vide : le contenu est genere en JS par renderIntegrations() (static/app.js),
    appele depuis showSection('integrations'), pour permettre la traduction via t()."""
    return r"""<!-- INTEGRATIONS (contenu injecte par renderIntegrations() en JS) -->
<div id="section-integrations" class="section"></div>
"""


def _modals() -> str:
    return r"""<!-- Modal Deploiement Hostinger -->
<div id="modal-deploy" style="display:none">
  <div class="deploy-modal-backdrop" onclick="if(event.target===this)fermerModalDeploy()">
    <div class="deploy-modal">
      <button class="dm-close" onclick="fermerModalDeploy()">✕</button>
      <h3>Deployer sur Hostinger</h3>
      <div class="dm-desc">Genere un pack statique (index.html) et prepare le deploiement vers ton domaine.</div>
      <div style="font-size:12px;color:var(--mut);margin-bottom:6px" id="deploy-produit-info"></div>
      <input type="text" id="deploy-domain" placeholder="ex: mon-outil.netroia.tech">
      <button id="btn-deploy-confirm" style="width:100%">Deployer</button>
      <div class="dm-log" id="deploy-log"></div>
      <div class="dm-status" id="deploy-status"></div>
    </div>
  </div>
</div>
"""


def _section_don() -> str:
    """Marqueur vide : le contenu est genere en JS par renderDon() (static/app.js),
    appele depuis showSection('don'), pour permettre la traduction via t()."""
    return r"""<!-- DON (contenu injecte par renderDon() en JS) -->
<div id="section-don" class="section"></div>
"""


def _foot() -> str:
    import pathlib as _pl
    _js = _pl.Path(__file__).parent / "static" / "app.js"
    _v = int(_js.stat().st_mtime) if _js.exists() else 0
    _lg = _pl.Path(__file__).parent / "static" / "liquid-glass.js"
    _vlg = int(_lg.stat().st_mtime) if _lg.exists() else 0
    _i18n = _pl.Path(__file__).parent / "static" / "i18n.js"
    _vi18n = int(_i18n.stat().st_mtime) if _i18n.exists() else 0
    return (f'<script src="/static/i18n.js?v={_vi18n}"></script>\n'
            f'<script src="/static/liquid-glass.js?v={_vlg}"></script>\n'
            f'<script src="/static/app.js?v={_v}"></script>\n</body>\n</html>\n')


def _section_evolution() -> str:
    """Marqueur vide : le contenu est genere en JS par renderEvolution() (static/app.js),
    appele depuis showSection('evolution'), pour permettre la traduction via t()."""
    return r"""<!-- EVOLUTION (contenu injecte par renderEvolution() en JS) -->
<div id="section-evolution" class="section"></div>
"""


def _section_marketing() -> str:
    """Marqueur vide : le contenu est genere en JS par renderMarketing() (static/app.js),
    appele depuis showSection('marketing'), pour permettre la traduction via t()."""
    return r"""<!-- MARKETING (contenu injecte par renderMarketing() en JS) -->
<div id="section-marketing" class="section"></div>
"""


def _section_ingenieur() -> str:
    return r"""
<div id="section-ingenieur" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:#10b981"></span>L'Ingenieur</h2>
    <p>Le developpeur autonome : il diagnostique, code ce qui manque, teste en sandbox, integre a chaud. Parle-lui ou confie-lui une tache.</p>
  </div>
  <div class="agent-chat-mount" data-agent="ingenieur" data-titre="🛠️ L'Ingenieur" data-sub="Demande-moi de coder, reparer, diagnostiquer ou rendre une fonction operationnelle. J'agis avec mes outils : je lis le code, je forge, j'ancre, je teste — je ne me contente pas de decrire."></div>

  <!-- Confier une tache directe + diagnostic instantane -->
  <div class="panel glass" style="margin-bottom:18px">
    <div class="row" style="gap:8px;flex-wrap:wrap;margin-bottom:12px">
      <input id="ing-tache-input" placeholder="Confie une tache a l'Ingenieur (ex: archive la capacite obsolete, ajoute telle fonction)…"
             style="flex:1;min-width:240px;font-size:13px;padding:10px 14px;background:rgba(0,0,0,.3);border:1px solid rgba(16,185,129,.3);border-radius:10px;color:#e2e8f0">
      <button id="ing-tache-btn" style="font-size:13px;padding:10px 18px;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.45);color:#10b981;border-radius:10px;font-weight:600;cursor:pointer">Confier</button>
      <button id="ing-diag-btn" class="ghost" style="font-size:13px;padding:10px 16px">&#128269; Diagnostic instantane</button>
    </div>
    <pre id="ing-diag-out" style="display:none;font-size:11px;line-height:1.5;white-space:pre-wrap;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:12px;max-height:300px;overflow:auto;margin:0"></pre>
  </div>

  <!-- Tableau de bord : patchs proposes, autorisations noyau (le mur), rebuild requis -->
  <div class="panel glass">
    <div style="font-size:14px;font-weight:700;margin-bottom:4px;display:flex;align-items:center;gap:8px">
      <span style="width:9px;height:9px;border-radius:50%;background:#10b981;box-shadow:0 0 10px #10b981"></span>
      Interventions
    </div>
    <div style="font-size:11px;opacity:.55;margin-bottom:12px">Patchs de code proposes, autorisations noyau a trancher (le mur), rebuild requis apres un patch de module.</div>
    <div id="ingenieur-corps" style="font-size:12px">Chargement...</div>
  </div>
</div>
"""


PAGE = (
    _head()
    + _sidebar()
    + _landing()
    + _section_creation()
    + _section_cerveau()
    + _section_production()
    + _section_compte()
    + _section_analyse()
    + _section_evolution()
    + _section_marketing()
    + _section_integrations()
    + _modals()
    + _section_don()
    + _foot()
)


# Marqueurs d'ouverture de section ou la forge de fragments injecte ses blocs (zone -> marqueur).
# Le fragment apparait en tete de la section, dans un conteneur identifiable .forge-zone.
_ANCRES_ZONES = {
    "landing":     '<div id="landing">',
    "cerveau":     '<div id="section-cerveau" class="section">',
    "production":  '<div id="section-production" class="section">',
    "compte":      '<div id="section-compte" class="section">',
    "analyse":     '<div id="section-analyse" class="section">',
    "marketing":   '<div id="section-marketing" class="section">',
    "evolution":   '<div id="section-evolution" class="section">',
    "integrations": '<div id="section-integrations" class="section">',
}


def rendre_page() -> str:
    """Rend la page AVEC les fragments forges injectes a leur zone (forge_fragments).
    Fail-closed : si l'injection ferait disparaitre une ancre d'integrite (moteur JS,
    navigation), on sert la PAGE d'origine intacte. Ne leve jamais : en cas de souci,
    l'interface d'origine est toujours servie."""
    try:
        import forge_fragments
        import noyau
    except Exception:
        return PAGE
    # Blocs permanents (forge UI Python, code source) : injectes en premier, fail-closed.
    try:
        import ui_custom
        permanents = getattr(ui_custom, "BLOCS", {}) or {}
    except Exception:
        permanents = {}
    page = PAGE
    try:
        for zone, marqueur in _ANCRES_ZONES.items():
            if marqueur not in page:
                continue
            perm = permanents.get(zone, "")
            frag = forge_fragments.fragments_pour_zone(zone)
            corps = ""
            if perm:
                ok_p, _ = noyau.presentation_sure(perm)
                if ok_p:
                    corps += f'\n<div class="forge-zone forge-permanent" data-zone="{zone}">\n{perm}\n</div>'
            if frag:
                corps += f'\n<div class="forge-zone" data-zone="{zone}" style="margin:8px 0">\n{frag}\n</div>'
            if corps:
                page = page.replace(marqueur, marqueur + corps, 1)
        ok, _ = noyau.verifier_ancres(page)
        if not ok:
            return PAGE
    except Exception:
        return PAGE
    return page
