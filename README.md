# Research Companion

Transforme une question de recherche en langage libre en une stratégie documentaire structurée, reproductible et prête à l'emploi sur PubMed.

---

## Ce que ça fait

1. L'utilisateur pose sa question en français ou en anglais, sans connaître PubMed, MeSH ni PICO.
2. L'application détecte l'intent (exploration ou structuration), extrait les concepts, applique la logique Bramer.
3. Elle génère une stratégie **large** et une stratégie **restreinte**, avec les requêtes PubMed correspondantes.
4. L'utilisateur peut affiner les concepts, prioriser, et exporter vers Zotero.

**Cas d'usage typique :** étudiant en médecine, professionnel de santé publique, chercheur qui commence une revue systématique.

---

## Installation

```bash
git clone https://github.com/harold229/research-companion.git
cd research-companion
pip install -r requirements.txt
```

Créer un fichier `.env` à la racine :

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...       # fallback si Claude indisponible
```

Ou pour Streamlit Cloud, renseigner les mêmes clés dans `st.secrets`.

---

## Lancer l'application

```bash
streamlit run app.py
```

---

## Structure du projet

```
research-companion/
├── app.py                   # Interface Streamlit
├── claude_helper.py         # Appel LLM + normalisation du JSON
├── prompt_core.py           # Prompt principal
├── examples.json            # Exemples few-shot pour le LLM
├── search_strategy.py       # Logique Bramer, stratégie canonique wide/narrow
├── services/
│   ├── query_builder.py     # Construction des requêtes par plateforme
│   ├── discovery.py         # Recherche initiale d'articles
│   ├── ranking.py           # Classement hybride
│   ├── concept_classifier.py
│   └── state_manager.py
├── platform_backends/
│   └── pubmed_backend.py    # Backend PubMed (seul actif)
├── ui/
│   ├── results_blocks.py    # Composants d'affichage des articles
│   └── query_panels.py
├── reading_prioritization.py
├── hybrid_reranker.py
├── abstract_reader_agent.py # Lecture et évaluation des abstracts par LLM
├── strategy_pack.py         # Texte explicatif de la stratégie
├── zotero_integration.py    # Export Zotero
├── SPEC.md                  # Source de vérité du projet
└── AGENTS.md                # Guide pour les agents IA qui travaillent sur ce projet
```

---

## Principes clés

- **Le cœur est indépendant des plateformes.** PubMed est le premier backend, pas la limite du produit.
- **L'utilisateur manipule des concepts, les plateformes reçoivent une syntaxe.**
- **Logique Bramer :** seuls les concepts dont l'absence dans un article ferait rater cet article deviennent des filtres actifs.
- **Transparence :** chaque décision d'inclusion ou d'exclusion est expliquée à l'utilisateur.

---

## Modèles LLM utilisés

| Usage | Modèle | Fallback |
|---|---|---|
| Analyse de la question | `claude-sonnet-4-20250514` | `gpt-4o` |
| Lecture des abstracts | `claude-sonnet-4-20250514` | `gpt-4o` |
| Expansion de requête | `claude-sonnet-4-20250514` | `gpt-4o` |

---

## Pour contribuer ou modifier

Lire **SPEC.md** avant tout changement — c'est la source de vérité.
Lire **AGENTS.md** si tu travailles avec un agent IA.

Les règles métier immuables sont dans `SPEC.md > Règles métier immuables`.
Ne pas les modifier sans mettre à jour la SPEC en premier.
