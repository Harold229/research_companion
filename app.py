import json

import streamlit as st

from abstract_reader_agent import assess_shortlist_with_agent
from abstract_reader_agent import build_shortlist_for_agent
from concept_editor import apply_editor_changes
from concept_editor import clone_search_elements
from concept_editor import EDITOR_STATE_OPTIONS
from concept_editor import get_editor_state
from concept_editor import serialize_terms
from feedback import save_feedback
from hybrid_reranker import rerank_articles_hybrid
from paywall_tracking import build_paywall_payload
from paywall_tracking import DEFAULT_PRICES
from paywall_tracking import get_session_id
from paywall_tracking import send_paywall_event
from platform_backends import pubmed_backend
from question_display import get_component_label
from question_display import get_question_presentation
from question_display import get_reformulated_question
from question_display import get_visible_explanation
from query_expansion import apply_expansion_terms
from query_expansion import build_expansion_shortlist
from query_expansion import propose_query_expansion
from query_expansion import RECOMMENDATION_LABELS
from related_articles import build_related_articles_query
from research_projects import create_project
from research_projects import get_project_by_id
from research_projects import get_recent_entries
from research_projects import load_projects
from research_projects import save_project_articles
from research_projects import save_project_zotero_target
from research_projects import save_entry_to_project
from reading_prioritization import FOCUS_OPTIONS
from reading_prioritization import apply_agent_assessment
from services.discovery import discover_articles
from services.discovery import run_topic_discovery
from services.query_builder import build_query_package
from services.query_builder import build_query_package_for_elements
from services.state_manager import load_analysis_entry
from services.state_manager import reset_search_state
from strategy_pack import build_search_strategy_pack
from ui.results_blocks import render_article_details
from ui.results_blocks import render_article_feedback_controls
from ui.results_blocks import render_article_reasons
from zotero_ready import build_zotero_ready_export
from zotero_ready import build_zotero_ready_json
from zotero_ready import build_zotero_ready_markdown
from zotero_integration import build_zotero_target_mapping
from zotero_integration import clear_zotero_connection
from zotero_integration import fetch_zotero_collections
from zotero_integration import fetch_zotero_items_preview
from zotero_integration import get_default_zotero_api_key
from zotero_integration import get_zotero_connection
from zotero_integration import validate_zotero_api_key
from zotero_integration import ZoteroIntegrationError


count_geographic_scopes = pubmed_backend.count_geographic_scopes
fetch_articles = pubmed_backend.fetch_articles
apply_pubmed_date_filter = pubmed_backend.apply_pubmed_date_filter
fetch_cited_articles = getattr(pubmed_backend, "fetch_cited_articles", lambda pmid, max_results=12: [])


def format_results_count(count) -> str:
    return str(count) if isinstance(count, int) and count >= 0 else "Résultats indisponibles"


def get_article_badge(article: dict) -> str:
    band = article.get("centrality_band")
    if band == "central":
        return "Article central"
    if band == "useful":
        return "Utile pour le sujet"
    if band == "contextual":
        return "Article de contexte"
    reasons = article.get("reasons", []) or []
    if reasons:
        return reasons[0]
    return "Article retenu"


def get_reference_badge(article: dict) -> str:
    score = float(article.get("hybrid_score", 0.0) or 0.0)
    if score >= 0.55:
        return "Article de base"
    if score >= 0.3:
        return "Référence citée utile"
    return "Référence de contexte"


def get_rank_caption(article: dict) -> str:
    app_rank = article.get("app_rank")
    pubmed_rank = article.get("pubmed_rank")
    parts = []
    if isinstance(app_rank, int):
        parts.append(f"Rang app {app_rank}")
    if isinstance(pubmed_rank, int):
        parts.append(f"Rang PubMed {pubmed_rank}")

    rank_delta = article.get("rank_delta")
    if isinstance(rank_delta, int) and rank_delta != 0:
        if rank_delta > 0:
            parts.append(f"Remonté de {rank_delta} place{'s' if rank_delta > 1 else ''}")
        else:
            delta = abs(rank_delta)
            parts.append(f"Descendu de {delta} place{'s' if delta > 1 else ''}")

    return " • ".join(parts)


def get_pack_preview(pack: str, max_lines: int = 18) -> str:
    lines = pack.splitlines()
    if len(lines) <= max_lines:
        return pack
    return "\n".join(lines[:max_lines]) + "\n\n[... aperçu tronqué ...]"


def get_entry_title(entry: dict) -> str:
    title = entry.get("reformulated_question") or entry.get("user_question") or "Recherche récente"
    return title if len(title) <= 90 else f"{title[:87]}..."


def build_history_entry(
    user_question: str,
    result: dict,
    strategy: dict,
    platform_outputs: dict,
    pack: str,
    search_session_id: str,
) -> dict:
    presentation = get_question_presentation(result, user_question)
    reformulated = get_reformulated_question(user_question, result, presentation)
    from datetime import datetime
    now = datetime.now()
    return {
        "id": now.strftime("%Y%m%d%H%M%S%f"),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "user_question": user_question,
        "reformulated_question": reformulated,
        "framework": result.get("framework"),
        "search_session_id": search_session_id,
        "result": result,
        "strategy": strategy,
        "platform_outputs": platform_outputs,
        "pack": pack,
    }


def render_suggested_query(bramer: dict) -> None:
    large = bramer.get("large", {})
    strict = bramer.get("strict", {})
    is_identical = bramer.get("is_identical", False)

    st.subheader("Requête proposée")
    st.caption("Commencez par une requête plausible et lisible, puis affinez seulement si nécessaire.")

    st.write("**Version large**")
    st.code(large.get("query", ""), language="text")
    if large.get("elements_used"):
        st.caption(f"Concepts inclus : {', '.join(large.get('elements_used', []))}")

    if is_identical:
        st.caption(
            "Aucun filtre supplémentaire pertinent n’a été identifié. "
            "La version large suffit pour démarrer."
        )
    else:
        st.write("**Version ciblée**")
        st.code(strict.get("query", ""), language="text")
        added = [
            element
            for element in strict.get("elements_used", [])
            if element not in large.get("elements_used", [])
        ]
        if added:
            st.caption(f"Cette version ajoute : {', '.join(added)}")


def render_what_i_understood(
    *,
    question: str,
    components: dict,
    presentation: dict,
    reformulated_question: str,
    visible_explanation: str,
    project_title: str = "",
) -> None:
    st.subheader("Ce que j’ai compris")
    if project_title:
        st.caption(f"Projet : {project_title}")

    normalized_question = " ".join(str(question or "").split()).strip()
    normalized_reformulation = " ".join(str(reformulated_question or "").split()).strip()

    if normalized_reformulation and normalized_reformulation.lower() != normalized_question.lower():
        st.write(f"**Reformulation** : {reformulated_question}")
    else:
        st.write(f"**Sujet** : {question}")

    st.write(f"**Type de sujet** : {presentation.get('question_type', 'question descriptive')}")

    main_dimensions = []
    for key, value in (components or {}).items():
        if value:
            label = get_component_label(key, presentation)
            main_dimensions.append(f"{label} : {value}")

    if main_dimensions:
        st.caption("Dimensions principales : " + " • ".join(main_dimensions[:3]))

    if visible_explanation:
        st.caption(visible_explanation)


