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
    return r"""<!-- CERVEAUX : super-agent orchestrateur -->
<div id="section-cerveau" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:#a855f7"></span>Cerveaux</h2>
    <p>Le Cerveau coordonne les agents (Forgeron, Genealogiste, Secretaire), parle pour toi et agit.</p>
  </div>
  <div class="agent-chat-mount" data-agent="cerveau" data-titre="🧠 Le Cerveau" data-sub="Je comprends, je delegue aux agents et je synthetise. Demande-moi n'importe quoi."></div>

  <!-- Competences auto-creees par l'agent (skills vivants) -->
  <div class="panel glass" style="margin-top:18px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Competences apprises (skills)</div>
      <div style="display:flex;gap:6px">
        <button class="ghost" id="skills-library-btn" style="font-size:12px;padding:4px 10px">Bibliotheque</button>
        <button class="ghost" id="skills-refresh" style="font-size:12px;padding:4px 10px">Rafraichir</button>
      </div>
    </div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">Le Cerveau forge ses propres competences quand il reussit une tache reproductible. Elles deviennent invocables tout de suite.</div>
    <div id="skills-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>

  <!-- Modal bibliotheque de skills communautaires -->
  <div id="skills-lib-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;align-items:center;justify-content:center">
    <div class="glass panel" style="width:min(680px,96vw);max-height:88vh;overflow-y:auto;padding:22px 24px;position:relative">
      <button onclick="document.getElementById('skills-lib-modal').style.display='none'" style="position:absolute;top:12px;right:14px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:6px;font-size:16px;cursor:pointer;color:rgba(255,255,255,.85);padding:2px 8px;font-weight:700">&times; Fermer</button>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
        <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--mut)">Bibliotheque communautaire</div>
        <button class="ghost" style="font-size:12px;padding:4px 12px;color:var(--acc)" onclick="openPublishSkillForm()">+ Proposer un skill</button>
      </div>
      <input type="text" id="skills-lib-search" class="skill-lib-search" placeholder="Rechercher un skill..." oninput="_renderSkillsLibList(this.value)">
      <div class="skill-lib-filter" id="skills-lib-filters"></div>
      <div id="skills-lib-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
      <!-- Sous-formulaire publication -->
      <div id="skills-publish-form" style="display:none;margin-top:14px;border-top:1px solid var(--line);padding-top:14px">
        <div style="font-size:12px;font-weight:700;color:var(--mut);margin-bottom:10px;text-transform:uppercase;letter-spacing:.7px">Proposer un skill</div>
        <select id="spf-skill-select" style="width:100%;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:rgba(255,255,255,.6);color:var(--txt);margin-bottom:8px">
          <option value="">-- Choisir un skill local --</option>
        </select>
        <input type="text" id="spf-desc" placeholder="Description publique (max 200 caracteres)..." style="width:100%;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:rgba(255,255,255,.6);color:var(--txt);margin-bottom:8px;outline:none">
        <select id="spf-cat" style="width:100%;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:rgba(255,255,255,.6);color:var(--txt);margin-bottom:8px">
          <option value="General">General</option>
          <option value="Analyse">Analyse</option>
          <option value="Production">Production</option>
          <option value="RPA">RPA</option>
          <option value="Recherche">Recherche</option>
          <option value="Communication">Communication</option>
          <option value="E-commerce">E-commerce</option>
          <option value="Juridique">Juridique</option>
        </select>
        <input type="text" id="spf-tags" placeholder="Tags separes par virgule (ex: analyse,pdf,rapport)..." style="width:100%;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:rgba(255,255,255,.6);color:var(--txt);margin-bottom:10px;outline:none">
        <div style="display:flex;gap:8px">
          <button class="ghost" style="font-size:12px;flex:1" onclick="submitPublishSkill()">Proposer</button>
          <button class="ghost" style="font-size:12px;color:var(--mut)" onclick="document.getElementById('skills-publish-form').style.display='none'">Annuler</button>
        </div>
        <div id="spf-status" style="font-size:12px;margin-top:8px;color:var(--mut)"></div>
      </div>
    </div>
  </div>

  <!-- Bebe-agents custom (crees par evolution) -->
  <div class="panel glass" style="margin-top:18px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Bebe-agents crees</div>
      <button class="ghost" id="bebeagents-refresh" style="font-size:12px;padding:4px 10px">Rafraichir</button>
    </div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">Agents specialises crees par evolution gouvernee. Chaque mise a jour bumpe la version.</div>
    <div id="bebeagents-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>

  <!-- Memoire cross-session : ce que l'agent retient de toi -->
  <div class="panel glass" style="margin-top:18px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Memoire de l'agent</div>
      <button class="ghost" id="mem-refresh" style="font-size:12px;padding:4px 10px">Rafraichir</button>
    </div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">Ce que l'agent retient de toi d'une session a l'autre (preferences, projets, faits). Il s'en sert pour personnaliser ses reponses.</div>
    <div id="mem-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>

  <!-- Taches autonomes (cron : l'agent agit tout seul a intervalle) -->
  <div class="panel glass" style="margin-top:18px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut)">Taches autonomes</div>
      <button class="ghost" id="tache-add-btn" style="font-size:12px;padding:4px 10px">+ Nouvelle tache</button>
    </div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">L'agent agit tout seul a intervalle regulier (veille, rapport...). Choisis le modele : <b>local</b> (gratuit, aucun credit) ou un provider configure cote instance. Provider injoignable -> bascule auto sur local.</div>
    <div id="tache-form" class="hidden" style="margin-bottom:12px;display:flex;flex-direction:column;gap:7px">
      <input type="text" id="tache-nom" placeholder="Nom (ex: Veille quotidienne)">
      <select id="tache-agent"><option value="cerveau">Le Cerveau</option><option value="genealogiste">Le Genealogiste</option><option value="secretaire">Le Secretaire</option></select>
      <textarea id="tache-msg" rows="2" placeholder="Que doit faire l'agent ? (ex: resume l'etat de mes creations)"></textarea>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span style="font-size:12px;color:var(--mut)">Modele</span>
        <select id="tache-provider" style="font-size:12px"><option value="local">Local (gratuit)</option><option value="anthropic">Anthropic</option><option value="openai">OpenAI</option><option value="gemini">Gemini</option><option value="deepseek">DeepSeek</option><option value="mistral">Mistral</option><option value="moonshot">Kimi (Moonshot)</option></select>
        <span style="font-size:12px;color:var(--mut)">Toutes les</span>
        <input type="number" id="tache-interval" value="60" min="5" style="width:70px"><span style="font-size:12px;color:var(--mut)">min</span>
        <button id="tache-save" style="margin-left:auto;font-size:13px;padding:6px 14px">Creer</button>
      </div>
    </div>
    <div id="tache-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
  </div>
</div>
"""


