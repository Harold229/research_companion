import requests 
import xml.etree.ElementTree as ET
import streamlit as st


@st.cache_data(ttl = 3600)
def get_mesh_terms(term: str) -> list:
    """
    Prend un terme de recherche et renvoie une liste de termes Mesh associés depuis l'API NCBI

    """
    try:
        base_url =  "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": term,
            "retmode": "xml",
        "retmax":0
    }

        response = requests.get(base_url, params = params, timeout = 10)

        if response.status_code != 200 or not response.text.strip():
            return f'"{term}"[ALL fields]'

        root = ET.fromstring(response.text)
        query_translation = root.find("QueryTranslation")

        if query_translation is not None:
            return query_translation.text
        return f'"{term}"[ALL fields]'
    except Exception:
           return f'"{term}"[All Fields]'





def build_pico_query(population: str, intervention: str = None,
                     intervention_mesh: str = None,
                     outcome: str = None, outcome_mesh: str = None,
                     comparaison: str = None,
                     exposure: str = None) -> str:
    blocks = []

    # Population — toujours via API
    if population:
        if "," in population:
            parts = [p.strip() for p in population.split(",")]
            for part in parts:
                blocks.append(f"({get_mesh_terms(part)})")
        else:
            blocks.append(f"({get_mesh_terms(population)})")

    # Intervention — bloc MeSH direct ou API
    if intervention_mesh:
        blocks.append(f"({intervention_mesh})")
    elif intervention:
        blocks.append(f"({get_mesh_terms(intervention)})")

    # Exposure — toujours via API
    if exposure:
        blocks.append(f"({get_mesh_terms(exposure)})")

    # Outcome — bloc MeSH direct ou API
    if outcome_mesh:
        blocks.append(f"({outcome_mesh})")
    elif outcome:
        blocks.append(f"({get_mesh_terms(outcome)})")

    # Comparaison — toujours via API
    if comparaison:
        blocks.append(f"({get_mesh_terms(comparaison)})")

    return "\nAND ".join(blocks)

if __name__ == "__main__":
    query = build_pico_query(
        population = "children with obesity",
        intervention = "physical activity",
        outcome = "BMI reduction"
    )
    print(query)