def _get_articles_cache_key(entry: dict, query: str, scope: str = "default") -> str:
    return f"article_cache_{entry.get('id')}_{scope}_{hash(query)}"


def _get_expansion_signature(query: str, search_elements: list) -> str:
    payload = json.dumps(search_elements or [], ensure_ascii=False, sort_keys=True)
    return f"{hash(query)}_{hash(payload)}"


def _get_editor_elements(entry: dict) -> list:
    key = f"concept_editor_elements_{entry.get('id')}"
    original_key = f"concept_editor_original_{entry.get('id')}"
    if original_key not in st.session_state:
        st.session_state[original_key] = clone_search_elements((entry.get("result") or {}).get("search_elements") or [])
    if key not in st.session_state:
        st.session_state[key] = clone_search_elements(st.session_state[original_key])
        _seed_editor_widget_state(entry, st.session_state[key])
    return st.session_state[key]


def _seed_editor_widget_state(entry: dict, elements: list) -> None:
    entry_id = entry.get("id")
    for index, element in enumerate(elements):
        st.session_state[f"concept_state_{entry_id}_{index}"] = get_editor_state(element)
        st.session_state[f"concept_tiab_{entry_id}_{index}"] = serialize_terms(element.get("tiab"))
        st.session_state[f"concept_mesh_{entry_id}_{index}"] = str(element.get("mesh") or "")
        st.session_state[f"concept_remove_{entry_id}_{index}"] = False


def _build_effective_analysis(entry: dict) -> tuple:
    edited_elements = _get_editor_elements(entry)
    query_package = build_query_package_for_elements(entry.get("result") or {}, clone_search_elements(edited_elements))
    effective_result = query_package.get("result", {})
    effective_strategy = query_package.get("strategy", {})
    effective_bramer = (query_package.get("platform_outputs") or {}).get("PubMed", {})
    return effective_result, effective_strategy, effective_bramer


def render_concept_editor(entry: dict) -> None:
    entry_id = entry.get("id")
    elements = _get_editor_elements(entry)

    st.subheader("Concept Editor")
    st.caption("Modifiez les concepts avant de relancer votre lecture des résultats. Les requêtes PubMed affichées plus bas se mettront à jour en conséquence.")

    if not elements:
        st.caption("Aucun concept éditable n’est disponible pour cette stratégie.")
        return

    for index, element in enumerate(elements):
        label = element.get("label", f"Concept {index + 1}")
        st.markdown(f"**{label}**")
        st.selectbox(
            "Utilisation du concept",
            options=list(EDITOR_STATE_OPTIONS.keys()),
            format_func=lambda value: EDITOR_STATE_OPTIONS[value],
            key=f"concept_state_{entry_id}_{index}",
        )
        st.text_area(
            "Termes de recherche (anglais, un terme par ligne)",
            key=f"concept_tiab_{entry_id}_{index}",
            height=110,
        )
        st.text_input(
            "Termes contrôlés (MeSH, si disponibles)",
            key=f"concept_mesh_{entry_id}_{index}",
        )
        st.checkbox(
            "Retirer complètement ce concept",
            key=f"concept_remove_{entry_id}_{index}",
        )
        st.caption("Impact : large = présent dans les deux versions ; restreinte = ajouté seulement dans la version plus ciblée ; non utilisé = visible mais retiré du filtrage.")
        st.markdown("---")

    action_cols = st.columns(2)
    if action_cols[0].button("Mettre à jour la stratégie", key=f"apply_concept_editor_{entry_id}"):
        edited_rows = []
        for index, _ in enumerate(elements):
            edited_rows.append({
                "state": st.session_state.get(f"concept_state_{entry_id}_{index}", "excluded"),
                "tiab": st.session_state.get(f"concept_tiab_{entry_id}_{index}", ""),
                "mesh": st.session_state.get(f"concept_mesh_{entry_id}_{index}", ""),
                "removed": st.session_state.get(f"concept_remove_{entry_id}_{index}", False),
            })

        updated_elements = apply_editor_changes(elements, edited_rows)
        st.session_state[f"concept_editor_elements_{entry_id}"] = updated_elements
        _seed_editor_widget_state(entry, updated_elements)
        st.session_state.pop(f"prioritized_articles_{entry_id}", None)
        st.success("Stratégie mise à jour.")
        st.rerun()

    if action_cols[1].button("Réinitialiser la stratégie proposée", key=f"reset_concept_editor_{entry_id}"):
        original_elements = clone_search_elements(st.session_state.get(f"concept_editor_original_{entry_id}", []))
        st.session_state[f"concept_editor_elements_{entry_id}"] = original_elements
        _seed_editor_widget_state(entry, original_elements)
        st.session_state.pop(f"prioritized_articles_{entry_id}", None)
        st.success("Stratégie réinitialisée.")
        st.rerun()