def _section_production() -> str:
    return r"""<!-- PRODUCTION -->
<div id="section-production" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-production)"></span>Production</h2>
    <p>Produits generes, valides, prets a l'emploi.</p>
  </div>
  <div class="agent-chat-mount" data-agent="genealogiste" data-titre="🧬 Le Genealogiste" data-sub="Je gere, classe et explique la genetique de tes creations."></div>
  <div id="produit-filtres" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
    <button onclick="filtrerProduits('actifs')" class="filtre-btn-prod" data-filtre="actifs" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(168,85,247,.2);border:1px solid rgba(168,85,247,.5);color:#a855f7;cursor:pointer">Actives</button>
    <button onclick="filtrerProduits('tous')" class="filtre-btn-prod" data-filtre="tous" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">Toutes</button>
    <button onclick="filtrerProduits('archivees')" class="filtre-btn-prod" data-filtre="archivees" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">Archivees</button>
  </div>
  <div id="produit-grid" class="produit-grid"></div>
  <pre id="code-view" class="hidden"></pre>
</div>
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
    return r"""<!-- DEV & ANALYSE (fusionne Analyse + Ingenieur) -->
<div id="section-analyse" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-analyse)"></span>Dev &amp; Analyse</h2>
    <p>Metriques, diagnostics et developpement autonome — observer, mesurer, coder.</p>
  </div>

  <!-- Onglets -->
  <div class="prov-tabs" style="margin-bottom:18px">
    <span class="prov-tab active" data-anlz-tab="analyse" onclick="anlzTab('analyse')">📊 Analyse</span>
    <span class="prov-tab" data-anlz-tab="ingenieur" onclick="anlzTab('ingenieur')">🛠️ Ingenieur</span>
  </div>

  <!-- Pane Analyse -->
  <div data-anlz-pane="analyse">
    <div class="agent-chat-mount" data-agent="analyste" data-titre="📊 L'Analyste" data-sub="Je lis les metriques, identifie les tendances et propose des optimisations basees sur les donnees reelles."></div>
    <div class="stat-grid" id="analyse-stats"></div>
    <div class="panel glass" style="margin-bottom:18px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Auto-amelioration (l'usage nourrit le systeme)</div>
      <div id="analyse-auto"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
    </div>
    <div class="panel glass" style="margin-bottom:18px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Capacites utilisees</div>
      <div id="analyse-caps"></div>
    </div>
    <div class="panel glass">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Repartition tentatives</div>
      <div id="analyse-tentatives"></div>
    </div>
  </div>

  <!-- Pane Ingenieur -->
  <div data-anlz-pane="ingenieur" style="display:none">
    <div id="section-ingenieur">
      <div class="agent-chat-mount" data-agent="ingenieur" data-titre="🛠️ L'Ingenieur" data-sub="Demande-moi de coder, reparer, diagnostiquer ou rendre une fonction operationnelle. J'agis avec mes outils : je lis le code, je forge, j'ancre, je teste."></div>
      <div class="panel glass" style="margin-bottom:18px">
        <div class="row" style="gap:8px;flex-wrap:wrap;margin-bottom:12px">
          <input id="ing-tache-input" placeholder="Confie une tache a l'Ingenieur (ex: archive la capacite obsolete, ajoute telle fonction)..."
                 style="flex:1;min-width:240px;font-size:13px;padding:10px 14px;background:rgba(0,0,0,.3);border:1px solid rgba(16,185,129,.3);border-radius:10px;color:#e2e8f0">
          <button id="ing-tache-btn" style="font-size:13px;padding:10px 18px;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.45);color:#10b981;border-radius:10px;font-weight:600;cursor:pointer">Confier</button>
          <button id="ing-diag-btn" class="ghost" style="font-size:13px;padding:10px 16px">&#128269; Diagnostic instantane</button>
        </div>
        <pre id="ing-diag-out" style="display:none;font-size:11px;line-height:1.5;white-space:pre-wrap;background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:12px;max-height:300px;overflow:auto;margin:0"></pre>
      </div>
      <div id="ing-decisions" style="display:none;margin-bottom:18px"></div>
      <div class="panel glass">
        <div style="font-size:14px;font-weight:700;margin-bottom:4px;display:flex;align-items:center;gap:8px">
          <span style="width:9px;height:9px;border-radius:50%;background:#10b981;box-shadow:0 0 10px #10b981"></span>
          Interventions
        </div>
        <div style="font-size:11px;opacity:.55;margin-bottom:12px">Patchs de code proposes, autorisations noyau, rebuild requis apres patch de module.</div>
        <div id="ingenieur-corps" style="font-size:12px">Chargement...</div>
      </div>
    </div>
  </div>
</div>
"""


def _section_integrations() -> str:
    return r"""<!-- INTEGRATIONS -->
