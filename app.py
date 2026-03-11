import streamlit as st

from claude_helper import analyze_research_question
from feedback import save_feedback
from platform_backends.pubmed_backend import build_pubmed_queries
from platform_backends.pubmed_backend import count_geographic_scopes
from search_strategy import build_search_strategy
from strategy_pack import build_search_strategy_pack


def format_results_count(count) -> str:
    return str(count) if isinstance(count, int) and count >= 0 else "Résultats indisponibles"


st.title("Research Companion")
st.subheader("De la question de recherche à la requête PubMed")
st.divider()

level = "auto"
population = ""
intervention = ""
outcome = ""
comparaison = ""

question = st.text_area(
    "Quel est votre sujet de recherche ?",
    placeholder="Ex: prévalence du diabète chez les enfants au Mali...",
    height=100,
)

if st.button("Analyser ma question"):
    if question:
        try:
            with st.spinner("Analyse de votre question..."):
                result = analyze_research_question(question)

            with st.expander("JSON de debug"):
                st.json(result)

            detected_intent = result.get("intent") or "structure"
            framework = result.get("framework")
            explanation = result.get("explanation")
            comment = result.get("research_question_comment")
            question_fr = result.get("research_question_fr")
            components = result.get("components") or {}

            if detected_intent == "structure":
                if framework:
                    st.write(f"Framework détecté : **{framework}**")
                if explanation:
                    st.caption(explanation)
            else:
                st.caption("Concepts clés identifiés dans votre question.")

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
                        st.write(f"**{key.capitalize()}** : {value}")
            else:
                st.caption("Aucune composante structurée retournée.")

            st.divider()

            with st.spinner("Construction de la stratégie de recherche..."):
                strategy = build_search_strategy(result)

            with st.spinner("Construction des requêtes PubMed..."):
                bramer = build_pubmed_queries(strategy)

            large = bramer["large"]
            strict = bramer["strict"]
            excluded = bramer["excluded"]
            is_identical = bramer.get("is_identical")
            if is_identical is None:
                is_identical = (
                    large["query"] == strict["query"]
                    and large["elements_used"] == strict["elements_used"]
                )

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
                key="feedback_rating",
            )

            comment = st.text_area(
                "Qu’est-ce qui a manqué ou prêté à confusion ?",
                placeholder="Ex: Je n’ai pas compris comment l’analyse fonctionnait...",
                height=100,
                key="feedback_comment",
            )

            if st.button("Envoyer le retour", key="send_feedback_inline"):
                try:
                    save_feedback(
                        level=level,
                        population=population,
                        intervention=intervention or "",
                        outcome=outcome or "",
                        comparaison=comparaison or "",
                        rating=rating,
                        comment=comment
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

            strategy_pack = build_search_strategy_pack(
                user_question=question,
                result=result,
                strategy=strategy,
                platform_outputs={"PubMed": bramer},
            )

            st.divider()
            st.subheader("Pack de stratégie de recherche")
            st.caption("Copiable tel quel ou exportable en markdown.")
            st.text_area(
                "Copier le pack de stratégie",
                value=strategy_pack,
                height=360,
            )
            st.download_button(
                "Télécharger le pack de stratégie",
                data=strategy_pack,
                file_name="search_strategy_pack.md",
                mime="text/markdown",
            )

        except Exception:
            st.error("L’analyse est temporairement indisponible. Veuillez réessayer plus tard.")
    else:
        st.warning("Veuillez décrire votre sujet de recherche.")
