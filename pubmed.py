import requests 
import xml.etree.ElementTree as ET
def get_mesh_terms(term: str) -> list:
    """
    Prend un terme de recherche et renvoie une liste de termes Mesh associés depuis l'API NCBI

    """

    base_url =  "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "xml",
        "retmax":0
    }

    response = requests.get(base_url, params = params)
    root = ET.fromstring(response.text)
    query_translation = root.find("QueryTranslation")

    if query_translation is not None:
        return query_translation.text
    return f'"{term}"[ALL fields]'

# Test rapide
if __name__ == "__main__":
    result = get_mesh_terms("diabetes")
    print(result)



def build_pico_query(population: str, intervention: str = None,
                     outcome: str = None, comparaison: str = None) -> str:
    """
Assemble une query PubMed complète à partir des composantes PICO.
    """
    blocks = []

 # Chaque terme PICO devient un bloc MeSH 
    if population:
        blocks.append(f"({get_mesh_terms(population)})")
    if intervention:
        blocks.append(f"({get_mesh_terms(intervention)})")
    if outcome:
        blocks.append(f"({get_mesh_terms(outcome)})")
    if comparaison:
        blocks.append(f"({get_mesh_terms(comparaison)})")
    
    # On assemble les blocs avec AND

    return " \nAND ".join(blocks)


if __name__ == "__main__":
    query = build_pico_query(
        population = "children with obesity",
        intervention = "physical activity",
        outcome = "BMI reduction"
    )
    print(query)
