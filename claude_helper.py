import anthropic
import streamlit as st
import os
import time
import json
from dotenv import load_dotenv

load_dotenv()


def get_client():
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"].strip()
    except:
        api_key = os.getenv("ANTHROPIC_API_KEY").strip()
    return anthropic.Anthropic(api_key=api_key)


def analyze_research_question(question: str) -> dict:
    client = get_client()

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": f"""Tu es un expert en méthodologie de recherche scientifique.

Un étudiant te soumet sa question de recherche :
"{question}"

Ton travail:
1. Identifier le bon framework (PICO, PEO, SPIDER)
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
}}"""}
                ]
            )

            response_text = message.content[0].text
            clean = response_text.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            if clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            return json.loads(clean.strip())

        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                if attempt < 2:
                    time.sleep(3)
                else:
                    raise Exception("The AI is temporarily busy. Please try again in a moment.")
            else:
                raise e


if __name__ == "__main__":
    result = analyze_research_question(
        "je veux étudier si les médecins connaissent bien la prise en charge de l'hyperkaliémie au Bénin"
    )
    print(result)