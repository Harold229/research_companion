# SPEC.md — Research Companion

> Source de vérité du projet. À lire avant chaque ticket.
> Dernière mise à jour : mars 2026

---

## Vision produit

Research Companion aide un utilisateur novice en recherche documentaire à transformer un sujet formulé en langage libre en une stratégie de recherche compréhensible, ajustable et exploitable sur plusieurs plateformes bibliographiques.

L'utilisateur n'a pas besoin de connaître : PICO, PEO, SPIDER, Bramer, TIAB, MeSH, Emtree, ni les syntaxes propres à PubMed, Scopus, Web of Science ou Embase. Ces notions travaillent en coulisses.

---

## Principe central

Research Companion n'est pas un produit limité à PubMed.

Le moteur central construit d'abord une **stratégie de recherche canonique**, indépendante de toute plateforme. Cette stratégie est ensuite traduite par un backend spécifique vers PubMed, Scopus, Web of Science, Embase, et d'autres plateformes.

> **Research Companion is not a PubMed-only product. PubMed is the first supported backend, not the product boundary.**

### Deux couches

**Cœur produit**
- compréhension de la question
- détection de l'intent
- extraction des composantes
- construction des `search_elements`
- décision de `search_filter` et attribution de `priority`
- construction logique `wide` / `narrow`
- interaction utilisateur dans le workspace

**Backend plateforme**
- traduction de la stratégie canonique dans une syntaxe plateforme
- ajout éventuel de vocabulaire contrôlé propre à la plateforme
- comptage des résultats si disponible
- export de la requête réelle

> **L'utilisateur manipule des concepts. Les plateformes reçoivent une syntaxe.**

---

## Logique Bramer

La logique Bramer structure le cœur du moteur. Elle sert à identifier les concepts utiles à la recherche, distinguer les concepts à filtrer de ceux à exclure, attribuer les priorités `1` et `2`, et construire une stratégie large puis une stratégie restreinte.

Elle s'applique à la **stratégie canonique**, avant toute traduction plateforme. Les backends ne redéfinissent pas cette logique, ils traduisent uniquement.

Référence : Bramer et al. (2018)

**Principes retenus :**
- Les frameworks comme PICO, PEO ou SPIDER servent à comprendre la question, pas à générer mécaniquement une requête.
- Tous les concepts extraits ne doivent pas devenir des filtres.
- Chaque bloc ajouté en `AND` augmente le risque d'exclure des documents pertinents.
- Il faut commencer large, puis affiner.
- Le comparateur aide à comprendre la question, mais ne doit pas servir de filtre actif par défaut.

**Question Bramer à appliquer à chaque concept :**

> Un document pertinent pourrait-il être utile même s'il ne mentionne pas explicitement ce concept dans les champs textuels recherchés ?

- si oui → `search_filter = false`
- si non → `search_filter = true`

Puis :
- `priority = 1` si le concept est essentiel
- `priority = 2` s'il est utile pour restreindre
- `priority = null` si `search_filter = false`

---

## Flow utilisateur cible

### Écran 1 — Entrée
Un seul champ texte : **Quel est votre sujet de recherche ?** L'utilisateur écrit en langage libre (français ou anglais). Pas de choix manuel `explore` / `structure` — l'intent est détecté automatiquement.

### Écran 2 — Compréhension
L'application montre ce qu'elle a compris : reformulation éventuelle, framework identifié, composantes extraites, niveau de précision, concepts retenus, concepts exclus du filtrage et pourquoi.

### Écran 3 — Stratégie canonique
- stratégie **large** = `priority = 1`
- stratégie **restreinte** = `priority = 1 + 2`
- un court texte expliquant les deux niveaux

### Écran 4 — Requêtes par plateforme
Pour chaque stratégie, les requêtes réelles par plateforme disponible (PubMed en premier).

### Cas particulier — wide == narrow
Si les deux stratégies sont logiquement identiques : afficher une seule stratégie + une note discrète d'affinement suggérant pays, contexte, population ou cadre d'étude.

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
- Un concept exclu reste visible dans l'interface avec sa justification.
- Le workspace manipule des concepts, pas des syntaxes de plateforme.
- Le code applicatif n'invente pas de nouvelle logique métier en dehors de la SPEC et du prompt.

---

