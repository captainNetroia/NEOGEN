/* NEOGEN - Internationalisation (i18n)
   Dictionnaire de traduction + fonction t(cle, params). Charge AVANT app.js
   (cf. ui.py::_foot) car app.js appelle t() des le premier rendu.

   Usage : t('compte.preferences') -> "Preferences" (fr) ou "Preferences" (en)
           t('compte.bienvenue', {prenom:'Jordan'}) -> remplace {prenom} dans la chaine

   Ajout d'une langue : ajouter une cle dans TRADUCTIONS ci-dessous avec les
   memes cles que 'fr'. Une cle absente dans la langue active retombe sur 'fr',
   puis sur la cle brute si meme 'fr' ne l'a pas (jamais de texte vide/casse). */

const TRADUCTIONS = {
  fr: {
    'compte.preferences': 'Preferences',
    'compte.mode_sombre': 'Mode sombre',
    'compte.autorisation_agent_ecran': 'Autorisation agent ecran',
    'compte.toujours_demander': 'Toujours demander',
    'compte.auto': 'Auto',
    'compte.agent_local_attente': 'Agent local...',
    'compte.effacer_chats': 'Effacer tous les chats',
    'compte.langue': 'Langue',
  },
  en: {
    'compte.preferences': 'Preferences',
    'compte.mode_sombre': 'Dark mode',
    'compte.autorisation_agent_ecran': 'Screen agent permission',
    'compte.toujours_demander': 'Always ask',
    'compte.auto': 'Auto',
    'compte.agent_local_attente': 'Local agent...',
    'compte.effacer_chats': 'Clear all chats',
    'compte.langue': 'Language',
  },
};

const LANGUES_DISPONIBLES = ['fr', 'en'];
const LANGUE_DEFAUT = 'fr';

function _langueActive() {
  try {
    const l = localStorage.getItem('neogen_langue');
    if (l && LANGUES_DISPONIBLES.includes(l)) return l;
  } catch (e) {}
  return LANGUE_DEFAUT;
}

function t(cle, params) {
  const langue = _langueActive();
  let texte = (TRADUCTIONS[langue] && TRADUCTIONS[langue][cle])
    || (TRADUCTIONS[LANGUE_DEFAUT] && TRADUCTIONS[LANGUE_DEFAUT][cle])
    || cle;
  if (params) {
    Object.keys(params).forEach(function (k) {
      texte = texte.split('{' + k + '}').join(params[k]);
    });
  }
  return texte;
}

function definirLangue(langue) {
  if (!LANGUES_DISPONIBLES.includes(langue)) return;
  try { localStorage.setItem('neogen_langue', langue); } catch (e) {}
  document.documentElement.lang = langue;
}

document.documentElement.lang = _langueActive();
