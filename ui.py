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
    return r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEOGEN</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>

<!-- SHADER CANVAS (fond fixe) -->
<canvas id="bg-canvas"></canvas>

<header>
  <h1 onclick="showLanding()">NEO<b>GEN</b></h1>
  <div id="docker-status"><span class="dot off"></span>chargement...</div>
</header>

<div id="breadcrumb" class="breadcrumb" onclick="showLanding()">
  <span style="font-size:16px">←</span>
  <span id="bc-label">Accueil</span>
</div>
"""


def _sidebar() -> str:
    return r"""<!-- SIDEBAR (flottant, visible en mode section) -->
<nav class="sidebar" id="sidebar">
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
    <span class="side-dot"></span>Analyse
    <span class="side-badge live">live</span>
  </div>
  <div class="side-item" style="--lc:#10b981" onclick="showSection('evolution')" id="side-evolution">
    <span class="side-dot"></span>Evolution
    <span class="side-badge live">live</span>
    <span id="evo-badge-nav" style="display:none;margin-left:auto;font-size:11px;font-weight:700;color:#10b981;background:rgba(16,185,129,.12);border-radius:99px;padding:1px 8px">0</span>
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
<div id="landing">
  <div class="landing-title">
    <h2>NEO<b>GEN</b></h2>
    <p>Une intention devient une application gouvernee, generee et executee en conteneur durci.</p>
  </div>

  <div class="bento">
    <div class="bento-3d">

    <div class="layer" onclick="showSection('cerveau')">
      <span class="layer-marker" style="--lc:#a855f7"></span>
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
      <div class="layer-label"><h3>Analyse</h3><p>Metriques de production et capacites utilisees</p></div>
      <span class="badge live">live</span>
      <span class="layer-arrow">›</span>
    </div>

    <div class="layer" onclick="showSection('evolution')">
      <span class="layer-marker" style="--lc:#10b981"></span>
      <div class="layer-label"><h3>Evolution</h3><p>Hub du savoir : 5 silos unifies, propositions d'amelioration</p></div>
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
      <button id="btn-conseils" class="ghost">Conseils (conformite)</button>
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

  <!-- Modal bibliotheque de skills -->
  <div id="skills-lib-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;align-items:center;justify-content:center">
    <div class="glass panel" style="width:min(540px,95vw);max-height:80vh;overflow-y:auto;padding:22px 24px;position:relative">
      <button onclick="document.getElementById('skills-lib-modal').style.display='none'" style="position:absolute;top:12px;right:14px;background:none;border:none;font-size:18px;cursor:pointer;color:var(--mut)">&times;</button>
      <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--mut);margin-bottom:14px">Bibliotheque communautaire</div>
      <div id="skills-lib-list"><div style="color:var(--mut);font-size:13px">Chargement...</div></div>
    </div>
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
        <select id="tache-provider" style="font-size:12px"><option value="local">Local (gratuit)</option><option value="anthropic">Anthropic</option><option value="openai">OpenAI</option><option value="gemini">Gemini</option><option value="deepseek">DeepSeek</option><option value="mistral">Mistral</option></select>
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
      <button class="ghost pack-btn" data-pack="starter" style="flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">100 GEN</span><span style="font-size:11px;opacity:.7">Starter — 2&#8364;</span></button>
      <button class="ghost pack-btn" data-pack="pro" style="flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">500 GEN</span><span style="font-size:11px;opacity:.7">Pro — 8&#8364; <span style="color:#10b981">-20%</span></span></button>
      <button class="ghost pack-btn" data-pack="power" style="flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">1 500 GEN</span><span style="font-size:11px;opacity:.7">Power — 20&#8364; <span style="color:#10b981">-33%</span></span></button>
      <button class="ghost pack-btn" data-pack="ultimate" style="flex-direction:column;gap:2px;padding:10px 8px;text-align:center"><span style="font-size:15px;font-weight:800;color:#f59e0b">5 000 GEN</span><span style="font-size:11px;opacity:.7">Ultimate — 50&#8364; <span style="color:#10b981">-50%</span></span></button>
    </div>
  </div>

  <!-- Telemetrie RGPD -->
  <div class="panel glass" style="margin-bottom:18px" id="telemetrie-panel">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:10px">Amelioration communautaire (opt-in)</div>
    <div style="font-size:12px;color:var(--mut);margin-bottom:10px">Contribue a rendre NEOGEN plus intelligent. Donnees anonymisees. <b style="color:#f59e0b">+5 GEN/mois</b> si tu participes.</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap" id="tele-consent-btns">
      <button class="ghost tele-btn" data-niveau="aucun" style="font-size:12px;padding:5px 12px">Aucun</button>
      <button class="ghost tele-btn" data-niveau="erreurs" style="font-size:12px;padding:5px 12px">Erreurs only</button>
      <button class="ghost tele-btn" data-niveau="usage" style="font-size:12px;padding:5px 12px">Erreurs + usage</button>
      <button class="ghost tele-btn" data-niveau="tout" style="font-size:12px;padding:5px 12px">Tout contribuer</button>
    </div>
    <div id="tele-status" style="font-size:11px;color:var(--mut);margin-top:8px"></div>
  </div>

  <!-- Panel Preferences toujours visible (sans connexion requise) -->
  <div class="panel glass" style="margin-bottom:18px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.9px;color:var(--mut);margin-bottom:14px">Preferences</div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <span style="font-size:13px;color:var(--txt)">Mode sombre</span>
      <label class="dark-toggle"><input type="checkbox" id="dark-toggle-cb"></label>
    </div>
    <div style="margin-bottom:6px">
      <div style="font-size:13px;color:var(--txt);margin-bottom:8px">Autorisation agent ecran</div>
      <div class="consent-btns">
        <button class="consent-btn safe" data-level="always" data-dur="0" title="Popup avant chaque action">Toujours demander</button>
        <button class="consent-btn" data-level="sequence" data-dur="120">2 min</button>
        <button class="consent-btn" data-level="sequence" data-dur="600">10 min</button>
        <button class="consent-btn" data-level="sequence" data-dur="1800">30 min</button>
        <button class="consent-btn" data-level="sequence" data-dur="3600">1 h</button>
        <button class="consent-btn" data-level="sequence" data-dur="7200">2 h</button>
        <button class="consent-btn" data-level="sequence" data-dur="18000">5 h</button>
        <button class="consent-btn" data-level="sequence" data-dur="43200">12 h</button>
        <button class="consent-btn danger" data-level="auto" data-dur="0" title="Aucune popup, auto-approuve tout">Auto</button>
      </div>
    </div>
    <div style="margin-top:14px;display:flex;align-items:center;gap:10px">
      <span id="agent-local-status" style="font-size:13px;color:var(--mut)">Agent local...</span>
      <button class="ghost" id="clear-chats-btn" style="font-size:12px;padding:5px 12px;margin-left:auto">Effacer tous les chats</button>
    </div>
  </div>
  <div class="agent-chat-mount" data-agent="secretaire" data-titre="📋 Le Secretaire" data-sub="Ton conseiller, administrateur et assistant au quotidien."></div>
  <div id="compte-root"></div>