## Concepts qui ne doivent pas filtrer par défaut

**Comparateur** — ex. : `versus insulin`, `compared with placebo`, `compared to standard care`

**Outcomes de mesure génériques** — ex. : `prevalence`, `incidence`, `frequency`, `burden`, `epidemiology`, `mortality rate`, `morbidity rate`

**Concepts trop génériques** — ex. : `complications`, `adverse events`, `incidents`, `safety`, `burden`, `epidemiology`, `frequency`, `outcomes`

Ces concepts peuvent être affichés pédagogiquement, mais ne doivent pas devenir des filtres actifs par défaut, sauf justification explicite et exceptionnelle.

---

## Structure canonique du JSON

Le LLM produit un JSON unique représentant la question de manière indépendante de toute plateforme.

```json
{
  "intent": "explore | structure",
  "framework": "PICO | PEO | SPIDER | null",
  "explanation": "...",
  "research_question_fr": "...",
  "research_question_en": "...",
  "research_question_comment": "...",
  "geography": {
    "country": "... | null",
    "region": "... | null",
    "continent": "... | null"
  },
  "components": {
    "population": "... | null",
    "intervention": "... | null",
    "comparison": "... | null",
    "outcome": "... | null",
    "exposure": "... | null",
    "setting": "... | null"
  },
  "search_elements": [
    {
      "label": "Short concept label",
      "tiab": "term1 OR term2 OR term3",
      "mesh": "MeSH Term 1 OR MeSH Term 2 | null",
      "search_filter": true,
      "priority": 1,
      "reason": "Short justification"
    }
  ],
  "research_level": 2
}
```

### Interprétation

| Champ | Rôle |
|---|---|
| `intent` | `explore` = question large, `structure` = question précise |
| `framework` | Usage pédagogique uniquement |
| `components` | Explique ce qui a été compris — pas la stratégie |
| `search_elements` | Matière première de la stratégie canonique |
| `tiab` | Termes textuels (Title/Abstract) |
| `mesh` | Vocabulaire contrôlé PubMed (null si non applicable) |
| `research_level` | 1 = exploratoire, 2 = normal, 3 = précis |

### Règles search_elements

- `search_filter = true` → le concept entre dans la stratégie
- `search_filter = false` → visible mais exclu
- `priority = 1` → concept central (wide + narrow)
- `priority = 2` → concept d'affinement (narrow seulement)
- `priority = null` → toujours si `search_filter = false`

**Souvent `priority = 1` :** population spécifique, condition centrale, intervention principale, exposition principale.

**Souvent `priority = 2` :** géographie, setting, type de structure, niveau de soins.

---

## Stratégie canonique wide / narrow

```json
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
```

**Wide** = tous les `search_elements` actifs avec `priority = 1`

**Narrow** = tous les `search_elements` actifs avec `priority = 1` et `priority = 2`

À ce stade, c'est une stratégie logique canonique, pas encore une requête de plateforme.

---

## Requêtes par plateforme

À partir de la stratégie canonique, chaque backend construit la requête réelle.

```json
{
  "wide": {
    "elements_used": ["Population", "Condition"],
    "platform_queries": {
      "pubmed": "...",
      "scopus": "...",
      "wos": "..."
    }
  },
  "narrow": {
    "elements_used": ["Population", "Condition", "Geography"],
    "platform_queries": {
      "pubmed": "...",
      "scopus": "...",
      "wos": "..."
    }
  }
}
```

**Règle générale des backends :** aucun backend ne modifie l'intent, le framework, les search_elements, search_filter, priority, ni la logique wide/narrow. Les backends ne font que traduire.

---

## Exemples de search_elements

### Prévalence du diabète chez les enfants au Mali

```json
[
  {
    "label": "Population",
    "tiab": "\"child\"[tiab] OR \"children\"[tiab] OR \"pediatric\"[tiab]",
    "mesh": null,
    "search_filter": true,
    "priority": 1,
    "reason": "Population spécifique et centrale"
  },
  {
    "label": "Condition",
    "tiab": "\"diabetes\"[tiab] OR \"diabetic\"[tiab] OR \"type 1 diabetes\"[tiab] OR \"type 2 diabetes\"[tiab]",
    "mesh": null,
    "search_filter": true,
    "priority": 1,
    "reason": "Condition centrale"
  },
  {
    "label": "Geography",
    "tiab": "\"Mali\"[tiab] OR \"West Africa\"[tiab]",
    "mesh": "\"Africa South of the Sahara\"[mesh]",
    "search_filter": true,
    "priority": 2,
    "reason": "Affinement géographique"
  },
  {
    "label": "Measure",
    "tiab": "\"prevalence\"[tiab]",
    "mesh": null,
    "search_filter": false,
    "priority": null,
    "reason": "Mesure générique trop large pour filtrer en sécurité"
  }
]
```

