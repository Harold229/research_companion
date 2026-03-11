import streamlit as st

from claude_helper import analyze_research_question
from feedback import save_feedback
from paywall_tracking import build_paywall_payload
from paywall_tracking import DEFAULT_PRICES
from paywall_tracking import get_session_id
from paywall_tracking import send_paywall_event
from platform_backends.pubmed_backend import build_pubmed_queries
from platform_backends.pubmed_backend import count_geographic_scopes
from question_display import get_component_label
from question_display import get_question_presentation
from question_display import get_visible_explanation
from search_history import build_history_entry
from search_history import load_recent_searches
from search_history import save_recent_search
from search_strategy import build_search_strategy
from strategy_pack import build_search_strategy_pack


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


def render_recent_searches(history_entries: list) -> None:
    st.subheader("Mes dernières stratégies")
    st.caption("Rouvrez une recherche récente pour relire le pack sans tout recalculer.")

    if not history_entries:
        st.caption("Aucune recherche récente enregistrée.")
        return

    for entry in history_entries[:5]:
        cols = st.columns([5, 1])
        cols[0].write(f"**{get_entry_title(entry)}**")
        presentation = get_question_presentation(entry.get("result") or {})
        question_type = presentation.get("question_type", "question descriptive")
        cols[0].caption(f"{entry.get('created_at', 'Date inconnue')} • {question_type} • Pack disponible")
        if cols[1].button("Rouvrir", key=f"open_history_{entry.get('id')}"):
            st.session_state["question_input"] = entry.get("user_question", "")
            st.session_state["current_analysis"] = entry


def render_fake_paywall(entry: dict) -> None:
    entry_id = entry.get("id")
    price_key = f"paywall_price_{entry_id}"
    refusal_open_key = f"paywall_refusal_open_{entry_id}"
    last_tracked_price_key = f"paywall_last_price_{entry_id}"

    st.warning("Le pack complet prêt à partager est actuellement proposé comme fonctionnalité premium en test.")
    st.write(
        "Ce pack complet inclut une version propre, directement copiable et montrable à un directeur de mémoire, "
        "un encadrant ou un collègue, sans retravailler la mise en forme."
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
    result = entry["result"]
    strategy = entry["strategy"]
    bramer = entry["platform_outputs"]["PubMed"]
    question = entry["user_question"]
    pack = entry["pack"]

    detected_intent = result.get("intent") or "structure"
    framework = result.get("framework")
    explanation = result.get("explanation")
    comment = result.get("research_question_comment")
    question_fr = result.get("research_question_fr")
    components = result.get("components") or {}
    presentation = get_question_presentation(result)
    visible_explanation = get_visible_explanation(result, presentation)

    st.write(f"Type de question : **{presentation.get('question_type', 'question descriptive')}**")
    if presentation.get("show_framework") and framework:
        st.caption(f"Framework méthodologique : {framework}")
    if visible_explanation:
        st.caption(visible_explanation)

    if detected_intent == "structure":
        if question_fr:
            if comment:
                st.write(f"**{comment}**")
            st.write(f"*{question_fr}*")
        elif comment:
            st.write(comment)

    st.subheader("Composantes de la recherche")
    if components:
        for key, value in components.items():
            if value:
                label = get_component_label(key, presentation)
                st.write(f"**{label}** : {value}")
    else:
        st.caption("Aucune composante structurée retournée.")

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

    if excluded:
        for ex in excluded:
            st.caption(
                f'Le concept "{ex["label"]}" n’est pas utilisé comme filtre : {ex["reason"]}'
            )

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

    st.markdown("---")
    st.caption(
        "Pourquoi deux versions ? En recherche systématique, chaque filtre "
        "supplémentaire risque d’exclure des articles pertinents. "
        "Il faut commencer large, puis restreindre si le volume est trop important.  \n"
        "*Bramer et al., 2018 — DOI: 10.5195/jmla.2018.283*"
    )

    geography = result.get("geography") or {}
    if geography and any(v for v in geography.values() if v):
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
            st.subheader("Résultats par périmètre géographique")
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
    st.caption("Aperçu gratuit du pack. La copie complète est testée via un faux paywall.")
    preview = get_pack_preview(pack)
    st.text_area(
        "Aperçu du pack",
        value=preview,
        height=300,
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
st.subheader("De la question de recherche à la requête PubMed")
st.divider()

get_session_id()

history_entries = load_recent_searches()
render_recent_searches(history_entries)

st.divider()

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
            st.session_state["current_analysis"] = entry

            try:
                save_recent_search(entry)
            except Exception:
                st.caption("L’historique récent n’a pas pu être mis à jour.")

        except Exception:
            st.error("L’analyse est temporairement indisponible. Veuillez réessayer plus tard.")
    else:
        st.warning("Veuillez décrire votre sujet de recherche.")

current_analysis = st.session_state.get("current_analysis")
if current_analysis:
    st.divider()
    render_analysis(current_analysis)
