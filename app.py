import streamlit as st

from abstract_reader_agent import assess_shortlist_with_agent
from abstract_reader_agent import build_shortlist_for_agent
from claude_helper import analyze_research_question
from concept_editor import apply_editor_changes
from concept_editor import clone_search_elements
from concept_editor import EDITOR_STATE_OPTIONS
from concept_editor import get_editor_state
from concept_editor import serialize_terms
from feedback import save_feedback
from paywall_tracking import build_paywall_payload
from paywall_tracking import DEFAULT_PRICES
from paywall_tracking import get_session_id
from paywall_tracking import send_paywall_event
from platform_backends.pubmed_backend import build_pubmed_queries
from platform_backends.pubmed_backend import count_geographic_scopes
from platform_backends.pubmed_backend import fetch_articles
from platform_backends.pubmed_backend import apply_pubmed_date_filter
from question_display import get_component_label
from question_display import get_question_presentation
from question_display import get_reformulated_question
from question_display import get_visible_explanation
from research_projects import create_project
from research_projects import get_project_by_id
from research_projects import get_recent_entries
from research_projects import load_projects
from research_projects import save_project_articles
from research_projects import save_project_zotero_target
from research_projects import save_entry_to_project
from reading_prioritization import FOCUS_OPTIONS
from reading_prioritization import apply_agent_assessment
from reading_prioritization import prioritize_articles
from search_strategy import build_search_strategy
from strategy_pack import build_search_strategy_pack
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


def format_results_count(count) -> str:
    return str(count) if isinstance(count, int) and count >= 0 else "Résultats indisponibles"


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
        "result": result,
        "strategy": strategy,
        "platform_outputs": platform_outputs,
        "pack": pack,
    }


def _get_articles_cache_key(entry: dict, query: str) -> str:
    return f"article_cache_{entry.get('id')}_{hash(query)}"


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
    effective_result = dict(entry.get("result") or {})
    effective_result["search_elements"] = clone_search_elements(edited_elements)
    effective_strategy = build_search_strategy(effective_result)
    effective_bramer = build_pubmed_queries(effective_strategy)
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
            st.caption(f"Justification : {article.get('justification', 'Non précisée')}")
            st.caption(f"Tags suggérés : {', '.join(article.get('tags', [])) or 'Aucun tag'}")
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


