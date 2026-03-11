# SPEC.md — Research Companion Search Strategy Engine

> Ce document est la source de vérité du projet.  
> Claude Code doit le lire avant chaque ticket.  
> Dernière mise à jour : 2026-03-11

---

## Vision produit

Research Companion aide un utilisateur novice en recherche documentaire
à transformer un sujet formulé en langage libre
en une stratégie de recherche compréhensible, ajustable et exploitable
sur plusieurs plateformes bibliographiques.

L’utilisateur n’a pas besoin de connaître :
- PICO
- PEO
- SPIDER
- Bramer
- TIAB
- MeSH
- Emtree
- les syntaxes propres à PubMed, Scopus, Web of Science ou Embase

Ces notions travaillent en coulisses.

Le produit doit :
- aider à clarifier une question de recherche
- identifier les concepts réellement utiles à la recherche documentaire
- distinguer ce qui doit filtrer de ce qui ne doit pas filtrer
- proposer une stratégie large puis une stratégie restreinte
- rester simple, pédagogique et transparent
- afficher à terme les requêtes réelles par plateforme

---

## Principe central

Research Companion n’est pas un produit limité à PubMed.

Le moteur central construit d’abord une **stratégie de recherche canonique**,
indépendante de toute plateforme.

Cette stratégie est ensuite traduite par un backend spécifique vers :
- PubMed
- Scopus
- Web of Science
- Embase
- d’autres plateformes plus tard

Phrase de référence :

**Research Companion is not a PubMed-only product. PubMed is the first supported backend, not the product boundary.**

Le produit comporte deux couches :

### Cœur produit
- compréhension de la question
- détection de l’intent
- extraction des composantes
- construction des `search_elements`
- décision de `search_filter`
- attribution de `priority`
- construction logique `wide` / `narrow`
- interaction utilisateur dans le workspace

### Backend plateforme
- traduction de la stratégie canonique dans une syntaxe plateforme
- ajout éventuel de vocabulaire contrôlé propre à la plateforme
- comptage des résultats si disponible
- export de la requête réelle

Principe UX :

**L’utilisateur manipule des concepts. Les plateformes reçoivent une syntaxe.**

---

## Place de la logique Bramer

La logique Bramer structure le cœur du moteur.

Elle sert à :
- identifier les concepts utiles à la recherche
- distinguer les concepts à filtrer de ceux à exclure
- attribuer les priorités `1` et `2`
- construire une stratégie large puis une stratégie restreinte

Elle s’applique donc à la **stratégie canonique**,
avant toute traduction plateforme.

Elle ne dépend pas de PubMed, Scopus, Web of Science ou Embase.

Les backends plateforme ne doivent pas redéfinir cette logique.
Ils traduisent uniquement la stratégie canonique dans leur syntaxe propre.

Référence conceptuelle :
Bramer et al. (2018)

Principes Bramer retenus :
- Les frameworks comme PICO, PEO ou SPIDER servent à comprendre la question, pas à générer mécaniquement une requête.
- Tous les concepts extraits ne doivent pas devenir des filtres.
- Chaque bloc ajouté en `AND` augmente le risque d’exclure des documents pertinents.
- Il faut donc limiter les blocs `AND` aux concepts réellement nécessaires.
- Il faut commencer large, puis affiner.
- Le comparateur aide à comprendre la question, mais ne doit pas servir de filtre actif par défaut.

Question Bramer à appliquer à chaque concept :

> Un document pertinent pourrait-il être utile même s’il ne mentionne pas explicitement ce concept dans les champs textuels recherchés ?

- si oui → `search_filter = false`
- si non → `search_filter = true`

Ensuite :
- `priority = 1` si le concept est essentiel
- `priority = 2` s’il est utile pour restreindre
- `priority = null` si `search_filter = false`

---

## Flow utilisateur cible

### Écran 1 — Entrée
- Un seul champ texte : **Quel est votre sujet de recherche ?**
- L’utilisateur écrit en langage libre
- français ou anglais
- pas de choix manuel `explore` / `structure`
- l’intent est détecté automatiquement

### Écran 2 — Compréhension
L’application montre ce qu’elle a compris :
- reformulation éventuelle de la question
- framework identifié
- composantes extraites
- niveau de précision de la question
- concepts retenus pour la recherche
- concepts exclus du filtrage et pourquoi

### Écran 3 — Stratégie canonique
L’application affiche :
- une stratégie **large** = `priority = 1`
- une stratégie **restreinte** = `priority = 1 + 2`
- un court texte expliquant pourquoi il y a deux niveaux