### Efficacité de la metformine vs insuline dans le diabète gestationnel

```json
[
  {
    "label": "Population/Condition",
    "tiab": "\"gestational diabetes\"[tiab] OR \"pregnant women\"[tiab]",
    "mesh": null,
    "search_filter": true,
    "priority": 1,
    "reason": "Population-condition spécifique"
  },
  {
    "label": "Intervention",
    "tiab": "\"metformin\"[tiab] OR \"oral hypoglycemic\"[tiab]",
    "mesh": null,
    "search_filter": true,
    "priority": 1,
    "reason": "Intervention principale"
  }
]
```

> Note : `insulin` = comparateur → non filtrant par défaut.

### Accidents d'anesthésie

```json
[
  {
    "label": "Context",
    "tiab": "\"anaesthesia\"[tiab] OR \"anesthesia\"[tiab] OR \"sedation\"[tiab]",
    "mesh": null,
    "search_filter": true,
    "priority": 1,
    "reason": "Contexte central"
  },
  {
    "label": "Complications",
    "tiab": "\"accidents\"[tiab] OR \"adverse events\"[tiab] OR \"complications\"[tiab]",
    "mesh": null,
    "search_filter": false,
    "priority": null,
    "reason": "Concept trop générique et transversal pour filtrer de façon fiable"
  }
]
```

---

## Règles du prompt LLM

**Intent**
- question vague ou exploratoire → `explore`
- question précise → `structure`

**Mode explore**
- 2 éléments maximum, tous en `priority = 1`
- objectif : cartographie initiale

**Mode structure**
- construction normale, possibilité d'éléments `priority = 2`

**Termes TIAB**
- rester courts et contrôlés
- éviter les listes infinies
- privilégier les variantes réellement utiles
- chaque terme tagger individuellement (`"term"[tiab]`)

**Robustesse minimale**
- si le feedback échoue → message discret, pas de crash
- si le comptage d'une plateforme échoue → afficher "Résultats indisponibles"
- si le JSON LLM est partiel → fallback propre
- jamais d'erreur technique brute affichée à l'utilisateur

---

## Architecture

```
Couche 1 — Compréhension
  entrée utilisateur → appel LLM → JSON canonique

Couche 2 — Logique Bramer / stratégie canonique
  concepts actifs / exclus → construction wide → construction narrow

Couche 3 — Traduction plateforme
  génération des requêtes par backend → comptage éventuel

Couche 4 — Rendu UI
  pédagogie · transparence · interaction utilisateur
```

---

## Cas tests sentinelles

| # | Exemple | Ce qui est vérifié |
|---|---|---|
| 1 | Prévalence du diabète chez les enfants au Mali | population + condition en priority 1, géographie en priority 2, prévalence exclue |
| 2 | Efficacité de la metformine vs insuline dans le diabète gestationnel | comparateur non filtrant |
| 3 | Incidence de l'hypertension chez les adultes | incidence non filtrante par défaut |
| 4 | Accidents d'anesthésie | exclusion des concepts trop génériques |
| 5 | Adhérence au traitement ARV chez les adolescents | wide et narrow potentiellement identiques |

---

## Philosophie

On préfère : peu de règles, règles fortes, peu de tickets, peu de cas tests, beaucoup de transparence.

On évite : les matrices infinies de cas d'usage, la logique métier dispersée, les heuristiques fragiles, les syntaxes de plateforme au cœur du moteur.

**En cas de doute :** la SPEC prévaut. Les règles immuables priment sur les cas particuliers. La logique Bramer gouverne la stratégie canonique. Le cœur reste indépendant des plateformes. Les backends traduisent. L'UI explique.

> **Users manipulate concepts; platforms receive syntax.**
