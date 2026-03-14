# AGENTS.md

## Project
Research Companion is a Streamlit app that helps users go from a free-text research topic
to plausible scientific articles, a suggested search query, and then a refinable search strategy.

## Current product direction
The product is being refactored from:

topic -> PICO/query -> maybe 0 results

to:

topic -> first plausible articles -> suggested query -> refinement

The main UX principle is:
**value first, explanation second**.

Users should first see:
1. what the app understood
2. plausible articles
3. a suggested query

Only after that should they see:
- concept editor
- detailed strategy
- methodology details
- advanced options
- projects
- Zotero
- premium/paywall

## Non-goals for this refactor
Do not:
- redesign the whole app
- migrate away from Streamlit
- introduce a large frontend framework
- add unrelated premium features
- add complex collaboration/auth unless explicitly requested
- over-engineer abstractions

## Technical constraints
- Keep Streamlit
- Separate business logic from UI as much as reasonably possible
- Prefer small, composable service modules over app.py-heavy logic
- Keep code readable and incremental
- Avoid breaking the existing app flow unless the ticket explicitly asks for it

## Preferred architecture direction
Use modules like:

- services/discovery.py
- services/query_builder.py
- services/ranking.py
- models/search_session.py
- models/search_strategy.py

These names are suggestions, not hard requirements.
The important thing is to move business logic out of the Streamlit page code.

## Product rules
- Never leave the user with a bare "0 results"
- The initial query should be broad and plausible
- Concepts should have roles, not all be treated the same
- Prioritization should stay anchored to the original topic
- Detailed explanations should be hidden by default
- The app should remain useful for a novice researcher

## Concept roles
When relevant, concepts should be classified into:
- core
- refinement
- ranking
- context

Typical meaning:
- core: essential to the topic
- refinement: useful to narrow results
- ranking: useful to sort results, not always mandatory in the query
- context: geography, setting, time frame, etc.

## Streamlit rules
- New searches must start from clean state
- Avoid session_state leaks between topics
- Do not mutate widget-backed session_state keys after widget instantiation
- Seed widget state before creating widgets
- Use forms when it reduces noisy reruns
- Use session_state deliberately and minimally

## UX rules
Default visible sections should be lightweight.
Show first:
- topic input
- what I understood
- articles to read first
- suggested query

Hide or collapse by default:
- why this article
- methodology details
- concept editor
- advanced strategy explanations
- long justifications

## Query rules
- Suggested queries must be valid in PubMed
- For PubMed text fields, tag each term individually
- Prefer [tiab] over applying one field tag to a full OR block
- Avoid bloated or weak synonyms
- For prevalence questions, do not use a broad “epidemiology/frequency/incidence/burden/prevalence” block by default
- Use only exact epidemiologic terms when they truly match the topic

## Ranking rules
- Ranking must stay anchored to the original topic
- General field relevance must not outrank direct subject centrality
- A near-exact title match should receive a strong boost
- Recency is secondary, not the main reason
- Distinguish between:
  - central to the exact topic
  - useful context
  - peripheral

## Connected-article rules
If generating “related articles” from a selected article:
- keep the original topic as the main anchor
- use the chosen article as a secondary anchor
- do not drift toward articles that only share country, journal, or general topic

## Delivery rules for Codex
For each task:
- inspect the existing code first
- implement the smallest clean version
- do not refactor unrelated areas
- run tests/lint if available
- summarize:
  1. changed files
  2. what was implemented
  3. checks performed
  4. remaining limitations

## Communication style in outputs
Be concise and concrete.
Prefer:
- changed files
- behavior changes
- checks run
- limitations

Avoid:
- vague summaries
- product essays
- unrelated suggestions