### Écran 4 — Requêtes par plateforme
Pour chaque stratégie, l’application affiche les requêtes réelles par plateforme disponible.

Exemples :
- PubMed
- Scopus
- Web of Science
- Embase

### Cas particulier — stratégie large et restreinte identiques
Si `wide == narrow` au niveau logique :
- ne pas afficher deux gros blocs identiques
- afficher une seule stratégie
- ajouter une note discrète d’affinement

Exemple :

> Aucun filtre supplémentaire pertinent n’a été identifié.  
> Vous pouvez affiner en précisant un pays, un contexte, une population ou un cadre d’étude.

---

## Principes UI

- Pas d’emojis décoratifs
- Design épuré, calme, lisible
- L’utilisateur doit comprendre ce que l’outil fait
- L’outil ne doit pas donner une impression de magie opaque
- Il faut montrer :
  - ce qui a été compris
  - ce qui est utilisé
  - ce qui est exclu
  - pourquoi
- Les explications doivent être courtes

### Règle de transparence

La stratégie de recherche ne doit pas être opaque.

Pour chaque plateforme prise en charge, l’utilisateur doit pouvoir voir
la requête réellement générée dans la syntaxe de cette plateforme,
au moins sur demande.

---

## Règles métier immuables

- Le comparateur ne filtre jamais par défaut.
- Les outcomes de mesure génériques ne filtrent pas par défaut.
- Les concepts trop génériques ne filtrent pas par défaut.
- La géographie est le principal filtre de restriction par défaut.
- `patient` ou `patients` seul est interdit comme concept de recherche.
- La géographie ne doit pas être fusionnée avec la population dans un même concept.
- Les synonymes doivent rester courts et contrôlés.
- Le moteur central doit être indépendant de toute plateforme.
- Le backend plateforme ne doit jamais redéfinir la logique métier.
- La stratégie large correspond aux concepts actifs de `priority = 1`.
- La stratégie restreinte correspond aux concepts actifs de `priority = 1 + 2`.
- Un concept exclu reste visible dans l’interface avec sa justification.
- Le workspace manipule des concepts, pas des syntaxes de plateforme.
- Le code applicatif n’invente pas de nouvelle logique métier en dehors de la SPEC et du prompt.

---

## Concepts qui ne doivent pas filtrer par défaut

### Comparateur
Exemples :
- versus insulin
- compared with placebo
- compared to standard care

### Outcomes de mesure génériques
Exemples :
- prevalence
- incidence
- frequency
- burden
- epidemiology
- mortality rate
- morbidity rate

### Concepts trop génériques
Exemples :
- complications
- adverse events
- incidents
- safety
- burden
- epidemiology
- frequency
- outcomes

### Règle
Ces concepts peuvent être affichés pédagogiquement,
mais ne doivent pas devenir des filtres actifs par défaut,
sauf justification explicite et exceptionnelle.

---

## Structure canonique du JSON

Le LLM produit un JSON unique représentant la question
de manière indépendante de toute plateforme.

### Schéma cible