<div id="section-integrations" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-integration)"></span>Integrations</h2>
    <p>Connecte ton modele IA et tes comptes. NEOGEN les utilise dans les analyses et productions.</p>
  </div>
  <div class="agent-chat-mount" data-agent="connecteur" data-titre="🔌 Le Connecteur" data-sub="Je diagnostique les connexions, guide la configuration des providers IA et l agent RPA. Dis-moi ce qui ne fonctionne pas."></div>

  <!-- Modele IA multi-provider avec switch actif -->
  <div class="panel glass" style="margin-bottom:20px">
    <div class="integ-section-label">Modele IA</div>
    <div id="integ-active-bar" style="margin-bottom:12px;font-size:13px;color:var(--mut)">
      Actif : <span id="integ-active-label" style="color:var(--txt);font-weight:600">aucun</span>
    </div>
    <div class="prov-tabs" id="prov-tabs">
      <span class="prov-tab active" data-prov="anthropic">Anthropic</span>
      <span class="prov-tab" data-prov="openai">OpenAI / GPT</span>
      <span class="prov-tab" data-prov="gemini">Gemini</span>
      <span class="prov-tab" data-prov="deepseek">DeepSeek</span>
      <span class="prov-tab" data-prov="mistral">Mistral</span>
      <span class="prov-tab" data-prov="moonshot">Kimi</span>
      <span class="prov-tab" data-prov="glm">GLM-5.2</span>
      <span class="prov-tab" data-prov="local">Local</span>
    </div>
    <div class="integ-model-row">
      <select id="integ-model-select"></select>
      <div class="integ-key-wrap">
        <input type="password" id="integ-api-key">
        <span class="integ-model-dot" id="integ-model-dot"></span>
      </div>
      <button id="integ-save-btn">Verifier &amp; activer</button>
    </div>
    <div id="integ-status"></div>
  </div>

  <!-- Grille des categories (rendue par JS) -->
  <div id="integ-grid-dynamic" class="integ-grid"></div>

  <!-- Agent local RPA — statut + apprentissage par imitation -->
  <div class="panel glass rpa-panel" style="margin-top:20px">
    <div class="integ-section-label">Agent local RPA</div>
    <div class="rpa-status-bar" id="rpa-status-bar">
      <span class="rpa-status-dot disconnected" id="rpa-dot"></span>
      <span>
        <span class="rpa-status-label" id="rpa-label">Agent deconnecte</span><br>
        <span class="rpa-status-sub" id="rpa-sub">Lancer <code>python rpa_agent.py</code> sur la machine hote</span>
      </span>
      <span class="rpa-queue-badge" id="rpa-queue-badge" style="display:none">file: 0</span>
    </div>

    <!-- /remote-control : prise de controle totale -->
    <div class="integ-section-label" style="margin-top:14px">Prise de contr&#244;le (/remote-control)</div>
    <div style="display:flex;align-items:center;gap:12px;padding:6px 0 4px;flex-wrap:wrap">
      <div style="flex:1;min-width:0">
        <div style="font-size:13px;color:var(--txt)">L&#8217;agent agit sans demander &#224; chaque action</div>
        <div style="font-size:11px;color:var(--mut);margin-top:2px">En mode contr&#244;le : le consentement est automatique. Arr&#234;t d&#8217;urgence : coin haut-gauche de l&#8217;&#233;cran.</div>
      </div>
      <button id="btn-remote-control" class="ghost" style="white-space:nowrap;min-width:130px">Prendre le contr&#244;le</button>
    </div>
    <div id="remote-control-status" style="font-size:12px;min-height:16px;color:var(--mut)"></div>

    <!-- /goal : mode objectif autonome -->
    <div class="integ-section-label" style="margin-top:14px">Mode Objectif (/goal)</div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:8px">D&#233;cris ce que tu veux accomplir. L&#8217;agent analyse, collecte les infos manquantes, puis ex&#233;cute jusqu&#8217;&#224; l&#8217;objectif.</div>
    <div style="display:flex;gap:8px;align-items:flex-start">
      <textarea id="goal-input" rows="2" placeholder="Ex : Remplis ma d&#233;claration URSSAF du trimestre..." style="flex:1;resize:vertical;min-height:52px;font-size:13px;padding:8px 10px;border-radius:8px;border:1px solid var(--brd);background:var(--surface);color:var(--txt)"></textarea>
      <button id="btn-goal-launch" class="ghost" style="align-self:flex-end;white-space:nowrap">Lancer</button>
    </div>
    <div id="goal-log" style="margin-top:10px;font-size:12px;color:var(--mut);min-height:20px;white-space:pre-line;max-height:180px;overflow-y:auto"></div>

    <div class="integ-section-label" style="margin-top:14px">Apprentissage continu</div>
    <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0 4px">
      <div style="font-size:13px;color:var(--txt)">NEOGEN observe et apprend tes routines tout seul
        <span style="display:block;font-size:11px;color:var(--mut);margin-top:2px">Quand une même séquence revient, elle est enregistrée automatiquement (pas besoin de cliquer « Enregistrer »).</span>
      </div>
      <label class="dark-toggle"><input type="checkbox" id="cont-learn-cb"></label>
    </div>
    <div id="cont-learn-status" style="font-size:12px;color:var(--mut);min-height:16px"></div>

    <div class="integ-section-label" style="margin-top:14px">Enregistrement manuel</div>
    <div class="imit-controls">
      <button id="btn-imit-start" class="ghost">Enregistrer</button>
      <button id="btn-imit-stop" class="ghost" style="display:none"><span class="imit-rec-dot"></span>Stopper</button>
      <button id="btn-rpa-clear" class="ghost" title="Arrêt d'urgence : vider la file RPA" style="margin-left:auto;color:var(--ko);border-color:rgba(220,38,38,.35)">Arrêt d'urgence</button>
    </div>
    <div class="imit-list" id="imit-list">
      <div style="color:var(--mut);font-size:13px;padding:10px 0">Aucun enregistrement. Clique sur « Enregistrer » pour démarrer.</div>
    </div>
  </div>
</div>
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
    return r"""<!-- DON -->
<div id="section-don" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-don)"></span>Soutenir NEOGEN</h2>
    <p>Chaque contribution finance le calcul, le developpement et la protection IP.</p>
  </div>
  <div style="max-width:560px;margin:0 auto">
    <div class="panel glass" style="text-align:center;padding:36px 32px;margin-bottom:16px">
      <div class="ph-icon" style="font-size:52px;margin-bottom:18px">♡</div>
      <h3 style="font-size:19px;font-weight:700;margin-bottom:10px;color:var(--txt)">NEOGEN est un projet ouvert</h3>
      <p style="color:var(--mut);font-size:14px;line-height:1.75;margin-bottom:28px">
        Un organisme logiciel autonome, aligne et auto-ameliorant.<br>
        Ton soutien fait pousser le noyau.
      </p>
      <button id="btn-don-stripe" onclick="ouvrirModalDon()"
         style="display:flex;align-items:center;justify-content:center;gap:10px;
         padding:13px 24px;border-radius:12px;cursor:pointer;width:100%;
         background:rgba(219,39,119,.12);
         border:1px solid rgba(219,39,119,.35);
         color:var(--c-don);font-size:14px;font-weight:600;
         transition:background .15s"
         onmouseover="this.style.background='rgba(219,39,119,.2)'"
         onmouseout="this.style.background='rgba(219,39,119,.12)'">
        ♡ &nbsp;Soutenir
      </button>
    </div>
    <div class="panel glass" style="padding:20px 24px">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:12px">Ou va ton soutien</div>
      <div class="hist-item"><span style="font-size:16px">⚡</span><span class="hist-intention">Calcul GPU pour la generation et l'evolution</span></div>
      <div class="hist-item"><span style="font-size:16px">⊕</span><span class="hist-intention">Developpement des phases D a G (integrations, GTM, applis)</span></div>
      <div class="hist-item"><span style="font-size:16px">◈</span><span class="hist-intention">Hebergement serveur dedie et infrastructure</span></div>
    </div>
  </div>
</div>

<!-- Modal don libre -->
<div id="modal-don" style="display:none;position:fixed;inset:0;z-index:9999;
  background:rgba(15,23,42,.55);backdrop-filter:blur(6px);
  align-items:center;justify-content:center">
  <div style="background:#fff;border-radius:18px;padding:32px 28px;max-width:380px;width:92%;
    box-shadow:0 24px 64px rgba(0,0,0,.22);position:relative">
    <button onclick="fermerModalDon()" style="position:absolute;top:14px;right:16px;
      background:none;border:none;font-size:20px;cursor:pointer;color:var(--mut);
      line-height:1;padding:2px 6px">✕</button>
    <div style="text-align:center;margin-bottom:22px">
      <div style="font-size:40px;margin-bottom:8px">♡</div>
      <h3 style="font-size:17px;font-weight:700;color:var(--txt)">Choisir un montant</h3>
      <p style="font-size:13px;color:var(--mut);margin-top:5px;line-height:1.5">Don libre. Ce que tu veux, quand tu veux.</p>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px">
      <button class="don-preset" onclick="selectMontant(1,this)">1 €</button>
      <button class="don-preset" onclick="selectMontant(10,this)">10 €</button>
      <button class="don-preset" onclick="selectMontant(20,this)">20 €</button>
      <button class="don-preset" onclick="selectMontant(50,this)">50 €</button>
      <button class="don-preset" onclick="selectMontant(100,this)">100 €</button>
      <button class="don-preset" onclick="selectMontant('custom',this)">Autre +</button>
    </div>
    <div id="don-custom-wrap" style="display:none;margin-bottom:12px">
      <input id="don-custom-input" type="number" min="1" max="9999" placeholder="Montant en EUR"
        style="width:100%;padding:9px 12px;border-radius:9px;font-size:15px;text-align:center;
        border:1px solid rgba(219,39,119,.35);outline:none;color:var(--txt)"
        oninput="donCustomVal=parseInt(this.value)||0;updateDonDisplay()">
    </div>
    <div id="don-display" style="font-size:13px;color:var(--c-don);text-align:center;
      margin-bottom:16px;min-height:20px;font-weight:600"></div>
    <button id="btn-don-confirmer" onclick="confirmerDon()"
      style="width:100%;padding:12px;border-radius:11px;font-size:14px;font-weight:600;
      background:rgba(219,39,119,.12);border:1px solid rgba(219,39,119,.4);
      color:var(--c-don);cursor:pointer;transition:background .15s"
      onmouseover="this.style.background='rgba(219,39,119,.22)'"
      onmouseout="this.style.background='rgba(219,39,119,.12)'">
      Continuer vers le paiement
    </button>
    <div id="don-modal-st" style="font-size:12px;color:var(--mut);text-align:center;margin-top:10px;min-height:16px"></div>
  </div>
</div>
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
    return r"""<!-- EVOLUTION : Hub du savoir unifie -->
