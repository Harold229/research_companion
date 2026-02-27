import requests
import xml.etree.ElementTree as ET
import streamlit as st


@st.cache_data(ttl=3600)
def get_mesh_terms(term: str) -> str:
    """
    Retourne la QueryTranslation NCBI pour un terme
    """
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": term,
            "retmode": "xml",
            "retmax": 0
        }
        response = requests.get(base_url, params=params, timeout=10)

        if response.status_code != 200 or not response.text.strip():
            return f'"{term}"[All Fields]'

        root = ET.fromstring(response.text)
        query_translation = root.find("QueryTranslation")

        if query_translation is not None and query_translation.text:
            return query_translation.text
        return f'"{term}"[All Fields]'

    except Exception:
        return f'"{term}"[All Fields]'


def build_block(term: str, mesh_block: str = None, 
                tiab_term: str = None, mode: str = "sensitive") -> str:
    """
    Construit un bloc de recherche selon le mode.
    
    term       → terme simple envoyé à l'API PubMed
    mesh_block → bloc MeSH direct généré par Claude (optionnel)
    tiab_term  → terme TIAB (optionnel, utilise term par défaut)
    mode       → sensitive, balanced, specific
    """


    mesh = mesh_block if mesh_block else get_mesh_terms(term)
    
    # Utilise tiab_term si fourni, sinon terme brut
    tiab = f"(({tiab_term})[Title/Abstract])" if tiab_term else f'"{term}"[Title/Abstract]'

    if mode == "sensitive":
        return f"({mesh} OR {tiab})"
    elif mode == "balanced":
        return f"({mesh} AND {tiab})"
    else:
        return f"({mesh})"


def build_pico_query(population: str, population_tiab: str = None,
                     intervention: str = None, intervention_mesh: str = None, intervention_tiab: str = None,
                     outcome: str = None, outcome_mesh: str = None, outcome_tiab: str = None,
                     comparaison: str = None,
                     exposure: str = None, exposure_tiab: str = None,
                     geography_tiab: str = None,
                     mode: str = "sensitive") -> str:
    blocks = []

    # Population
    if population:
        if "," in population:
            parts = [p.strip() for p in population.split(",")]
            pop_blocks = [build_block(part, tiab_term=population_tiab, mode=mode) for part in parts]
            blocks.append(f"({' OR '.join(pop_blocks)})")
        else:
            blocks.append(build_block(population, tiab_term=population_tiab, mode=mode))

    # Intervention
    if intervention_mesh or intervention:
        blocks.append(build_block(
            term=intervention or "",
            mesh_block=intervention_mesh,
            tiab_term=intervention_tiab or intervention,
            mode=mode
        ))

    # Exposure
    if exposure:
        blocks.append(build_block(
            term=exposure,
            tiab_term=exposure_tiab or exposure,
            mode=mode
        ))

    # Outcome
    if outcome_mesh or outcome:
        blocks.append(build_block(
            term=outcome or "",
            mesh_block=outcome_mesh,
            tiab_term=outcome_tiab or outcome,
            mode=mode
        ))

    # Comparaison
    if comparaison:
        blocks.append(build_block(comparaison, mode=mode))

    # Geography
    if geography_tiab:
        # Applique [Title/Abstract] à chaque terme séparément
        terms = [t.strip().strip('"') for t in geography_tiab.split(" OR ")]
        geo_blocks = [f'"{t.strip()}"[Title/Abstract]' for t in terms]
        blocks.append(f"({' OR '.join(geo_blocks)})")
    return "\nAND ".join(blocks)
    
if __name__ == "__main__":
    print("=== SENSITIVE ===")
    print(build_pico_query(
        population="children with obesity",
        intervention="physical activity",
        outcome="BMI reduction",
        mode="sensitive"
    ))

    print("\n=== BALANCED ===")
    print(build_pico_query(
        population="children with obesity",
        intervention="physical activity",
        outcome="BMI reduction",
        mode="balanced"
    ))

    print("\n=== SPECIFIC ===")
    print(build_pico_query(
        population="children with obesity",
        intervention="physical activity",
        outcome="BMI reduction",
        mode="specific"
    ))