def render_reading_focus(entry: dict, result: dict, bramer: dict) -> None:
    st.divider()
    st.subheader("Focalisation de lecture")
    st.write("Qu’aimeriez-vous repérer en priorité dans ces résultats ?")

    goal_key = f"reading_focus_goal_{entry.get('id')}"
    suggestion_key = f"reading_focus_suggestion_{entry.get('id')}"

    suggestions = {
        "geography": "Je cherche surtout les études africaines",
        "factors": "Je veux d’abord les articles sur les facteurs associés",
        "validity": "Je veux d’abord les validations méthodologiques",
        "tool": "Je veux surtout les études qui comparent l’outil à une mesure de référence",
    }

    st.caption("Suggestions rapides, si vous voulez partir d’un exemple :")
    suggestion_cols = st.columns(len(suggestions))
    for index, (focus_key, suggestion_text) in enumerate(suggestions.items()):
        if suggestion_cols[index].button(FOCUS_OPTIONS[focus_key], key=f"{suggestion_key}_{focus_key}"):
            st.session_state[goal_key] = suggestion_text
            st.session_state[suggestion_key] = focus_key

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
    mode_key = f"time_filter_mode_{entry.get('id')}"
    start_key = f"time_filter_start_{entry.get('id')}"
    end_key = f"time_filter_end_{entry.get('id')}"

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

    time_filter = _get_time_filter_state(entry)
    if time_filter.get("enabled") and time_filter.get("valid"):
        st.caption(f"Filtre actif : {time_filter.get('label')}")
    elif time_filter.get("error"):
        st.caption(time_filter["error"])

    focus_key = st.session_state.get(suggestion_key, "other")
    if not custom_goal:
        focus_key = "other"

    if st.button("Prioriser la lecture", key=f"reading_focus_submit_{entry.get('id')}"):
        if not time_filter.get("valid", True):
            st.caption(time_filter.get("error") or "Le filtre temporel est invalide.")
            return
        query = bramer["strict"]["query"] if not bramer.get("is_identical") else bramer["large"]["query"]
        query = apply_pubmed_date_filter(
            query,
            start_year=time_filter.get("start_year", ""),
            end_year=time_filter.get("end_year", ""),
        )
        cache_key = _get_articles_cache_key(entry, query)
        articles = st.session_state.get(cache_key)

        if articles is None:
            with st.spinner("Récupération d’un premier lot d’articles PubMed..."):
                articles = fetch_articles(query, max_results=15)
            st.session_state[cache_key] = articles

        prioritized = prioritize_articles(articles or [], result, focus_key, custom_goal)
        prioritized["time_filter"] = time_filter
        st.session_state[f"prioritized_articles_{entry.get('id')}"] = prioritized

    prioritized = st.session_state.get(f"prioritized_articles_{entry.get('id')}")
    current_time_filter = _get_time_filter_state(entry)
    if prioritized and prioritized.get("time_filter") != current_time_filter:
        prioritized = None
    if not prioritized:
        st.caption("Cette étape n’affine pas la stratégie de recherche : elle aide seulement à savoir quels articles regarder d’abord.")
        return

    if not prioritized.get("articles"):
        st.caption("Aucun article n’a pu être récupéré pour cette priorisation. La stratégie de recherche n’a pas été modifiée.")
        return

    active_time_filter = prioritized.get("time_filter") or _get_time_filter_state(entry)
    if active_time_filter.get("enabled") and active_time_filter.get("valid"):
        st.caption(f"Résultats actuellement limités à la période : {active_time_filter.get('label')}")

    st.caption(
        "Cette priorisation est une aide à la lecture. Elle repose d’abord sur le titre et l’abstract, et ne remplace pas une appréciation critique complète des articles."
    )

    focus_terms = prioritized.get("focus_terms", [])
    if focus_terms:
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

    grouped = {
        "Très pertinent": [],
        "Pertinent": [],
        "À vérifier": [],
    }
    for article in prioritized.get("articles", []):
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
            st.caption(f"Pourquoi il remonte : {', '.join(article.get('reasons', [])[:2])}")

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
            st.session_state["question_input"] = entry.get("user_question", "")
            st.session_state["current_analysis"] = entry


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
                st.session_state["question_input"] = entry.get("user_question", "")
                st.session_state["current_analysis"] = entry


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

    st.subheader("Question analysée")
    if entry.get("project_title"):
        st.caption(f"Projet : {entry.get('project_title')}")
    st.write(question)
    st.write(f"Type de sujet : **{presentation.get('question_type', 'question descriptive')}**")
    if presentation.get("show_framework") and framework:
        st.caption(f"Framework méthodologique : {framework}")

    if detected_intent == "structure" and reformulated_question:
        st.write("**Reformulation proposée**")
        st.write(f"*{reformulated_question}*")

    st.subheader("Composantes de la recherche")
    if components:
        for key, value in components.items():
            if value:
                label = get_component_label(key, presentation)
                st.write(f"**{label}** : {value}")
    else:
        st.caption("Aucune composante structurée retournée.")

    st.divider()
    render_concept_editor(entry)
    st.divider()

    large = bramer["large"]
    strict = bramer["strict"]
    excluded = bramer["excluded"]
    is_identical = bramer.get("is_identical", False)

    large_count_label = format_results_count(large.get("count"))
    strict_count_label = format_results_count(strict.get("count"))

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
        st.subheader("Concepts non utilisés comme filtres")
        for ex in excluded:
            st.caption(
                f'Le concept "{ex["label"]}" n’est pas utilisé comme filtre : {ex["reason"]}'
            )

    if visible_explanation:
        st.subheader("Repère méthodologique")
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

    render_reading_focus(entry, result, bramer)

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
    render_projects_overview(projects)
    render_recent_entries(get_recent_entries(projects))

    st.divider()

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
    render_zotero_connection(active_project)

question = st.text_area(
    "Quel est votre sujet de recherche ?",
    placeholder="Ex: prévalence du diabète chez les enfants au Mali...",
    height=100,
    key="question_input",
)

if st.button("Analyser ma question"):
    if question:
        try:
            with st.spinner("Analyse de votre question..."):
                result = analyze_research_question(question)

            with st.spinner("Construction de la stratégie de recherche..."):
                strategy = build_search_strategy(result)

            with st.spinner("Construction des requêtes PubMed..."):
                bramer = build_pubmed_queries(strategy)

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
            except Exception:
                st.session_state["current_analysis"] = entry
                st.caption("Le projet n’a pas pu être mis à jour, mais l’analyse reste disponible.")

        except Exception:
            st.error("L’analyse est temporairement indisponible. Veuillez réessayer plus tard.")
    else:
        st.warning("Veuillez décrire votre sujet de recherche.")

current_analysis = st.session_state.get("current_analysis")
if current_analysis:
    st.divider()
    render_analysis(current_analysis)