<div id="section-evolution" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:#10b981"></span>Evolution</h2>
    <p>Hub du savoir : 5 silos unifies. Le systeme apprend, propose, tu approuves.</p>
  </div>
  <div class="agent-chat-mount" id="evo-architecte-mount" data-agent="architecte" data-titre="🏗️ L'Architecte" data-sub="Je connais le noyau, les murs et les stores. Dis-moi ce que tu veux faire evoluer : je t'aide a formuler la bonne proposition."></div>

  <!-- Vue bridee (non-proprietaire) : le Hub complet reste reserve, mais Evolution reste
       visible et explique — avec un chemin sur vers la forge personnelle (sac isole). -->
  <div id="evo-vue-bridee" class="panel glass" style="display:none;margin-bottom:20px;border-color:rgba(16,185,129,.3)">
    <div style="font-size:14px;font-weight:700;margin-bottom:8px;color:#10b981">Evolution — vue publique</div>
    <div style="font-size:13px;line-height:1.6;opacity:.8;margin-bottom:14px">
      Cette section pilote le cerveau commun de NEOGEN (regles, agents, savoir partage entre
      tous les utilisateurs) — reservee au proprietaire de l'instance pour proteger l'integrite
      du systeme. Tu peux quand meme forger tes propres competences : elles restent isolees
      dans ton espace, invisibles et sans effet sur le reste du systeme.
    </div>
    <button id="evo-vers-mes-skills" style="font-size:13px;padding:10px 20px;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.45);color:#10b981;border-radius:10px;font-weight:600;cursor:pointer">Aller a Mes skills (Compte)</button>
  </div>

  <!-- Panneaux proprietaire (Hub complet) : un seul wrapper, cache en bloc pour un non-proprietaire. -->
  <div id="evo-panneaux-owner">
  <!-- Stats Hub -->
  <div class="panel glass" style="margin-bottom:20px">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:14px">
      <h3 style="margin:0;font-size:15px">Etat du Hub</h3>
      <button id="btn-hub-refresh" class="ghost" style="font-size:12px;padding:6px 14px">&#8635; Rafraichir</button>
    </div>
    <div id="hub-stats-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px">
      <div class="hub-stat-card" style="text-align:center;padding:12px;background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.08)">
        <div style="font-size:22px;font-weight:700;color:#10b981" id="hub-total-grains">--</div>
        <div style="font-size:11px;opacity:.6;margin-top:2px">grains total</div>
      </div>
      <div class="hub-stat-card" style="text-align:center;padding:12px;background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.08)">
        <div style="font-size:22px;font-weight:700;color:#f59e0b" id="hub-props-en-attente">--</div>
        <div style="font-size:11px;opacity:.6;margin-top:2px">propositions</div>
      </div>
      <div id="hub-silos-grid" style="display:contents"></div>
    </div>
    <div id="hub-refresh-status" style="margin-top:10px;font-size:12px;opacity:.5;display:none"></div>
  </div>

  <!-- Recherche semantique -->
  <div class="panel glass" style="margin-bottom:20px">
    <h3 style="font-size:14px;margin-bottom:12px">Recherche semantique (TF-IDF)</h3>
    <div class="row" style="gap:10px;align-items:center">
      <input id="hub-search-input" type="text" placeholder="Ex : erreur de memoire, skill python..." style="flex:1;padding:9px 14px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:13px">
      <select id="hub-search-domaine" style="padding:9px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px">
        <option value="">Tous les silos</option>
        <option value="skill">Skills</option>
        <option value="memoire">Memoire</option>
        <option value="erreur">Erreurs</option>
        <option value="amelioration">Amelioration</option>
        <option value="ledger">Ledger</option>
        <option value="telemetrie">Telemetrie</option>
      </select>
      <button id="btn-hub-search" style="padding:9px 18px">Chercher</button>
    </div>
    <div id="hub-search-results" style="margin-top:14px"></div>
  </div>

  <!-- Propositions -->
  <div class="panel glass">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:14px">
      <h3 style="margin:0;font-size:15px">Propositions d'evolution</h3>
      <span id="hub-props-count" style="font-size:12px;opacity:.5">chargement...</span>
    </div>
    <div id="hub-props-list">
      <div style="text-align:center;padding:30px;opacity:.4;font-size:13px">Cliquer sur Rafraichir pour analyser les silos</div>
    </div>
  </div>

  <!-- La Pensee : intelligence collective autonome -->
  <div class="panel glass" style="margin-top:20px">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:6px">
      <h3 style="margin:0;font-size:15px">La Pensee <span style="font-size:11px;opacity:.5;font-weight:400">&mdash; intelligence collective</span></h3>
      <span id="pensee-count" style="font-size:12px;opacity:.5">chargement...</span>
    </div>
    <p style="font-size:12px;opacity:.55;margin:0 0 14px;line-height:1.5">Les agents conversent seuls en puisant dans le savoir des silos. Idees, reflexions, reves : tout est archive ; les pensees a haut score s'affichent en bulle et deviennent des propositions.</p>

    <div class="row" style="gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px">
      <label style="font-size:12px;opacity:.7">Modele</label>
      <select id="pensee-mode" style="padding:8px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px">
        <option value="eco">Eco / local (gratuit)</option>
        <option value="fort">Fort (provider configure)</option>
        <option value="mixte">Mixte (equilibre)</option>
      </select>
      <label style="font-size:12px;opacity:.7;margin-left:6px">Intervalle</label>
      <select id="pensee-intervalle" style="padding:8px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px">
        <option value="30">30 min</option>
        <option value="60">1 h</option>
        <option value="120">2 h</option>
        <option value="240">4 h</option>
        <option value="480">8 h</option>
      </select>
      <label style="font-size:12px;opacity:.7;display:flex;align-items:center;gap:6px;margin-left:6px;cursor:pointer">
        <input type="checkbox" id="pensee-actif" style="cursor:pointer"> Active
      </label>
      <label class="eco-toggle eclair-toggle" id="pensee-eclair-toggle" title="Mode ÉCLAIR : compression intelligente du contexte — économisez 30 à 50% sur vos tokens lors des longues sessions" style="margin-left:6px">
        <input type="checkbox" id="pensee-eclrcb"><span>&#9889; ÉCLAIR</span>
      </label>
      <button id="btn-pensee-cycle" class="ghost" style="font-size:12px;padding:7px 14px;margin-left:auto">Provoquer une pensee</button>
    </div>
    <div class="row" style="gap:10px;align-items:center;margin-bottom:10px">
      <input id="pensee-sujet" type="text" placeholder="Proposer un sujet de discussion aux agents (ex : comment rendre l'onboarding plus fluide ?)" style="flex:1;padding:8px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px">
      <button id="btn-pensee-discuter" style="padding:8px 16px;font-size:12px">Discuter</button>
    </div>
    <div id="pensee-config-status" style="font-size:12px;opacity:.5;margin-bottom:10px;display:none"></div>

    <div id="pensee-filtres" style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:7px">
      <button onclick="filtrerPensees('tous')" class="filtre-btn" data-filtre="tous" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(168,85,247,.2);border:1px solid rgba(168,85,247,.5);color:#a855f7;cursor:pointer">Toutes</button>
      <button onclick="filtrerPensees('neuves')" class="filtre-btn" data-filtre="neuves" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">&#9733; Neuves</button>
      <button onclick="filtrerPensees('pris-en-vie')" class="filtre-btn" data-filtre="pris-en-vie" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">&#10003; En vie</button>
      <button onclick="filtrerPensees('generee')" class="filtre-btn" data-filtre="generee" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">&#9889; Forgees</button>
      <button onclick="filtrerPensees('bulle')" class="filtre-btn" data-filtre="bulle" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">&#9679; Bulles</button>
      <button onclick="filtrerPensees('refusee')" class="filtre-btn" data-filtre="refusee" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">&#10007; Refusees</button>
      <button onclick="filtrerPensees('archivee')" class="filtre-btn" data-filtre="archivee" style="font-size:11px;padding:4px 10px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#9ca3af;cursor:pointer">Archivees</button>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;align-items:center">
      <div id="pensee-filtres-type" style="display:flex;gap:4px;flex-wrap:wrap;align-items:center">
        <span style="font-size:10px;opacity:.35;margin-right:2px">type :</span>
        <button onclick="filtrerPenseesType('tous')" class="filtre-btn-type" data-type="tous" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(168,85,247,.15);border:1px solid rgba(168,85,247,.4);color:#a855f7;cursor:pointer">Tous</button>
        <button onclick="filtrerPenseesType('sujet')" class="filtre-btn-type" data-type="sujet" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Sujets</button>
        <button onclick="filtrerPenseesType('idee')" class="filtre-btn-type" data-type="idee" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Idees</button>
        <button onclick="filtrerPenseesType('suggestion')" class="filtre-btn-type" data-type="suggestion" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Sug.</button>
        <button onclick="filtrerPenseesType('reflexion')" class="filtre-btn-type" data-type="reflexion" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Reflexions</button>
        <button onclick="filtrerPenseesType('reve')" class="filtre-btn-type" data-type="reve" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Reves</button>
        <button onclick="filtrerPenseesType('obsession')" class="filtre-btn-type" data-type="obsession" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Obsessions</button>
        <button onclick="filtrerPenseesType('desir')" class="filtre-btn-type" data-type="desir" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Desirs</button>
      </div>
      <div id="pensee-tri" style="display:flex;gap:4px;align-items:center;margin-left:auto">
        <span style="font-size:10px;opacity:.35;margin-right:2px">tri :</span>
        <button onclick="trierPensees('type')" class="filtre-btn-tri" data-tri="type" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(168,85,247,.15);border:1px solid rgba(168,85,247,.4);color:#a855f7;cursor:pointer">&#8597; Type</button>
        <button onclick="trierPensees('recent')" class="filtre-btn-tri" data-tri="recent" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">&#8595; Recent</button>
        <button onclick="trierPensees('ancien')" class="filtre-btn-tri" data-tri="ancien" style="font-size:10px;padding:2px 7px;border-radius:4px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">&#8593; Ancien</button>
      </div>
    </div>

    <div id="pensee-list">
      <div style="text-align:center;padding:24px;opacity:.4;font-size:13px">Aucune pensee pour l'instant.</div>
    </div>
  </div>

  <!-- Super-capacite : evolution gouvernee (s'auto-modifier sans toucher au noyau) -->
  <div class="panel glass" style="margin-top:20px">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:6px">
      <h3 style="margin:0;font-size:15px">Super-capacite <span style="font-size:11px;opacity:.5;font-weight:400">&mdash; evolution gouvernee</span></h3>
      <span id="evo-portee-badge" style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px;background:rgba(16,185,129,.12);color:#10b981">--</span>
    </div>
    <p style="font-size:12px;opacity:.55;margin:0 0 14px;line-height:1.5">NEOGEN peut ajouter regles, idees, skills, savoir, bebe-agents, modeles... TOUT en data-driven. Le noyau (ADN + murs + securite) reste grave : aucune evolution ne peut le toucher. Chaque changement passe par ton consentement (onglet Propositions) et est notifie sur la generation de l'annee.</p>

    <!-- Noyau grave -->
    <div id="evo-noyau" style="padding:12px;background:rgba(239,68,68,.05);border:1px solid rgba(239,68,68,.15);border-radius:10px;margin-bottom:14px;font-size:12px">
      <div style="font-weight:600;color:#ef4444;margin-bottom:6px">&#128274; Noyau grave (jamais modifiable)</div>
      <div id="evo-noyau-corps" style="opacity:.7;line-height:1.6">chargement...</div>
    </div>

    <!-- Generation courante -->
    <div class="row" style="gap:12px;align-items:center;margin-bottom:14px;flex-wrap:wrap">
      <div style="text-align:center;padding:10px 16px;background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.08)">
        <div style="font-size:20px;font-weight:700;color:#10b981" id="evo-gen-num">--</div>
        <div style="font-size:10px;opacity:.5">generation (1 an)</div>
      </div>
      <div style="text-align:center;padding:10px 16px;background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.08)">
        <div style="font-size:20px;font-weight:700;color:#3b82f6" id="evo-gen-chg">--</div>
        <div style="font-size:10px;opacity:.5">changements cette annee</div>
      </div>
    </div>

    <!-- Proposer un changement -->
    <div style="padding:12px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:10px;margin-bottom:14px">
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">Proposer une evolution</div>
      <div class="row" style="gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
        <select id="evo-type" style="padding:8px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px">
          <option value="regle">Regle</option>
          <option value="idee">Idee</option>
          <option value="skill">Skill / fonction</option>
          <option value="savoir">Savoir</option>
          <option value="agent">Bebe-agent</option>
          <option value="modele">Modele IA</option>
        </select>
        <input id="evo-titre" type="text" placeholder="Titre court" style="flex:1;min-width:160px;padding:8px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px">
      </div>
      <textarea id="evo-payload" placeholder='payload JSON, ex : {"cle":"style_reponse","valeur":"direct"}' style="width:100%;min-height:60px;padding:8px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px;font-family:monospace;margin-bottom:8px"></textarea>
      <div class="row" style="gap:10px;align-items:center">
        <input id="evo-raison" type="text" placeholder="Pourquoi ce changement ?" style="flex:1;padding:8px 12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:#fff;font-size:12px">
        <button id="btn-evo-proposer" style="padding:8px 18px;font-size:12px">Proposer</button>
      </div>
      <div id="evo-proposer-status" style="font-size:12px;opacity:.6;margin-top:8px;display:none"></div>
    </div>

    <!-- Changelog de la generation -->
    <div class="row" style="align-items:center;margin-bottom:8px;gap:8px;flex-wrap:wrap">
      <div style="font-size:13px;font-weight:600">Changements de la generation</div>
      <div id="changelog-filtres" style="display:flex;gap:5px;flex-wrap:wrap">
        <button onclick="filtrerChangelog('tous')" class="filtre-btn-cl" data-cl="tous" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.4);color:#10b981;cursor:pointer">Tous</button>
        <button onclick="filtrerChangelog('interface')" class="filtre-btn-cl" data-cl="interface" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Interface</button>
        <button onclick="filtrerChangelog('regle')" class="filtre-btn-cl" data-cl="regle" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Regle</button>
        <button onclick="filtrerChangelog('loi')" class="filtre-btn-cl" data-cl="loi" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Loi</button>
        <button onclick="filtrerChangelog('idee')" class="filtre-btn-cl" data-cl="idee" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Idee</button>
        <button onclick="filtrerChangelog('agent')" class="filtre-btn-cl" data-cl="agent" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Agent</button>
        <button onclick="filtrerChangelog('modele')" class="filtre-btn-cl" data-cl="modele" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Modele</button>
        <button onclick="filtrerChangelog('cellule')" class="filtre-btn-cl" data-cl="cellule" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Cellule</button>
        <button onclick="filtrerChangelog('skill')" class="filtre-btn-cl" data-cl="skill" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Skill</button>
        <button onclick="filtrerChangelog('savoir')" class="filtre-btn-cl" data-cl="savoir" style="font-size:11px;padding:3px 8px;border-radius:5px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);color:#9ca3af;cursor:pointer">Savoir</button>
      </div>
    </div>
    <div id="evo-changelog">
      <div style="text-align:center;padding:20px;opacity:.4;font-size:12px">Aucun changement applique cette annee.</div>
    </div>

    <!-- CONSCIENCE DU SYSTEME : ce que NEOGEN sait de lui-meme (statut reel de chaque capacite) -->
    <div id="conscience-panel" style="margin:22px 0 8px;border:1px solid rgba(0,232,105,.18);border-radius:14px;padding:16px;background:rgba(0,20,8,.35)">
      <div class="row" style="align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px">
        <div style="font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px">
          <span style="width:9px;height:9px;border-radius:50%;background:#00e869;box-shadow:0 0 10px #00e869"></span>
          Conscience du systeme
        </div>
        <span style="font-size:11px;opacity:.55;font-weight:400">ce que l'organisme sait de lui-meme : ce qui est integre, en echec, reparable</span>
        <button id="btn-conscience-autorep" onclick="autoReparerConscience(this)" style="margin-left:auto;font-size:12px;padding:6px 14px;background:rgba(251,146,60,.12);border:1px solid rgba(251,146,60,.35);color:#fb923c">&#128295; Auto-reparer</button>
        <button id="btn-conscience-diag" onclick="diagnostiquerConscience(this)" style="font-size:12px;padding:6px 14px">Diagnostiquer</button>
      </div>
      <div id="conscience-jauge" style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px"></div>

      <!-- ATTEINDRE UN OBJECTIF : les 3 etats appliques a toute demande -->
      <div style="margin:6px 0 14px;padding:12px;border:1px dashed rgba(0,232,105,.28);border-radius:12px;background:rgba(0,16,6,.3)">
        <div style="font-size:12px;font-weight:700;margin-bottom:7px">&#127919; Atteindre un objectif <span style="font-size:10px;opacity:.5;font-weight:400">— NEOGEN classe CERTAIN / INCONNU / ANGLE MORT, forge les manques, demande les donnees sensibles</span></div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <input type="text" id="obj-input" placeholder="ex: un outil qui calcule mes charges sociales d'auto-entrepreneur" style="flex:1;min-width:240px;font-size:12px;padding:7px 11px;background:rgba(0,0,0,.25);border:1px solid rgba(0,232,105,.25);color:#e8ffe8;border-radius:8px">
          <button id="obj-btn" onclick="resoudreObjectif(this)" style="font-size:12px;padding:7px 16px">Resoudre</button>
        </div>
        <div id="obj-resultat" style="margin-top:10px;display:none"></div>
      </div>

      <div id="conscience-capacites">
        <div style="text-align:center;padding:18px;opacity:.4;font-size:12px">Clique « Diagnostiquer » : le systeme va se regarder lui-meme.</div>
      </div>
    </div>

    <!-- Subconscient : memoire-graphe + moteur de reve -->
    <div id="subconscient-panel" style="margin:18px 0 8px;border:1px solid rgba(245,158,11,.22);border-radius:14px;padding:16px;background:rgba(20,10,0,.35)">
      <div class="row" style="align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px">
        <div style="font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px">
          <span style="width:9px;height:9px;border-radius:50%;background:#f59e0b;box-shadow:0 0 10px #f59e0b"></span>
          Subconscient
        </div>
        <span style="font-size:11px;opacity:.55;font-weight:400">memoire-graphe + bisociation + nouveaute — les reves emergent en bulles</span>
        <button id="btn-rever" onclick="faireRever(this)" style="margin-left:auto;font-size:12px;padding:6px 14px;background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.4);color:#f59e0b">&#127769; Faire rever NEOGEN</button>
      </div>
      <div id="subconscient-etat" style="font-size:11px;opacity:.55;margin-bottom:8px">Chargement...</div>
      <div id="subconscient-reves" style="display:flex;flex-direction:column;gap:6px"></div>
    </div>

    <!-- Cellules forgees : le VRAI code genere par "donner vie" sur une idee technique -->
    <div style="font-size:13px;font-weight:600;margin:18px 0 8px">Cellules forgees <span style="font-size:11px;opacity:.5;font-weight:400">(code reel genere, teste en sandbox, valide contre les murs)</span></div>
    <div id="evo-cellules">
      <div style="text-align:center;padding:20px;opacity:.4;font-size:12px">Aucune cellule forgee. « Donner vie » a une idee technique en genere une.</div>
    </div>

    <!-- Interface : evolutions d'apparence (CSS override), reversibles -->
    <div class="row" style="align-items:center;margin:18px 0 8px;gap:10px">
      <div style="font-size:13px;font-weight:600">Interface <span style="font-size:11px;opacity:.5;font-weight:400">(« donner vie » a une idee d'affichage genere un apercu CSS a confirmer)</span></div>
      <button class="ghost" id="btn-ui-reset" style="font-size:11px;padding:4px 12px;margin-left:auto">Reinitialiser l'interface</button>
    </div>

    <!-- Forge de fragments : de VRAIS blocs HTML injectes a l'ecran (proprio uniquement) -->
    <div id="forge-frag-panel" style="margin-top:22px;border-top:1px solid rgba(255,255,255,.08);padding-top:16px">
      <div style="font-size:13px;font-weight:700;margin-bottom:4px">&#9874; Forge de blocs <span style="font-size:11px;opacity:.5;font-weight:400">(de vrais elements HTML, pas juste du CSS — injectes en direct, reversibles)</span></div>
      <div style="font-size:11px;opacity:.5;margin-bottom:12px">Decris un bloc, choisis sa zone, genere un apercu, applique. Ton interface change vraiment. Tout est reversible et ne touche jamais au noyau.</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px">
        <select id="frag-zone" style="font-size:12px;padding:6px 10px"></select>
        <input type="text" id="frag-idee" placeholder="ex: un panel 'Carte vivante' avec 3 indicateurs en puces" style="flex:1;min-width:220px;font-size:12px;padding:6px 10px">
        <button id="frag-apercu-btn" style="font-size:12px;padding:6px 14px">Generer un apercu</button>
      </div>
      <div id="frag-apercu-zone" style="display:none;margin:10px 0;padding:12px;background:rgba(168,85,247,.06);border:1px dashed rgba(168,85,247,.3);border-radius:10px">
        <div style="font-size:11px;font-weight:700;color:#a855f7;margin-bottom:6px">Apercu <span id="frag-apercu-titre" style="opacity:.7;font-weight:400"></span></div>
        <div id="frag-apercu-render" style="margin:8px 0;padding:8px;background:rgba(0,0,0,.2);border-radius:8px"></div>
        <div id="frag-apercu-expl" style="font-size:11px;opacity:.6;margin-bottom:10px"></div>
        <button id="frag-appliquer-btn" style="font-size:12px;padding:6px 14px">Appliquer (runtime)</button>
        <button id="frag-graver-btn" style="font-size:12px;padding:6px 14px;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.4);color:#10b981">&#128190; Graver (permanent, code)</button>
        <button class="ghost" id="frag-annuler-btn" style="font-size:12px;padding:6px 14px">Annuler</button>
        <div style="font-size:10px;opacity:.45;margin-top:6px;line-height:1.4"><b>Runtime</b> : applique tout de suite, reversible en un clic (data). &nbsp;·&nbsp; <b>Permanent</b> : grave dans le vrai code, versionne git, survit a une remise a zero (backup + rollback auto).</div>
      </div>
      <div id="frag-status" style="font-size:12px;min-height:16px;margin:6px 0"></div>
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;opacity:.5;margin:14px 0 8px">Blocs forges</div>
      <div id="frag-liste"><div style="opacity:.4;font-size:12px">Chargement...</div></div>
    </div>
  </div>
  </div>
</div>
"""


def _section_marketing() -> str:
    return r"""<!-- MARKETING -->
<div id="section-marketing" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-marketing)"></span>Marketing</h2>
    <p>Strategie, creation de contenu, campagnes et distribution — amplifie ta presence digitale.</p>
  </div>

  <!-- Agent Mercure -->
  <div class="agent-chat-mount" data-agent="marketeur" data-titre="🪁 Mercure" data-sub="Strategie reseaux, copywriting, visuels, campagnes, analyse de performance — dis-moi ta cible et ton objectif."></div>

  <!-- Plateformes Reseaux Sociaux -->
  <div class="panel glass" style="margin-bottom:18px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Reseaux Sociaux</div>
    <div class="mkt-platform-grid">
      <div class="mkt-platform-card" style="--pc:#e1306c"><span>📸</span><b>Instagram</b><span class="mkt-tag">Stories · Reels · Posts</span></div>
      <div class="mkt-platform-card" style="--pc:#1877f2"><span>📘</span><b>Facebook / Meta</b><span class="mkt-tag">Ads · Pages · Groupes</span></div>
      <div class="mkt-platform-card" style="--pc:#0a66c2"><span>💼</span><b>LinkedIn</b><span class="mkt-tag">B2B · Articles · Ads</span></div>
      <div class="mkt-platform-card" style="--pc:#1da1f2"><span>🐦</span><b>X / Twitter</b><span class="mkt-tag">Threads · Tendances</span></div>
      <div class="mkt-platform-card" style="--pc:#ff0050"><span>🎵</span><b>TikTok</b><span class="mkt-tag">UGC · Tendances · Ads</span></div>
      <div class="mkt-platform-card" style="--pc:#ff0000"><span>▶️</span><b>YouTube</b><span class="mkt-tag">Shorts · Videos · SEO</span></div>
      <div class="mkt-platform-card" style="--pc:#e60023"><span>📌</span><b>Pinterest</b><span class="mkt-tag">Visuels · Trafic</span></div>
      <div class="mkt-platform-card" style="--pc:#25d366"><span>💬</span><b>WhatsApp / SMS</b><span class="mkt-tag">Broadcast · CRM</span></div>
    </div>
  </div>

  <!-- Creation Visuelle & Video -->
  <div class="panel glass" style="margin-bottom:18px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Creation Image &amp; Video</div>
    <div class="mkt-platform-grid">
      <div class="mkt-platform-card mkt-available" style="--pc:#f97316" title="MCP disponible dans NEOGEN"><span>✨</span><b>Magnific</b><span class="mkt-tag">MCP actif · Images &amp; Videos IA</span></div>
      <div class="mkt-platform-card" style="--pc:#a855f7"><span>🎨</span><b>Midjourney</b><span class="mkt-tag">Illustrations · Concepts</span></div>
      <div class="mkt-platform-card" style="--pc:#10b981"><span>🖼️</span><b>DALL-E / GPT-4o</b><span class="mkt-tag">Images OpenAI</span></div>
      <div class="mkt-platform-card" style="--pc:#ef4444"><span>🎬</span><b>Runway</b><span class="mkt-tag">Video IA Gen-3</span></div>
      <div class="mkt-platform-card" style="--pc:#3b82f6"><span>🎥</span><b>Pika Labs</b><span class="mkt-tag">Video courte IA</span></div>
      <div class="mkt-platform-card" style="--pc:#f59e0b"><span>🖌️</span><b>Canva</b><span class="mkt-tag">Design templates</span></div>
      <div class="mkt-platform-card" style="--pc:#ec4899"><span>🎭</span><b>HeyGen</b><span class="mkt-tag">Avatar video IA</span></div>
      <div class="mkt-platform-card" style="--pc:#6366f1"><span>🔊</span><b>ElevenLabs</b><span class="mkt-tag">Voix IA · Podcasts</span></div>
    </div>
  </div>

  <!-- MCP & Integrations Recommandees -->
  <div class="panel glass" style="margin-bottom:18px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">MCP &amp; Plugins Recommandes</div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <div class="mkt-mcp-card mkt-available">
        <span style="font-size:20px">✨</span>
        <div>
          <div style="font-weight:600;font-size:14px">Magnific MCP <span class="mkt-badge-ok">Disponible</span></div>
          <div style="font-size:12px;opacity:.65;margin-top:2px">Generation d'images, upscale, videos, voix — directement depuis ton agent Mercure.</div>
        </div>
      </div>
      <div class="mkt-mcp-card mkt-available">
        <span style="font-size:20px">📓</span>
        <div>
          <div style="font-weight:600;font-size:14px">NotebookLM MCP <span class="mkt-badge-ok">Disponible</span></div>
          <div style="font-size:12px;opacity:.65;margin-top:2px">Recherche approfondie, synthese de tendances, briefings marketing construits sur des sources reelles.</div>
        </div>
      </div>
      <div class="mkt-mcp-card">
        <span style="font-size:20px">⚡</span>
        <div>
          <div style="font-weight:600;font-size:14px">n8n Workflows <span class="mkt-badge">Recommande</span></div>
          <div style="font-size:12px;opacity:.65;margin-top:2px">Automatise la publication multi-plateforme : cree ton contenu dans NEOGEN, publie en automatique via n8n.</div>
        </div>
      </div>
      <div class="mkt-mcp-card">
        <span style="font-size:20px">📊</span>
        <div>
          <div style="font-weight:600;font-size:14px">Meta Business MCP <span class="mkt-badge">A installer</span></div>
          <div style="font-size:12px;opacity:.65;margin-top:2px">Gestion des campagnes Meta Ads, statistiques et audiences directement depuis ton agent.</div>
        </div>
      </div>
      <div class="mkt-mcp-card">
        <span style="font-size:20px">🔍</span>
        <div>
          <div style="font-weight:600;font-size:14px">Google Analytics MCP <span class="mkt-badge">A installer</span></div>
          <div style="font-size:12px;opacity:.65;margin-top:2px">Tes metriques GA4 accessibles directement dans la conversation avec Mercure.</div>
        </div>
      </div>
      <div class="mkt-mcp-card">
        <span style="font-size:20px">📧</span>
        <div>
          <div style="font-weight:600;font-size:14px">Brevo / Mailchimp MCP <span class="mkt-badge">A installer</span></div>
          <div style="font-size:12px;opacity:.65;margin-top:2px">Campagnes email et newsletters pilotees depuis NEOGEN.</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Outils Marketing Essentiels -->
  <div class="panel glass">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Outils Essentiels</div>
    <div class="mkt-platform-grid">
      <div class="mkt-platform-card" style="--pc:#f97316"><span>📈</span><b>Google Analytics 4</b><span class="mkt-tag">Trafic · Conversions</span></div>
      <div class="mkt-platform-card" style="--pc:#4285f4"><span>🔍</span><b>Google Ads</b><span class="mkt-tag">SEA · Display</span></div>
      <div class="mkt-platform-card" style="--pc:#007bff"><span>📧</span><b>Brevo</b><span class="mkt-tag">Email · SMS · Automation</span></div>
      <div class="mkt-platform-card" style="--pc:#ffe01b"><span>📨</span><b>Mailchimp</b><span class="mkt-tag">Email Marketing</span></div>
      <div class="mkt-platform-card" style="--pc:#ff6550"><span>📐</span><b>Semrush</b><span class="mkt-tag">SEO · Mots-cles</span></div>
      <div class="mkt-platform-card" style="--pc:#10b981"><span>🔗</span><b>Buffer</b><span class="mkt-tag">Planificateur social</span></div>
      <div class="mkt-platform-card" style="--pc:#6366f1"><span>📅</span><b>Hootsuite</b><span class="mkt-tag">Gestion reseaux</span></div>
      <div class="mkt-platform-card" style="--pc:#a855f7"><span>🎯</span><b>Meta Pixel</b><span class="mkt-tag">Retargeting · ROI</span></div>
    </div>
  </div>
</div>
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
