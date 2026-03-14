import json

import streamlit as st
import streamlit.components.v1 as components


def render_copy_button(text: str, key: str) -> None:
    payload = json.dumps(str(text or ""))
    element_id = f"copy-{key}".replace(" ", "-").replace("/", "-")
    components.html(
        f"""
        <button id="{element_id}" style="
            width: 100%;
            padding: 0.45rem 0.75rem;
            border: 1px solid #d0d7de;
            border-radius: 0.5rem;
            background: #f6f8fa;
            cursor: pointer;
            font-size: 0.9rem;
        ">Copier la requête</button>
        <script>
        const button = document.getElementById("{element_id}");
        button.addEventListener("click", async () => {{
            try {{
                await navigator.clipboard.writeText({payload});
                button.innerText = "Requête copiée";
            }} catch (error) {{
                button.innerText = "Copie indisponible";
            }}
        }});
        </script>
        """,
        height=44,
    )


def render_query_variant_panel(variant_key: str, definition: dict, search_session_id: str) -> None:
    st.markdown(f"**{definition.get('label', variant_key.title())}**")
    st.caption(definition.get("description", ""))
    st.text_area(
        f"Requête {definition.get('label', variant_key.title())}",
        value=definition.get("query", "") or "Aucune requête générée pour cette variante.",
        height=180,
        key=f"strategy_builder_query_{search_session_id}_{variant_key}",
    )
    concepts_used = definition.get("concepts_used") or []
    if concepts_used:
        st.caption(f"Concepts utilisés : {', '.join(concepts_used)}")
    else:
        st.caption("Aucun concept actif dans cette variante.")
    render_copy_button(definition.get("query", ""), f"{search_session_id}-{variant_key}")