def render_query_expansion(entry: dict, result: dict, strategy: dict, bramer: dict, time_filter: dict) -> None:
    search_elements = result.get("search_elements") or []
    if not search_elements:
        return

    base_query = bramer["large"]["query"]
    if not base_query:
        return

    filtered_query = apply_pubmed_date_filter(
        base_query,
        start_year=time_filter.get("start_year", ""),
        end_year=time_filter.get("end_year", ""),
    )
    signature = _get_expansion_signature(filtered_query, search_elements)
    proposals_key = f"query_expansion_proposals_{entry.get('id')}"
    signature_key = f"query_expansion_signature_{entry.get('id')}"
    enriched_key = f"query_expansion_enriched_{entry.get('id')}"

    if st.session_state.get(signature_key) != signature:
        st.session_state.pop(proposals_key, None)
        st.session_state.pop(enriched_key, None)
        st.session_state[signature_key] = signature

    st.divider()
    st.subheader("Expansion guidée de la requête")
    st.caption(
        "À partir des premiers articles trouvés, l’app peut proposer quelques termes réellement utilisés dans la littérature pour enrichir une version optionnelle de la requête."
    )
    if time_filter.get("enabled") and time_filter.get("valid"):
        st.caption(f"La lecture initiale des articles respecte actuellement la période : {time_filter.get('label')}.")

    if st.button("Proposer des termes d’expansion", key=f"query_expansion_run_{entry.get('id')}"):
        cache_key = _get_articles_cache_key(entry, filtered_query, scope="expansion")
        articles = st.session_state.get(cache_key)
        if articles is None:
            with st.spinner("Récupération d’un noyau initial d’articles..."):
                articles = fetch_articles(filtered_query, max_results=12)
            st.session_state[cache_key] = articles

        if not articles:
            st.caption("Aucun article initial n’a pu être récupéré pour proposer une expansion.")
        else:
            shortlist = build_expansion_shortlist(articles)
            try:
                with st.spinner("Lecture des premiers titres et abstracts pour proposer des termes..."):
                    proposals = propose_query_expansion(shortlist, search_elements, entry.get("user_question", ""))
                st.session_state[proposals_key] = {
                    "shortlist_size": len(shortlist),
                    "proposals": proposals.get("proposals", []),
                    "base_query": base_query,
                    "filtered_query": filtered_query,
                }
            except Exception:
                st.caption("La proposition d’expansion est indisponible pour le moment.")

    proposals_state = st.session_state.get(proposals_key)
    if not proposals_state:
        return

    proposals = proposals_state.get("proposals", [])
    if not proposals:
        st.caption("Aucun terme d’expansion prudent n’a été proposé à partir de ce premier noyau d’articles.")
        return

    st.caption(
        f"{proposals_state.get('shortlist_size', 0)} article(s) ont été lus sur titre + abstract. Vous gardez le contrôle : chaque terme peut être accepté, refusé ou reformulé."
    )

    selected_proposals = []
    for index, proposal in enumerate(proposals):
        proposal_id = proposal.get("proposal_id", f"T{index + 1}")
        include_key = f"query_expansion_include_{entry.get('id')}_{proposal_id}"
        term_key = f"query_expansion_term_{entry.get('id')}_{proposal_id}"

        if include_key not in st.session_state:
            st.session_state[include_key] = proposal.get("recommendation") != "prudente"
        if term_key not in st.session_state:
            st.session_state[term_key] = proposal.get("term", "")

        st.markdown(f"**{proposal.get('term', 'Terme proposé')}**")
        st.caption(
            f"Concept cible : {proposal.get('target_concept', 'Concept')} • "
            f"{RECOMMENDATION_LABELS.get(proposal.get('recommendation'), 'Recommandation utile')}"
        )
        row_cols = st.columns([1, 3])
        row_cols[0].checkbox("Ajouter", key=include_key)
        row_cols[1].text_input(
            "Terme éditable",
            key=term_key,
        )
        with st.expander("Pourquoi cette proposition ?", expanded=False):
            st.caption(proposal.get("reason", ""))
        st.markdown("---")

        if st.session_state.get(include_key):
            edited_term = str(st.session_state.get(term_key, "")).strip()
            if edited_term:
                selected_proposals.append({
                    **proposal,
                    "term": edited_term,
                })

    if st.button("Générer la requête enrichie", key=f"query_expansion_build_{entry.get('id')}"):
        if not selected_proposals:
            st.caption("Sélectionnez au moins un terme à ajouter.")
        else:
            enriched_result = dict(result)
            enriched_result["search_elements"] = apply_expansion_terms(search_elements, selected_proposals)
            enriched_query_package = build_query_package(enriched_result)
            st.session_state[enriched_key] = {
                "selected_proposals": selected_proposals,
                "result": enriched_query_package.get("result", {}),
                "strategy": enriched_query_package.get("strategy", {}),
                "bramer": (enriched_query_package.get("platform_outputs") or {}).get("PubMed", {}),
            }

    enriched_state = st.session_state.get(enriched_key)
    if not enriched_state:
        return

    enriched_bramer = enriched_state.get("bramer", {})
    st.write("**Requête initiale**")
    st.code(base_query, language="text")
    st.caption(f"Résultats observés : {format_results_count(bramer['large'].get('count'))}")

    st.write("**Requête enrichie proposée**")
    st.code(enriched_bramer.get("large", {}).get("query", ""), language="text")
    st.caption(
        f"Résultats observés : {format_results_count(enriched_bramer.get('large', {}).get('count'))}"
    )
    st.caption(
        "Cette version enrichie reste distincte de la requête initiale. Elle ajoute uniquement les termes que vous avez validés à partir des premiers articles lus."
    )

    if not enriched_bramer.get("is_identical"):
        st.write("**Version restreinte enrichie**")
        st.code(enriched_bramer.get("strict", {}).get("query", ""), language="text")
        st.caption(
            f"Résultats observés : {format_results_count(enriched_bramer.get('strict', {}).get('count'))}"
        )