</div>
"""


def _section_analyse() -> str:
    return r"""<!-- ANALYSE -->
<div id="section-analyse" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-analyse)"></span>Analyse</h2>
    <p>Metriques de production, capacites utilisees, repartition tentatives.</p>
  </div>
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
"""


def _section_integrations() -> str:
    return r"""<!-- INTEGRATIONS -->
<div id="section-integrations" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:var(--c-integration)"></span>Integrations</h2>
    <p>Connecte ton modele IA et tes comptes. NEOGEN les utilise dans les analyses et productions.</p>
  </div>

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
    return r"""<script src="/static/app.js"></script>
</body>
</html>
"""


def _section_evolution() -> str:
    return r"""<!-- EVOLUTION : Hub du savoir unifie -->
<div id="section-evolution" class="section">
  <div class="sec-header">
    <h2><span class="sec-dot" style="background:#10b981"></span>Evolution</h2>
    <p>Hub du savoir : 5 silos unifies. Le systeme apprend, propose, tu approuves.</p>
  </div>

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
      <button id="btn-pensee-cycle" class="ghost" style="font-size:12px;padding:7px 14px;margin-left:auto">Provoquer une pensee</button>
    </div>
    <div id="pensee-config-status" style="font-size:12px;opacity:.5;margin-bottom:10px;display:none"></div>

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
    <div style="font-size:13px;font-weight:600;margin-bottom:8px">Changements de la generation</div>
    <div id="evo-changelog">
      <div style="text-align:center;padding:20px;opacity:.4;font-size:12px">Aucun changement applique cette annee.</div>
    </div>
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
    + _section_integrations()
    + _modals()
    + _section_don()
    + _foot()
)