```json
{
  "intent": "explore" or "structure",
  "framework": "PICO" or "PEO" or "SPIDER" or null,
  "explanation": "...",
  "research_question_fr": "..." or null,
  "research_question_en": "..." or null,
  "research_question_comment": "..." or null,
  "geography": {
    "country": "..." or null,
    "region": "..." or null,
    "continent": "..." or null
  },
  "components": {
    "population": "..." or null,
    "intervention": "..." or null,
    "comparison": "..." or null,
    "outcome": "..." or null,
    "exposure": "..." or null,
    "setting": "..." or null
  },
  "search_elements": [
    {
      "label": "Short concept label",
      "canonical_terms": ["term 1", "term 2", "term 3"],
      "controlled_terms": {
        "mesh": ["..."],
        "emtree": ["..."],
        "other": []
      },
      "search_filter": true,
      "priority": 1,
      "reason": "Short justification"
    }
  ],
  "research_level": 1,
  "platform_hints": {
    "preferred_text_fields": ["title", "abstract", "keywords"],
    "notes": []
  }
}
Interprétation du JSON
intent

explore : sujet encore large, exploratoire

structure : sujet assez précis pour construire une stratégie structurée

framework

Usage pédagogique uniquement.

components

Sert à expliquer ce qui a été compris.
Ce bloc n’est pas la stratégie de recherche.

search_elements

C’est la matière première de la stratégie canonique.

canonical_terms

Liste de termes pivots indépendants de toute plateforme.

controlled_terms

Vocabulaire contrôlé éventuel organisé par système documentaire ou plateforme.

platform_hints

Aides facultatives pour guider la traduction vers des plateformes spécifiques.

Search elements — règles

Chaque search_element représente un concept potentiel de recherche.

Champs requis

label

canonical_terms

controlled_terms

search_filter

priority

reason

Règles

search_filter = true si le concept doit entrer dans la stratégie

search_filter = false s’il doit rester visible mais exclu

priority = 1 pour les concepts centraux

priority = 2 pour les concepts d’affinement

priority = null si search_filter = false

Exemples de concepts souvent priority = 1

population spécifique

condition centrale

intervention principale

exposition principale

phénomène étudié s’il est réellement spécifique

Exemples de concepts souvent priority = 2

géographie

setting

type de structure

niveau de soins

contexte institutionnel

Stratégie canonique

Le moteur central doit produire deux niveaux logiques.

Wide

Tous les search_elements actifs avec priority = 1

Narrow

Tous les search_elements actifs avec priority = 1 et priority = 2

Important

À ce stade, il ne s’agit pas encore d’une requête de plateforme.
Il s’agit d’une stratégie logique canonique.

Structure attendue
{
  "wide": {
    "elements_used": ["Population", "Condition"]
  },
  "narrow": {
    "elements_used": ["Population", "Condition", "Geography"]
  },
  "excluded": [
    {
      "label": "Prevalence",
      "reason": "Generic measurement outcome, too broad to filter safely"
    }
  ],
  "is_identical": false
}
Requêtes par plateforme

À partir de la stratégie canonique, chaque backend construit la requête réelle propre à sa plateforme.

Principe

Le cœur produit ne génère pas directement une requête finale de base de données.
Il génère une stratégie canonique.
Puis chaque plateforme génère sa requête.

Format cible
{
  "wide": {
    "elements_used": ["Population", "Condition"],
    "platform_queries": {
      "pubmed": "...",
      "scopus": "...",
      "wos": "...",
      "embase": "..."
    }
  },
  "narrow": {
    "elements_used": ["Population", "Condition", "Geography"],
    "platform_queries": {
      "pubmed": "...",
      "scopus": "...",
      "wos": "...",
      "embase": "..."
    }
  }
}
Backends plateforme
Règle générale

Aucun backend ne doit modifier :

l’intent

le framework

les search_elements

search_filter

priority

la logique wide / narrow

Les backends ne font que traduire.

Backend PubMed

Peut utiliser :

champs textuels PubMed

MeSH

API de comptage PubMed

Backend Scopus

Peut utiliser :

champs textuels Scopus

syntaxe Scopus spécifique

Backend Web of Science

Peut utiliser :

syntaxe TS=

logique propre à WoS

Backend Embase

Peut utiliser :

champs textuels Embase

Emtree

syntaxe Embase

Exemples de search elements
Exemple 1 — prévalence du diabète chez les enfants au Mali
"search_elements": [
  {
    "label": "Population",
    "canonical_terms": ["child", "children", "pediatric", "youth"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Population spécifique et centrale"
  },
  {
    "label": "Condition",
    "canonical_terms": ["diabetes", "diabetic", "hyperglycemia", "type 1 diabetes", "type 2 diabetes"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Condition centrale"
  },
  {
    "label": "Geography",
    "canonical_terms": ["Mali", "West Africa", "Sub-Saharan Africa"],
    "controlled_terms": {
      "mesh": ["Africa", "Africa South of the Sahara"],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 2,
    "reason": "Affinement géographique"
  },
  {
    "label": "Measure",
    "canonical_terms": ["burden", "epidemiology", "frequency", "incidence", "prevalence"],
    "controlled_terms": {
      "mesh": ["Prevalence", "Incidence"],
      "emtree": [],
      "other": []
    },
    "search_filter": false,
    "priority": null,
    "reason": "Mesure générique trop large pour filtrer en sécurité"
  }
]
Exemple 2 — adhérence au traitement ARV chez les adolescents au Cameroun
"search_elements": [
  {
    "label": "Population",
    "canonical_terms": ["adolescent", "adolescents", "teenagers", "young adults", "youth"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Population spécifique"
  },
  {
    "label": "Treatment",
    "canonical_terms": ["antiretroviral", "antiretroviral therapy", "ART", "HAART"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Traitement central"
  },
  {
    "label": "Adherence",
    "canonical_terms": ["adherence", "compliance", "medication adherence", "treatment adherence"],
    "controlled_terms": {
      "mesh": ["Medication Adherence", "Patient Compliance", "Treatment Adherence and Compliance"],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Sujet central"
  },
  {
    "label": "Geography",
    "canonical_terms": ["Cameroon", "Central Africa", "Sub-Saharan Africa"],
    "controlled_terms": {
      "mesh": ["Africa", "Africa South of the Sahara"],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 2,
    "reason": "Affinement géographique"
  }
]
Exemple 3 — efficacité de la metformine vs insuline dans le diabète gestationnel
"search_elements": [
  {
    "label": "Population/Condition",
    "canonical_terms": ["gestational diabetes", "pregnancy", "pregnant women"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Population-condition spécifique"
  },
  {
    "label": "Intervention",
    "canonical_terms": ["metformin", "oral hypoglycemic"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Intervention principale"
  }
]

Note :

insulin = comparateur → non filtrant par défaut

Exemple 4 — accidents d’anesthésie
"search_elements": [
  {
    "label": "Context",
    "canonical_terms": ["anaesthesia", "anesthesia", "anaesthetic", "anesthetic", "sedation"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": true,
    "priority": 1,
    "reason": "Contexte central"
  },
  {
    "label": "Complications",
    "canonical_terms": ["accidents", "adverse events", "complications", "incidents", "safety"],
    "controlled_terms": {
      "mesh": [],
      "emtree": [],
      "other": []
    },
    "search_filter": false,
    "priority": null,
    "reason": "Concept trop générique et transversal pour filtrer de façon fiable"
  }
]
Prompt LLM — exigences

Le prompt doit produire :

le bloc pédagogique

le JSON canonique

les search_elements

la détection automatique de l’intent

une sortie stable

Règles du prompt
Intent

question vague ou exploratoire → explore

question précise → structure

Mode explore

2 éléments maximum

tous en priority = 1

objectif : cartographie initiale du sujet

Mode structure

construction normale des éléments

possibilité d’ajouter des éléments priority = 2

Concepts trop génériques

Si un concept est trop générique et applicable à presque tous les domaines :

search_filter = false

priority = null

Comparateur

Le comparateur n’est jamais un filtre actif par défaut.

Canonical terms

rester courts

rester contrôlés

éviter les listes infinies

privilégier les variantes réellement utiles

Controlled terms

facultatifs

organisés par système documentaire

ne jamais être inventés sans contrôle

Robustesse minimale

L’application ne doit jamais planter pour un composant non essentiel.

Règles

si le feedback échoue → message discret, pas de crash

si le comptage d’une plateforme échoue → afficher Résultats indisponibles

si le JSON LLM est partiel → fallback propre

si un backend plateforme échoue → les autres restent utilisables

si une plateforme n’a pas encore de backend → afficher Bientôt disponible

ne jamais afficher d’erreur technique brute à l’utilisateur

Validation minimale du JSON

Avant usage :

intent existe ou fallback sur "structure"

framework existe ou fallback sur null

components existe ou fallback sur objet vide

search_elements existe ou fallback sur liste vide

geography existe ou fallback sur objet null-safe

research_level existe ou fallback sur 2

Workspace interactif

Le workspace manipule les concepts, pas la syntaxe des plateformes.

Règles

les éléments priority = 1 sont préchargés

les éléments priority = 2 sont disponibles pour affinement

les éléments search_filter = false sont visibles mais non activables par défaut

pas de duplication d’un même concept

retirer un concept le remet dans la liste disponible

toute modification met à jour :

la stratégie canonique

les requêtes par plateforme

les compteurs si disponibles

Règle forte

L’UI n’invente aucun concept.
Elle manipule uniquement les search_elements existants.

Architecture conceptuelle
Couche 1 — compréhension

entrée utilisateur

appel LLM

production du JSON canonique

Couche 2 — logique Bramer / stratégie canonique

séparation des concepts actifs et exclus

construction wide

construction narrow

Couche 3 — traduction plateforme

génération des requêtes par backend

comptage éventuel

Couche 4 — rendu UI

pédagogie

transparence

interaction utilisateur

Architecture fichiers
projet/
├── SPEC.md
├── app.py
├── claude_helper.py
├── prompt_core.py
├── examples.json
├── search_strategy.py
├── platform_backends/
│   ├── __init__.py
│   ├── pubmed_backend.py
│   ├── scopus_backend.py
│   ├── wos_backend.py
│   └── embase_backend.py
├── QueryWorkspace.jsx
├── feedback.py
├── requirements.txt
└── .env
Rôle des fichiers

SPEC.md → source de vérité

app.py → interface

claude_helper.py → appel LLM + validation JSON

prompt_core.py → prompt principal

examples.json → exemples few-shot

search_strategy.py → logique Bramer et stratégie canonique wide / narrow

platform_backends/* → traductions par plateforme

QueryWorkspace.jsx → UI interactive

feedback.py → feedback non bloquant

Roadmap d’implémentation

Ordre recommandé :
A → B → C → D → E

Ticket A — Auto intent

Objectif
Supprimer le choix manuel d’intent.
Un seul champ texte. Le LLM détecte l’intent.

Portée

interface d’entrée

récupération de intent

fallback si intent absent

Hors portée

backends multi-plateformes

workspace interactif

Critères d’acceptation

un seul champ texte

pas de radio explore/structure

pas de crash si intent manque

Ticket B — Concepts trop génériques

Objectif
Empêcher l’utilisation comme filtres actifs de concepts trop vagues.

Portée

prompt principal

exemples few-shot

validation sur le cas sentinelle accidents d’anesthésie

Hors portée

UI avancée

architecture backend complète

Critères d’acceptation

complications n’est plus actif par défaut dans les sujets trop larges

moins de stratégies absurdes

le cas accidents d’anesthésie respecte la logique Bramer

Ticket C — UX quand wide == narrow

Objectif
Éviter les doublons visuels quand les deux stratégies sont identiques.

Portée

affichage de la stratégie

note discrète d’affinement

Hors portée

logique Bramer

traduction backend

Critères d’acceptation

une seule stratégie affichée si identiques

pas de doublon visuel

note d’affinement discrète

Ticket D — Validation JSON + robustesse

Objectif
Sécuriser le cœur de l’application.

Portée

validation minimale du JSON

fallback sur valeurs par défaut

gestion propre des erreurs de backend

affichage utilisateur non cassant

Hors portée

refonte complète de tous les backends secondaires

Critères d’acceptation

pas de crash si JSON partiel

pas de crash si un backend échoue

erreurs utilisateur propres

pas de valeur technique brute affichée

Ticket E — Stratégie canonique + requêtes par plateforme + workspace

Objectif
Construire le cœur base-agnostic et afficher les requêtes réelles par plateforme.

Portée

stratégie canonique wide / narrow

traduction par plateforme

transparence des requêtes

workspace basé sur les search_elements

Hors portée

sophistication excessive des backends secondaires

optimisation fine spécifique à chaque plateforme

Critères d’acceptation

le cœur ne dépend pas de PubMed

PubMed reste le premier backend fonctionnel

les requêtes sont visibles par plateforme

le workspace manipule les concepts et non la syntaxe

Dépendances recommandées

A avant C

B avant E

D transverse

E après stabilisation du cœur logique

Cas tests sentinelles

On garde seulement 5 cas tests.

Cas 1 — Prévalence + pays

Exemple :
prévalence du diabète chez les enfants au Mali

Vérifie :

population et condition en priority = 1

géographie en priority = 2

prévalence exclue du filtrage

Cas 2 — Intervention / comparateur

Exemple :
efficacité de la metformine vs insuline dans le diabète gestationnel

Vérifie :

comparateur non filtrant

Cas 3 — Outcome de mesure

Exemple :
incidence de l'hypertension chez les adultes

Vérifie :

incidence non filtrante par défaut

Cas 4 — Question trop large

Exemple :
accidents d’anesthésie

Vérifie :

exclusion des concepts trop génériques

Cas 5 — Sans géographie

Exemple :
adhérence au traitement ARV chez les adolescents

Vérifie :

wide et narrow potentiellement identiques

Philosophie générale

Le produit ne doit pas essayer de prédire tous les cas possibles.

On préfère :

peu de règles

règles fortes

peu de tickets

peu de cas tests

beaucoup de transparence

On évite :

les matrices infinies de cas d’usage

la logique métier dispersée

les heuristiques fragiles

les syntaxes de plateforme au cœur du moteur

Principe final :

Users manipulate concepts; platforms receive syntax.

Règle finale

En cas de doute :

la SPEC prévaut

les règles immuables priment sur les cas particuliers

la logique Bramer gouverne la stratégie canonique

le cœur produit reste indépendant des plateformes

les backends traduisent

l’UI explique