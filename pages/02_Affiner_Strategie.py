import streamlit as st

from services.query_builder import build_query_variants
from services.query_builder import get_strategy_builder_state
from services.query_builder import group_concepts_by_role
from services.query_builder import ROLE_DESCRIPTIONS
from services.query_builder import ROLE_LABELS
from services.query_builder import STATUS_DESCRIPTIONS
from services.query_builder import STATUS_OPTIONS
from services.query_builder import update_workspace_statuses
from ui.query_panels import render_query_variant_panel


st.set_page_config(page_title="Affiner / Strategie", page_icon=None, layout="wide")

st.title("Affiner / Strategie")
st.caption("Ajustez les concepts detectes et comparez plusieurs variantes de requete sans revenir au premier ecran.")

current_analysis = st.session_state.get("current_analysis")

if not current_analysis:
    st.info("Aucune recherche n'a encore ete lancee. Commencez par la page Trouver pour obtenir des concepts et une premiere strategie.")
    st.stop()

search_session_id, workspace_concepts = get_strategy_builder_state(current_analysis, st.session_state)

if not workspace_concepts:
    st.info("Aucun concept exploitable n'est disponible pour cette recherche.")
    st.stop()

st.write(f"**Sujet courant** : {current_analysis.get('user_question', '')}")
if current_analysis.get("reformulated_question"):
    st.caption(f"Reformulation : {current_analysis.get('reformulated_question')}")

st.subheader("Concepts et statuts")
st.caption("Chaque concept peut etre rendu obligatoire, optionnel, utile seulement pour prioriser la lecture, ou ignore.")

grouped_concepts = group_concepts_by_role(workspace_concepts)

for role_key in ("core", "refinement", "ranking", "context"):
    concepts = grouped_concepts.get(role_key) or []
    if not concepts:
        continue

    st.markdown(f"### {ROLE_LABELS[role_key]}")
    st.caption(ROLE_DESCRIPTIONS[role_key])

    for concept in concepts:
        cols = st.columns([2, 2, 2])
        cols[0].markdown(f"**{concept['label']}**")
        cols[0].caption(concept.get("tiab") or "Aucun terme texte")
        if concept.get("mesh"):
            cols[0].caption(f"MeSH : {concept['mesh']}")
        if concept.get("reason"):
            cols[1].caption(f"Contexte : {concept['reason']}")
        cols[2].selectbox(
            "Statut",
            options=list(STATUS_OPTIONS.keys()),
            format_func=lambda value: STATUS_OPTIONS[value],
            index=list(STATUS_OPTIONS.keys()).index(concept["status"]),
            key=f"strategy_builder_status_{search_session_id}_{concept['id']}",
        )
        st.caption(STATUS_DESCRIPTIONS[st.session_state.get(f"strategy_builder_status_{search_session_id}_{concept['id']}", concept['status'])])
        st.divider()

updated_concepts = update_workspace_statuses(workspace_concepts, st.session_state, search_session_id)
st.session_state[f"strategy_builder_workspace_{search_session_id}"] = updated_concepts

variants = build_query_variants(updated_concepts)

st.subheader("Variantes de requete")
variant_cols = st.columns(3)
for col, variant_key in zip(variant_cols, ("large", "focused", "strict")):
    with col:
        render_query_variant_panel(variant_key, variants[variant_key], search_session_id)
