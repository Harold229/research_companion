import anthropic
import streamlit as st
import os 
from dotenv import load_dotenv
load_dotenv()

def get_client():
    """
    Crée un client Anthropic en lisant la clé API
    depuis les Secrets Streamlit ou le fichier .env
    """
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"].strip()
    except:
        api_key = os.getenv("ANTHROPIC_API_KEY").strip()
    
    return anthropic.Anthropic(api_key=api_key)
def analyze_research_question(question: str) -> dict : 
    """
    Prendre une question en langage naturel et retourner les composantes structurées
    
    """

    client = get_client()

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": f""" Tu es un expert en methodologie de recherche scientifque.
             
 Un étudiant te soumet sa question de recherche :
             "{question}"
              
             Ton travail:

             1. Identifier le bon framework (PICO,PEO, SPIDER)
             2. Extraire les composantes selon le framework
             3. Traduire chaque composante en anglais pour PubMed
            
             
 Réponds UNIQUEMENT en JSON avec cette structure :
            {{
                "framework": "PICO" ou "PEO" ou "SPIDER",
                "explanation": "pourquoi ce framework en une phrase",
                "components": {{
                    "population": "...",
                    "intervention": "..." ou null,
                    "comparison": "..." ou null,
                    "outcome": "..." ou null,
                    "exposure": "..." ou null
                }},
                "components_english": {{
                    "population": "...",
                    "intervention": "..." ou null,
                    "comparison": "..." ou null,
                    "outcome": "..." ou null,
                    "exposure": "..." ou null
                }},
                "research_level": 1 ou 2 ou 3
            }}  """ }
        ]
    )         

    print("Message complet:", message)
    print("Content:", message.content)
    response_text = message.content[0].text
    
    import json
    
    response_text = message.content[0].text
    print("Stop reason:", message.stop_reason)
    print("Contenu brut:", repr(response_text))
    clean = response_text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]  # enlève ```json
    if clean.startswith("```"):
        clean = clean[3:]  # enlève ```
    if clean.endswith("```"):
        clean = clean[:-3]  # enlève ``` à la fin

    return json.loads(clean.strip())

if __name__ == "__main__":
    result = analyze_research_question(
        "je veux étudier si les médecins connaissent bien la prise en charge de l'hyperkaliémie au Bénin"
    )
    print(result)