def _validate_year_input(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if len(text) == 4 and text.isdigit() else None


def _get_time_filter_state(entry: dict) -> dict:
    entry_id = entry.get("id")
    mode = st.session_state.get(f"time_filter_mode_{entry_id}", "Aucune limite")
    start_raw = st.session_state.get(f"time_filter_start_{entry_id}", "")
    end_raw = st.session_state.get(f"time_filter_end_{entry_id}", "")
    start_year = _validate_year_input(start_raw)
    end_year = _validate_year_input(end_raw)

    if mode == "Aucune limite":
        return {
            "enabled": False,
            "valid": True,
            "start_year": "",
            "end_year": "",
            "label": "",
            "error": "",
        }

    if start_year is None or end_year is None:
        return {
            "enabled": True,
            "valid": False,
            "start_year": "",
            "end_year": "",
            "label": "",
            "error": "Saisissez des années au format AAAA.",
        }

    if start_year and end_year and int(start_year) > int(end_year):
        return {
            "enabled": True,
            "valid": False,
            "start_year": start_year,
            "end_year": end_year,
            "label": "",
            "error": "La borne de début doit être inférieure ou égale à la borne de fin.",
        }

    if start_year and end_year:
        label = f"{start_year}–{end_year}"
    elif start_year:
        label = f"Depuis {start_year}"
    elif end_year:
        label = f"Jusqu’à {end_year}"
    else:
        label = ""

    return {
        "enabled": bool(start_year or end_year),
        "valid": True,
        "start_year": start_year or "",
        "end_year": end_year or "",
        "label": label,
        "error": "",
    }


def render_zotero_connection(project) -> None:
    with st.expander("Connexion Zotero", expanded=False):
        connection = get_zotero_connection()

        if connection:
            st.caption(
                f"Compte connecté : {connection.get('username', 'Inconnu')} • "
                f"Bibliothèque {connection.get('library_type', 'user')} {connection.get('user_id', '')}"
            )
            if st.button("Déconnecter Zotero", key="disconnect_zotero"):
                clear_zotero_connection()
                st.success("Connexion Zotero supprimée.")
                return
        else:
            default_key = get_default_zotero_api_key()
            api_key = st.text_input(
                "Clé API Zotero",
                value=default_key,
                type="password",
                key="zotero_api_key_input",
            )
            if st.button("Connecter Zotero", key="connect_zotero"):
                try:
                    connection = validate_zotero_api_key(api_key)
                    st.session_state["zotero_connection"] = connection
                    st.success("Compte Zotero connecté.")
                except ZoteroIntegrationError as exc:
                    st.caption(str(exc))
                    return

        connection = get_zotero_connection()
        if not connection:
            st.caption("Aucun compte Zotero connecté.")
            return

        try:
            collections = fetch_zotero_collections(connection)
            st.session_state["zotero_collections"] = collections
        except ZoteroIntegrationError as exc:
            st.caption(str(exc))
            return

        if not collections:
            st.caption("La bibliothèque Zotero ne contient pas encore de collection.")
            return

        collection_options = {item["key"]: item for item in collections if item.get("key")}
        selected_key = st.selectbox(
            "Collection cible",
            options=list(collection_options.keys()),
            format_func=lambda key: collection_options[key]["name"],
            key="zotero_selected_collection_key",
        )
        selected_collection = collection_options.get(selected_key, {})
        st.caption(f"Collection utilisée : {selected_collection.get('name', 'Non définie')}")

        try:
            preview_items = fetch_zotero_items_preview(connection, selected_key)
            st.session_state["zotero_items_preview"] = preview_items
        except ZoteroIntegrationError as exc:
            st.caption(str(exc))
            preview_items = []

        if preview_items:
            st.caption("Aperçu des références déjà présentes dans cette collection :")
            for item in preview_items[:5]:
                st.caption(
                    f"- {item.get('title', 'Référence sans titre')} • {item.get('itemType', '')} • {item.get('date', '')}"
                )
        else:
            st.caption("Aucune référence disponible dans cette collection ou aperçu indisponible.")

        if project and selected_collection:
            zotero_mapping = build_zotero_target_mapping(
                project,
                {"articles": project.get("saved_articles", [])},
                selected_collection,
                connection,
            )
            try:
                save_project_zotero_target(project["id"], zotero_mapping)
            except Exception:
                st.caption("La collection cible Zotero n’a pas pu être enregistrée dans le projet.")


def render_zotero_ready_section(entry: dict, prioritized: dict, result: dict = None) -> None:
    if not prioritized or not prioritized.get("articles"):
        return

    export_data = build_zotero_ready_export(
        prioritized,
        result or entry.get("result") or {},
        user_question=entry.get("user_question", ""),
        reformulated_question=entry.get("reformulated_question", ""),
        project_title=entry.get("project_title", ""),
    )
    markdown_export = build_zotero_ready_markdown(export_data)
    json_export = build_zotero_ready_json(export_data)

    st.divider()
    st.subheader("Articles retenus et argumentaire")
    st.caption("Sortie structurée réutilisable plus tard pour des tags, notes et collections Zotero.")

    with st.expander("Voir l’export Zotero-ready", expanded=False):
        for article in export_data.get("articles", [])[:5]:
            st.markdown(f"**{article.get('title') or 'Article sans titre'}**")
            st.caption(
                f"{article.get('priority', 'À vérifier')} • {article.get('source', 'Source non précisée')} • "
                f"{article.get('year', 'Année non précisée')}"
            )
            st.caption(f"Tags suggérés : {', '.join(article.get('tags', [])) or 'Aucun tag'}")
            with st.expander("Pourquoi cet article ?", expanded=False):
                st.caption(f"Justification : {article.get('justification', 'Non précisée')}")
                st.caption(f"Note d’argumentaire : {article.get('argument_note', 'Non précisée')}")

        st.download_button(
            "Télécharger en JSON",
            data=json_export,
            file_name="zotero_ready_articles.json",
            mime="application/json",
            key=f"download_zotero_json_{entry.get('id')}",
        )
        st.download_button(
            "Télécharger en Markdown",
            data=markdown_export,
            file_name="zotero_ready_articles.md",
            mime="text/markdown",
            key=f"download_zotero_md_{entry.get('id')}",
        )

    if entry.get("project_id"):
        try:
            save_project_articles(entry["project_id"], export_data)
        except Exception:
            st.caption("Les articles retenus n’ont pas pu être enregistrés dans le projet pour le moment.")


def _compute_prioritized_results(
    entry: dict,
    result: dict,
    bramer: dict,
    focus_key: str,
    custom_goal: str,
    time_filter: dict,
) -> dict:
    query = bramer["strict"]["query"] if not bramer.get("is_identical") else bramer["large"]["query"]
    filtered_query = apply_pubmed_date_filter(
        query,
        start_year=time_filter.get("start_year", ""),
        end_year=time_filter.get("end_year", ""),
    )
    cache_key = _get_articles_cache_key(entry, filtered_query, scope="reranking")
    cached_payload = st.session_state.get(cache_key)

    if cached_payload is None:
        with st.spinner("Récupération et classement initial des articles..."):
            cached_payload = discover_articles(
                question=entry.get("user_question", ""),
                result=result,
                query=query,
                focus_key=focus_key,
                custom_goal=custom_goal,
                max_results=50,
                time_filter=time_filter,
            )
        st.session_state[cache_key] = cached_payload

    return cached_payload.get("prioritized", {})


def render_reading_focus(entry: dict, result: dict, bramer: dict) -> None:
    st.divider()
    st.subheader("Articles à regarder d’abord")

    goal_key = f"reading_focus_goal_{entry.get('id')}"
    suggestion_key = f"reading_focus_suggestion_{entry.get('id')}"
    selected_central_key = f"selected_central_article_{entry.get('id')}"
    article_feedback_key = f"article_feedback_{entry.get('id')}"

    suggestions = {
        "geography": "Je cherche surtout les études africaines",
        "factors": "Je veux d’abord les articles sur les facteurs associés",
        "validity": "Je veux d’abord les validations méthodologiques",
        "tool": "Je veux surtout les études qui comparent l’outil à une mesure de référence",
    }
    mode_key = f"time_filter_mode_{entry.get('id')}"
    start_key = f"time_filter_start_{entry.get('id')}"
    end_key = f"time_filter_end_{entry.get('id')}"
    time_filter = _get_time_filter_state(entry)
    focus_key = st.session_state.get(suggestion_key, "other")
    custom_goal = st.session_state.get(goal_key, "").strip()
    if not custom_goal:
        focus_key = "other"

    prioritized = st.session_state.get(f"prioritized_articles_{entry.get('id')}")
    current_time_filter = _get_time_filter_state(entry)
    if prioritized and prioritized.get("time_filter") != current_time_filter:
        prioritized = None
    if prioritized is None and time_filter.get("valid", True):
        prioritized = _compute_prioritized_results(entry, result, bramer, focus_key, custom_goal, time_filter)
        st.session_state[f"prioritized_articles_{entry.get('id')}"] = prioritized
    if not prioritized:
        st.caption("Cette étape n’affine pas la stratégie de recherche : elle aide seulement à savoir quels articles regarder d’abord.")
        return

    if not prioritized.get("articles"):
        fallback = prioritized.get("fallback") or {}
        if fallback.get("used"):
            st.caption(
                "Aucun article n’a été trouvé avec la version stricte. "
                f"Même après relâchement de {', '.join(fallback.get('relaxed_labels', []))}, aucun article plausible n’a pu être récupéré."
            )
        else:
            st.caption("Aucun article n’a pu être récupéré pour cette priorisation. La stratégie de recherche n’a pas été modifiée.")
        return

    active_time_filter = prioritized.get("time_filter") or _get_time_filter_state(entry)
    if active_time_filter.get("enabled") and active_time_filter.get("valid"):
        st.caption(f"Résultats actuellement limités à la période : {active_time_filter.get('label')}")

    current_query = prioritized.get("discovery_query")
    if not current_query:
        current_query = bramer["strict"]["query"] if not bramer.get("is_identical") else bramer["large"]["query"]
        current_query = apply_pubmed_date_filter(
            current_query,
            start_year=active_time_filter.get("start_year", ""),
            end_year=active_time_filter.get("end_year", ""),
        )

    fallback = prioritized.get("fallback") or {}
    if fallback.get("used"):
        st.caption(
            "Aucun article n’a été trouvé avec la version stricte. "
            f"Les articles ci-dessous proviennent d’une version relâchée en retirant : {', '.join(fallback.get('relaxed_labels', []))}."
        )

    st.link_button("Ouvrir ces résultats dans PubMed", f'https://pubmed.ncbi.nlm.nih.gov/?term={current_query}')

    with st.expander("Affiner cette priorisation", expanded=False):
        st.write("Qu’aimeriez-vous repérer en priorité dans ces résultats ?")
        st.caption("Suggestions rapides, si vous voulez partir d’un exemple :")
        suggestion_cols = st.columns(len(suggestions))
        for index, (suggested_focus_key, suggestion_text) in enumerate(suggestions.items()):
            if suggestion_cols[index].button(FOCUS_OPTIONS[suggested_focus_key], key=f"{suggestion_key}_{suggested_focus_key}"):
                st.session_state[goal_key] = suggestion_text
                st.session_state[suggestion_key] = suggested_focus_key

        custom_goal = st.text_area(
            "Votre objectif de lecture",
            placeholder=(
                "Ex: Je veux surtout les études qui comparent la montre à une mesure de référence ; "
                "Je cherche les études africaines ; Je veux d’abord les validations méthodologiques..."
            ),
            height=90,
            key=goal_key,
        ).strip()

        st.write("Période des résultats")
        st.caption("Ce filtre temporel agit sur les résultats affichés et leur priorisation, sans modifier la stratégie de recherche.")
        st.radio(
            "Limiter les résultats à une période",
            options=["Aucune limite", "Définir une période"],
            horizontal=True,
            key=mode_key,
        )

        if st.session_state.get(mode_key) == "Définir une période":
            year_cols = st.columns(2)
            year_cols[0].text_input(
                "Année de début",
                placeholder="Ex: 2018",
                key=start_key,
            )
            year_cols[1].text_input(
                "Année de fin",
                placeholder="Ex: 2024",
                key=end_key,
            )

        refreshed_time_filter = _get_time_filter_state(entry)
        if refreshed_time_filter.get("enabled") and refreshed_time_filter.get("valid"):
            st.caption(f"Filtre actif : {refreshed_time_filter.get('label')}")
        elif refreshed_time_filter.get("error"):
            st.caption(refreshed_time_filter["error"])

        refreshed_focus_key = st.session_state.get(suggestion_key, "other")
        if not custom_goal:
            refreshed_focus_key = "other"

        if st.button("Actualiser la priorisation", key=f"reading_focus_submit_{entry.get('id')}"):
            if not refreshed_time_filter.get("valid", True):
                st.caption(refreshed_time_filter.get("error") or "Le filtre temporel est invalide.")
                return
            prioritized = _compute_prioritized_results(
                entry,
                result,
                bramer,
                refreshed_focus_key,
                custom_goal,
                refreshed_time_filter,
            )
            st.session_state[f"prioritized_articles_{entry.get('id')}"] = prioritized
            st.rerun()

    st.caption(
        "Cette priorisation est une aide à la lecture. Elle repose d’abord sur le titre et l’abstract, et ne remplace pas une appréciation critique complète des articles."
    )
    reranking = prioritized.get("reranking") or {}
    if reranking.get("signals_used"):
        with st.expander("Détails méthodologiques", expanded=False):
            st.caption(
                "Les résultats ont d’abord été rerankés pour rapprocher les articles les plus centraux du sujet exact avant la priorisation finale : "
                + ", ".join(reranking.get("signals_used", []))
                + "."
            )

    focus_terms = prioritized.get("focus_terms", [])
    if focus_terms:
        with st.expander("Critères de priorisation", expanded=False):
            st.caption(f"Critères utilisés pour faire remonter un article : {', '.join(focus_terms[:5])}")

    shortlist = build_shortlist_for_agent(prioritized)
    if shortlist:
        st.caption(
            f"Vous pouvez aussi faire lire une shortlist de {len(shortlist)} articles à un agent pour affiner cette priorisation."
        )
        if st.button("Faire lire la shortlist par l’agent", key=f"reading_focus_agent_{entry.get('id')}"):
            try:
                with st.spinner("Lecture rapide des titres et abstracts de la shortlist..."):
                    assessment = assess_shortlist_with_agent(
                        shortlist,
                        prioritized.get("focus_label", ""),
                        custom_goal,
                    )
                prioritized = apply_agent_assessment(prioritized, shortlist, assessment)
                st.session_state[f"prioritized_articles_{entry.get('id')}"] = prioritized
            except Exception:
                st.caption("L’agent lecteur d’abstracts est indisponible pour le moment. La priorisation simple reste disponible.")

    if prioritized.get("agent_enabled"):
        st.caption("Classement affiné par un agent à partir du titre, de l’abstract et de quelques métadonnées.")

    article_feedback_store = st.session_state.setdefault(article_feedback_key, {})

    grouped = {
        "Très pertinent": [],
        "Pertinent": [],
        "À vérifier": [],
    }
    visible_articles = prioritized.get("display_articles") or prioritized.get("articles", [])
    for article in visible_articles:
        grouped.setdefault(article["priority"], []).append(article)

    for priority in ("Très pertinent", "Pertinent", "À vérifier"):
        articles = grouped.get(priority, [])
        if not articles:
            continue
        st.markdown(f"**{priority}**")
        for article in articles[:4]:
            title = article.get("title") or "Article sans titre"
            url = article.get("url")
            title_line = f"[{title}]({url})" if url else title
            st.markdown(f"- {title_line}")
            meta = " · ".join(part for part in [
                article.get("journal"),
                article.get("year"),
                ", ".join(article.get("authors", [])),
            ] if part)
            if meta:
                st.caption(meta)
            rank_caption = get_rank_caption(article)
            if rank_caption:
                st.caption(rank_caption)
            st.caption(get_article_badge(article))
            render_article_feedback_controls(entry.get("id"), article, article_feedback_store)
            with st.expander("Pourquoi cet article ?", expanded=False):
                render_article_reasons(article)
                render_article_details(article)

    central_candidates = [article for article in visible_articles if article.get("pmid")]
    central_article = None
    if central_candidates:
        option_map = {
            article.get("pmid"): (
                f"{article.get('title', 'Article sans titre')} "
                f"({article.get('year') or 'année non précisée'})"
            )
            for article in central_candidates
        }
        default_pmid = st.session_state.get(selected_central_key)
        if default_pmid not in option_map:
            default_pmid = central_candidates[0].get("pmid")
            st.session_state[selected_central_key] = default_pmid

        st.write("**Choisir un article central**")
        selected_pmid = st.radio(
            "Cet article me semble le plus parlant",
            options=list(option_map.keys()),
            format_func=lambda pmid: option_map[pmid],
            key=selected_central_key,
        )
        central_article = next(
            (article for article in central_candidates if article.get("pmid") == selected_pmid),
            None,
        )
    if central_article:
        st.divider()
        st.subheader("Articles connexes")
        related_query = build_related_articles_query(
            current_query,
            central_article,
            subject_text=entry.get("user_question", ""),
        )
        related_cache_key = f"related_articles_{entry.get('id')}_{central_article.get('pmid')}_{hash(related_query)}"
        related_articles = st.session_state.get(related_cache_key)
        if related_articles is None:
            with st.spinner("Recherche d’articles connexes..."):
                related_articles = fetch_articles(related_query, max_results=12) if related_query else []
            related_articles = [
                article for article in related_articles
                if article.get("pmid") != central_article.get("pmid")
            ]
            st.session_state[related_cache_key] = related_articles

        if related_articles:
            related_reranked = rerank_articles_hybrid(
                related_articles,
                entry.get("user_question", ""),
                custom_goal,
            )
            visible_related = [
                article for article in related_reranked.get("articles", [])
                if float(article.get("hybrid_score", 0.0) or 0.0) >= 0.18
            ][:5]
            if not visible_related:
                visible_related = related_reranked.get("articles", [])[:3]

            for article in visible_related:
                title = article.get("title") or "Article sans titre"
                url = article.get("url")
                title_line = f"[{title}]({url})" if url else title
                st.markdown(f"- {title_line}")
                meta = " · ".join(part for part in [
                    ", ".join(article.get("authors", [])),
                    article.get("year"),
                ] if part)
                if meta:
                    st.caption(meta)
        else:
            st.caption("Aucun article connexe suffisamment proche n’a pu être proposé à partir de cet article.")

        st.divider()
        st.subheader("Cet article cite aussi")
        st.caption(central_article.get("title", "Article central"))
        cited_cache_key = f"cited_refs_{entry.get('id')}_{central_article.get('pmid')}"
        cited_articles = st.session_state.get(cited_cache_key)
        if cited_articles is None:
            with st.spinner("Récupération des références citées..."):
                cited_articles = fetch_cited_articles(central_article.get("pmid"), max_results=15)
            st.session_state[cited_cache_key] = cited_articles

        if cited_articles:
            cited_reranked = rerank_articles_hybrid(
                cited_articles,
                entry.get("user_question", ""),
                custom_goal,
            )
            visible_refs = [
                article for article in cited_reranked.get("articles", [])
                if float(article.get("hybrid_score", 0.0) or 0.0) >= 0.18
            ][:5]
            if not visible_refs:
                visible_refs = cited_reranked.get("articles", [])[:3]

            for article in visible_refs:
                title = article.get("title") or "Référence sans titre"
                url = article.get("url")
                title_line = f"[{title}]({url})" if url else title
                st.markdown(f"- {title_line}")
                meta = " · ".join(part for part in [
                    ", ".join(article.get("authors", [])),
                    article.get("year"),
                ] if part)
                if meta:
                    st.caption(meta)
                identifier_parts = []
                if article.get("pmid"):
                    identifier_parts.append(f"PMID {article.get('pmid')}")
                if article.get("doi"):
                    identifier_parts.append(f"DOI {article.get('doi')}")
                if identifier_parts:
                    st.caption(" • ".join(identifier_parts))
                st.caption(get_reference_badge(article))
                with st.expander("Pourquoi cette référence ?", expanded=False):
                    st.caption(", ".join(article.get("hybrid_reasons", [])[:2]) or "Référence proche du sujet.")
        else:
            st.caption("Les références citées n’étaient pas accessibles pour cet article central dans les données récupérables ici.")
            st.caption("Pour continuer, vous pouvez utiliser les articles connexes ci-dessus ou relancer une recherche proche de cet article dans PubMed.")
            if related_query:
                st.link_button(
                    "Chercher des articles proches dans PubMed",
                    f'https://pubmed.ncbi.nlm.nih.gov/?term={related_query}',
                )

    render_zotero_ready_section(entry, prioritized, result=result)


def render_projects_overview(projects: list) -> None:
    st.subheader("Mes projets")

    if not projects:
        st.caption("Aucun projet pour le moment. Votre première recherche créera automatiquement un projet si besoin.")
        return

    active_project_id = st.session_state.get("active_project_id")
    project_options = {project["id"]: project for project in projects}
    project_ids = list(project_options.keys())
    default_index = project_ids.index(active_project_id) if active_project_id in project_options else 0

    selected_project_id = st.selectbox(
        "Projet actif",
        options=project_ids,
        index=default_index,
        format_func=lambda project_id: project_options[project_id]["title"],
        key="selected_project_id",
    )
    st.session_state["active_project_id"] = selected_project_id

    project = get_project_by_id(projects, selected_project_id)
    if not project:
        return

    st.caption(
        f"{len(project.get('entries', []))} recherche(s) liée(s) • Mise à jour : {project.get('updated_at', 'Date inconnue')}"
    )

    for entry in project.get("entries", [])[:4]:
        cols = st.columns([6, 2, 1])
        cols[0].write(get_entry_title(entry))
        cols[1].caption(entry.get("created_at", "Date inconnue"))
        if cols[2].button("Ouvrir", key=f"open_project_entry_{entry.get('id')}"):
            load_analysis_entry(st.session_state, entry)


def render_recent_entries(entries: list) -> None:
    if not entries:
        return

    with st.expander("Historique récent", expanded=False):
        st.caption("Vue transversale des dernières stratégies, tous projets confondus.")

        for entry in entries[:5]:
            cols = st.columns([5, 2, 1])
            cols[0].write(get_entry_title(entry))
            cols[1].caption(entry.get("project_title", "Sans projet"))
            cols[1].caption(entry.get("created_at", "Date inconnue"))
            if cols[2].button("Rouvrir", key=f"open_recent_{entry.get('id')}"):
                load_analysis_entry(st.session_state, entry)


def render_fake_paywall(entry: dict) -> None:
    entry_id = entry.get("id")
    price_key = f"paywall_price_{entry_id}"
    refusal_open_key = f"paywall_refusal_open_{entry_id}"
    last_tracked_price_key = f"paywall_last_price_{entry_id}"

    st.warning("Le pack complet est actuellement proposé comme fonctionnalité premium en test.")
    st.write(
        "Le pack complet fournit une version claire, structurée et réutilisable de votre stratégie de recherche, "
        "pour retrouver votre travail plus tard, l’affiner plus facilement et éviter de repartir de zéro."
    )

    if st.button("Je veux débloquer cette fonctionnalité", key=f"paywall_unlock_{entry_id}"):
        send_paywall_event(build_paywall_payload(entry, "paywall_click_unlock"))
        st.caption("Le paiement n’est pas encore ouvert. Vous pouvez tout de même nous indiquer votre intérêt.")

    if st.button("Je suis intéressé", key=f"paywall_interest_{entry_id}"):
        send_paywall_event(build_paywall_payload(entry, "paywall_click_interest"))
        st.success("Merci, votre intérêt a été enregistré.")

    selected_price = st.selectbox(
        "Si cette fonctionnalité existait, quel prix vous semblerait acceptable ?",
        options=[""] + DEFAULT_PRICES,
        format_func=lambda value: "Choisir un prix" if value == "" else value,
        key=price_key,
    )

    if selected_price and st.session_state.get(last_tracked_price_key) != selected_price:
        send_paywall_event(
            build_paywall_payload(
                entry,
                "paywall_price_selected",
                price_selected=selected_price,
            )
        )
        st.session_state[last_tracked_price_key] = selected_price
        if selected_price == "Je ne paierais pas":
            st.session_state[refusal_open_key] = True

    email = st.text_input(
        "Email (facultatif) pour être recontacté quand la fonctionnalité sera disponible",
        key=f"paywall_email_{entry_id}",
    )
    if st.button("Être recontacté", key=f"paywall_email_submit_{entry_id}"):
        if email.strip():
            send_paywall_event(
                build_paywall_payload(
                    entry,
                    "paywall_email_submitted",
                    price_selected=selected_price,
                    email=email.strip(),
                )
            )
            st.success("Merci. Votre email a été enregistré.")
        else:
            st.caption("Vous pouvez laisser ce champ vide si vous ne souhaitez pas être recontacté.")

    if st.button("Pas maintenant", key=f"paywall_dismiss_{entry_id}"):
        send_paywall_event(
            build_paywall_payload(
                entry,
                "paywall_dismissed",
                price_selected=selected_price,
            )
        )
        st.session_state[refusal_open_key] = True

    if st.session_state.get(refusal_open_key):
        refusal_reason = st.selectbox(
            "Qu’est-ce qui vous freine le plus ?",
            options=[
                "",
                "Je veux d’abord tester davantage",
                "Ce n’est pas encore assez clair pour moi",
                "Le prix me semble trop élevé",
                "Je n’en ai pas besoin pour l’instant",
            ],
            format_func=lambda value: "Choisir une réponse (facultatif)" if value == "" else value,
            key=f"paywall_refusal_reason_{entry_id}",
        )
        if st.button("Envoyer cette réponse", key=f"paywall_refusal_submit_{entry_id}"):
            if refusal_reason:
                send_paywall_event(
                    build_paywall_payload(
                        entry,
                        "paywall_refusal_reason_submitted",
                        price_selected=selected_price,
                        refusal_reason=refusal_reason,
                    )
                )
                st.success("Merci, votre réponse a été enregistrée.")
            else:
                st.caption("Cette question reste facultative.")


def render_analysis(entry: dict) -> None:
    result, strategy, bramer = _build_effective_analysis(entry)
    question = entry["user_question"]
    time_filter = _get_time_filter_state(entry)
    pack = build_search_strategy_pack(
        user_question=question,
        result=result,
        strategy=strategy,
        platform_outputs={"PubMed": bramer},
        result_filters={"time": time_filter} if time_filter.get("enabled") and time_filter.get("valid") else None,
    )

    detected_intent = result.get("intent") or "structure"
    framework = result.get("framework")
    components = result.get("components") or {}
    presentation = get_question_presentation(result, question)
    reformulated_question = get_reformulated_question(question, result, presentation)
    visible_explanation = get_visible_explanation(result, presentation)

    render_what_i_understood(
        question=question,
        components=components,
        presentation=presentation,
        reformulated_question=reformulated_question if detected_intent == "structure" else "",
        visible_explanation=visible_explanation,
        project_title=entry.get("project_title") or "",
    )

    render_reading_focus(entry, result, bramer)

    large = bramer["large"]
    strict = bramer["strict"]
    excluded = bramer["excluded"]
    is_identical = bramer.get("is_identical", False)

    st.divider()
    render_suggested_query(bramer)

    large_count_label = format_results_count(large.get("count"))
    strict_count_label = format_results_count(strict.get("count"))

    with st.expander("Comprendre et ajuster la stratégie", expanded=False):
        if presentation.get("show_framework") and framework:
            st.caption(f"Framework méthodologique identifié : {framework}")

        st.subheader("Composantes de la recherche")
        if components:
            for key, value in components.items():
                if value:
                    label = get_component_label(key, presentation)
                    st.write(f"**{label}** : {value}")
        else:
            st.caption("Aucune composante structurée retournée.")

        classified_concepts = result.get("classified_concepts") or []
        if classified_concepts:
            st.write("**Concepts détectés**")
            for concept in classified_concepts:
                role = concept.get("role", "core")
                st.caption(f"{concept.get('label', 'Concept')} · rôle : {role}")

        st.divider()
        render_concept_editor(entry)
        st.divider()

        st.subheader(f"Recherche large — {large_count_label}")
        st.code(large["query"], language="text")
        if large["elements_used"]:
            st.caption(f"Concepts retenus : {', '.join(large['elements_used'])}")
        else:
            st.caption("Aucun concept de recherche actif retourné.")

        if is_identical:
            st.caption(
                "Aucun filtre supplémentaire pertinent n’a été identifié. "
                "Vous pouvez affiner en précisant un pays, un contexte, "
                "une population ou un cadre d’étude."
            )
        else:
            st.markdown("---")

            added = [
                e for e in strict["elements_used"]
                if e not in large["elements_used"]
            ]
            added_text = (
                f"L’élément{'s suivants ont été ajoutés' if len(added) > 1 else ' suivant a été ajouté'} "
                f"pour restreindre les résultats : {', '.join(added)}."
            )

            st.subheader(f"Recherche restreinte — {strict_count_label}")
            st.code(strict["query"], language="text")
            st.caption(added_text)

        if excluded:
            with st.expander("Pourquoi certains concepts ne sont pas utilisés comme filtres ?", expanded=False):
                for ex in excluded:
                    st.caption(
                        f'Le concept "{ex["label"]}" n’est pas utilisé comme filtre : {ex["reason"]}'
                    )

        render_query_expansion(entry, result, strategy, bramer, time_filter)

        with st.expander("Détails méthodologiques", expanded=False):
            if visible_explanation:
                st.caption(visible_explanation)
            st.caption(
                "La stratégie commence large, puis ajoute seulement les filtres jugés réellement utiles pour éviter d’exclure trop tôt des articles pertinents."
            )

    geography = result.get("geography") or {}
    if geography and any(v for v in geography.values() if v):
        with st.expander("Voir les résultats par périmètre géographique", expanded=False):
            try:
                with st.spinner("Comptage des résultats par périmètre géographique..."):
                    scopes = count_geographic_scopes(
                        large["query"],
                        geography,
                        geography_tiab=result.get("geography_tiab"),
                    )
            except Exception:
                scopes = {}

            if scopes:
                scope_order = ["geo_filter", "country", "region", "continent", "global"]
                visible = [s for s in scope_order if s in scopes]
                cols = st.columns(len(visible))
                for i, scope in enumerate(visible):
                    s = scopes[scope]
                    cols[i].metric(
                        label=s["label"],
                        value=format_results_count(s.get("count")),
                    )
                    cols[i].link_button(
                        "Ouvrir dans PubMed",
                        f'https://pubmed.ncbi.nlm.nih.gov/?term={s["query"]}',
                    )
            else:
                st.caption("Aucun résultat géographique détaillé disponible.")

    st.divider()
    st.subheader("Retour rapide")
    st.write("Avant de poursuivre, 30 secondes pour nous aider à améliorer l’outil.")

    rating = st.slider(
        "Cet outil vous a-t-il été utile ?",
        min_value=1,
        max_value=5,
        value=3,
        key=f"feedback_rating_{entry.get('id')}",
    )

    feedback_comment = st.text_area(
        "Qu’est-ce qui a manqué ou prêté à confusion ?",
        placeholder="Ex: Je n’ai pas compris comment l’analyse fonctionnait...",
        height=100,
        key=f"feedback_comment_{entry.get('id')}",
    )

    if st.button("Envoyer le retour", key=f"send_feedback_{entry.get('id')}"):
        try:
            save_feedback(
                level="auto",
                population="",
                intervention="",
                outcome="",
                comparaison="",
                rating=rating,
                comment=feedback_comment,
            )
            st.success("Merci. Votre retour nous aide à améliorer l’outil.")
        except Exception:
            st.caption("Le feedback est indisponible pour le moment. L’application reste utilisable.")

    st.divider()
    st.subheader("Actions finales")
    st.link_button(
        "Rechercher dans PubMed (large)",
        f'https://pubmed.ncbi.nlm.nih.gov/?term={large["query"]}',
    )
    if not is_identical:
        st.link_button(
            "Rechercher dans PubMed (restreinte)",
            f'https://pubmed.ncbi.nlm.nih.gov/?term={strict["query"]}',
        )

    st.divider()
    st.subheader("Pack de stratégie de recherche")
    st.caption("Aperçu gratuit du pack. La version complète vise surtout à vous aider à conserver, reprendre et réutiliser votre stratégie plus facilement.")
    if time_filter.get("enabled") and time_filter.get("valid"):
        st.caption(f"Filtre temporel actuellement reflété dans le pack : {time_filter.get('label')}.")
    preview = get_pack_preview(pack)
    with st.expander("Voir l’aperçu du pack", expanded=False):
        st.text_area(
            "Aperçu du pack",
            value=preview,
            height=260,
            key=f"pack_preview_{entry.get('id')}",
        )
        st.download_button(
            "Télécharger l’aperçu du pack",
            data=preview,
            file_name="search_strategy_pack_preview.md",
            mime="text/markdown",
            key=f"download_pack_preview_{entry.get('id')}",
        )
    if st.button("Copier le pack complet", key=f"open_paywall_{entry.get('id')}"):
        st.session_state[f"show_paywall_{entry.get('id')}"] = True
        send_paywall_event(build_paywall_payload(entry, "paywall_view"))

    if st.session_state.get(f"show_paywall_{entry.get('id')}"):
        st.markdown("---")
        st.subheader("Accéder au pack complet")
        render_fake_paywall(entry)


st.title("Research Companion")
st.caption("Trouvez les articles scientifiques sur votre sujet.")

get_session_id()

with st.sidebar:
    projects = load_projects()
    with st.expander("Projets", expanded=False):
        render_projects_overview(projects)
        render_recent_entries(get_recent_entries(projects))

    with st.expander("Organisation", expanded=False):
        new_project_title = st.text_input(
            "Nouveau projet (facultatif)",
            placeholder="Ex: Prévalence du diabète au Mali",
            key="new_project_title",
        )
        if st.button("Créer ce projet", key="create_project_button"):
            if new_project_title.strip():
                try:
                    project = create_project(new_project_title.strip())
                    st.session_state["active_project_id"] = project.get("id")
                    st.success("Projet créé.")
                except Exception:
                    st.caption("Le projet n’a pas pu être créé pour le moment.")
            else:
                st.caption("Saisissez d’abord un titre de projet.")

    active_project = get_project_by_id(load_projects(), st.session_state.get("active_project_id", ""))
    with st.expander("Zotero", expanded=False):
        render_zotero_connection(active_project)

if st.session_state.pop("reset_question_input_pending", False):
    st.session_state.pop("question_input", None)

question = st.text_area(
    "Quel est votre sujet de recherche ?",
    placeholder="Ex: prévalence du diabète chez les enfants au Mali...",
    height=100,
    key="question_input",
)

input_actions = st.columns([1, 1, 5])
run_analysis = input_actions[0].button("Analyser ma question")
new_search = input_actions[1].button("Nouvelle recherche")

if new_search:
    st.session_state["reset_question_input_pending"] = True
    reset_search_state(st.session_state, clear_question=True, update_question=False)
    st.rerun()

if run_analysis:
    if question:
        try:
            search_session_id = reset_search_state(
                st.session_state,
                question.strip(),
                update_question=False,
            )
            with st.spinner("Analyse du sujet et découverte initiale..."):
                discovery_payload = run_topic_discovery(question)

            result = discovery_payload.get("result", {})
            query_package = discovery_payload.get("query_package", {})
            strategy = query_package.get("strategy", {})
            bramer = (query_package.get("platform_outputs") or {}).get("PubMed", {})
            initial_discovery = discovery_payload.get("discovery", {})

            entry = build_history_entry(
                user_question=question,
                result=result,
                strategy=strategy,
                platform_outputs={"PubMed": bramer},
                pack=build_search_strategy_pack(
                    user_question=question,
                    result=result,
                    strategy=strategy,
                    platform_outputs={"PubMed": bramer},
                ),
                search_session_id=search_session_id,
            )
            project_title = new_project_title.strip() or (active_project.get("title") if active_project else "")
            project_id = active_project.get("id") if active_project and not new_project_title.strip() else None

            try:
                if new_project_title.strip():
                    project = create_project(new_project_title.strip())
                    st.session_state["active_project_id"] = project.get("id")
                    project_id = project.get("id")
                    project_title = project.get("title")

                entry = save_entry_to_project(
                    entry,
                    project_id=project_id,
                    project_title=project_title or question,
                )
                st.session_state["current_analysis"] = entry
                if initial_discovery.get("prioritized"):
                    st.session_state[f"prioritized_articles_{entry.get('id')}"] = initial_discovery["prioritized"]
            except Exception:
                st.session_state["current_analysis"] = entry
                if initial_discovery.get("prioritized"):
                    st.session_state[f"prioritized_articles_{entry.get('id')}"] = initial_discovery["prioritized"]
                st.caption("Le projet n’a pas pu être mis à jour, mais l’analyse reste disponible.")

        except Exception:
            st.error("L’analyse est temporairement indisponible. Veuillez réessayer plus tard.")
    else:
        st.warning("Veuillez décrire votre sujet de recherche.")

current_analysis = st.session_state.get("current_analysis")
if current_analysis:
    st.divider()
    render_analysis(current_analysis)
