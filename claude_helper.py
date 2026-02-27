import anthropic
import streamlit as st
import os
import time
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def get_anthropic_client():
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"].strip()
    except:
        api_key = os.getenv("ANTHROPIC_API_KEY").strip()
    return anthropic.Anthropic(api_key=api_key)


def get_openai_client():
    try:
        api_key = st.secrets["OPENAI_API_KEY"].strip()
    except:
        api_key = os.getenv("OPENAI_API_KEY").strip()
    return OpenAI(api_key=api_key)


PROMPT = """Tu es un expert en méthodologie de recherche scientifique et en terminologie MeSH de PubMed.

Un étudiant te soumet sa question de recherche :
"{question}"

L'étudiant veut : {intent}

TON TRAVAIL :
1. Adapter ta réponse selon l'intent
2. Identifier le bon framework si nécessaire
3. Reformuler la question correctement
4. Extraire les composantes avec synonymes TIAB

RÈGLE 1 — INTENT :
- intent "explore" → pas de framework, 2 composantes max (population + sujet), query large
- intent "structure" → PICO, PEO ou SPIDER selon la question

RÈGLE 2 — FRAMEWORK pour intent "structure" :
- "connaissance / savoir / pratique / attitudes" → PEO obligatoirement
- Question avec intervention et comparaison → PICO
- Question qualitative / expérience vécue → SPIDER

RÈGLE 3 — REFORMULATION :
Reformule la question en français académique correct.
- explore : "Existe-t-il des études sur [sujet] chez [population] ?"
- structure PEO : "Dans quelle mesure [population] connaît-elle [sujet] ?"
- structure PICO : "Chez [population], [intervention] améliore-t-elle [outcome] ?"

Si la question est déjà bien formulée académiquement → 
    research_question_fr: null
    research_question_comment: "Votre question est bien formulée."

Si la question peut être améliorée →
    research_question_fr: "version améliorée..."
    research_question_comment: "Voici une formulation plus précise."

RÈGLE 4 — SYNONYMES TIAB :
Pour chaque composante, génère 3-5 synonymes couramment utilisés dans les titres/abstracts des publications médicales.
Exemple : "enfants obèses" → tiab: "obese children OR childhood obesity OR pediatric obesity OR overweight children"

RÈGLE 5 — CONCEPTS ÉPIDÉMIOLOGIQUES STANDARDS :
Ces concepts ont toujours un bloc MeSH direct :
- connaissance / KAP → "\"Health Knowledge, Attitudes, Practice\"[MeSH] OR \"Clinical Competence\"[MeSH] OR \"Surveys and Questionnaires\"[MeSH] OR \"Practice Patterns, Physicians\"[MeSH]"
- prévalence / incidence → "\"Prevalence\"[MeSH] OR \"Incidence\"[MeSH]"
- facteurs de risque → "\"Risk Factors\"[MeSH]"
- mortalité / morbidité → "\"Mortality\"[MeSH] OR \"Morbidity\"[MeSH]"
- prise en charge / traitement → "\"Disease Management\"[MeSH] OR \"Therapeutics\"[MeSH]"

RÈGLE 6 — POPULATION MÉDICALE :
Format : "Spécialité, Physicians"
- "médecins" → "Physicians, General Practitioners"
- "cardiologues" → "Cardiologists, Physicians"
- "infirmiers" → "Nurses, Nursing Staff"
- "médecins de réanimation" → "Physicians, Intensive Care Units"

RÈGLE 7 — PAYS AFRICAINS :
Si un pays africain est mentionné → extraire dans geography :
- country: nom du pays en anglais
- region: région (West Africa, East Africa, Central Africa...)
- continent: "Sub-Saharan Africa" ou "North Africa"
- geography_tiab: "Benin OR \"West Africa\" OR \"Sub-Saharan Africa\""
Ne jamais mettre la géographie dans population_tiab

EXEMPLES :

Exemple 1 — Explore :
Question : "est-ce qu'il y a des études sur l'hyperkaliémie chez les enfants ?"
Intent : explore
→ framework: null
→ research_question_fr: "Existe-t-il des études sur l'hyperkaliémie chez les enfants ?"
→ population: "Children"
→ population_tiab: "children OR pediatric OR childhood OR youth"
→ exposure: "Hyperkalemia"
→ exposure_tiab: "hyperkalemia OR hyperkalaemia OR high potassium OR elevated potassium"

Exemple 2 — Structure PEO :
Question : "connaissance des médecins sur la prise en charge de l'hyperkaliémie au Bénin"
Intent : structure
→ framework: "PEO"
→ research_question_fr: "Dans quelle mesure les médecins généralistes connaissent-ils la prise en charge de l'hyperkaliémie au Bénin ?"
→ population: "Physicians, General Practitioners"
→ population_tiab: "physicians OR doctors OR general practitioners OR clinicians OR Benin OR West Africa OR Sub-Saharan Africa"
→ exposure: "Hyperkalemia"
→ exposure_tiab: "hyperkalemia OR hyperkalaemia OR high potassium"
→ outcome_mesh: "\"Health Knowledge, Attitudes, Practice\"[MeSH] OR \"Clinical Competence\"[MeSH] OR \"Disease Management\"[MeSH] OR \"Surveys and Questionnaires\"[MeSH] OR \"Practice Patterns, Physicians\"[MeSH]"
→ outcome_tiab: "knowledge OR practice OR management OR survey OR questionnaire"

Exemple 3 — Structure PICO :
Question : "prévalence du diabète chez les enfants au Mali"
Intent : structure
→ framework: "PICO"
→ research_question_fr: "Quelle est la prévalence du diabète chez les enfants au Mali ?"
→ population: "Children"
→ population_tiab: "children OR pediatric OR childhood OR youth OR Mali OR West Africa OR Sub-Saharan Africa"
→ intervention: "Diabetes Mellitus"
→ intervention_tiab: "diabetes OR diabetic OR hyperglycemia OR type 2 diabetes"
→ outcome_mesh: "\"Prevalence\"[MeSH] OR \"Incidence\"[MeSH]"
→ outcome_tiab: "prevalence OR incidence OR epidemiology OR frequency OR burden"


Réponds UNIQUEMENT en JSON :
{{
    "intent": "explore" ou "structure",
    "framework": "PICO" ou "PEO" ou "SPIDER" ou null,
    "explanation": "pourquoi ce framework en une phrase",
    "research_question_fr": "..." ou null,
    "research_question_en": "..." ou null,
    "research_question_comment":"....",
    "geography": {{
        "country": "..." ou null,
        "region": "..." ou null,
        "continent": "..." ou null
    }},
    "geography_tiab": "..." ou null,
    "components": {{
        "population": "...",
        "intervention": "..." ou null,
        "comparison": "..." ou null,
        "outcome": "..." ou null,
        "exposure": "..." ou null
    }},
    "components_english": {{
        "population": "...",
        "population_tiab": "terme1 OR terme2 OR terme3",
        "intervention": "..." ou null,
        "intervention_mesh": "..." ou null,
        "intervention_tiab": "..." ou null,
        "comparison": "..." ou null,
        "outcome": "..." ou null,
        "outcome_mesh": "..." ou null,
        "outcome_tiab": "..." ou null,
        "exposure": "..." ou null,
        "exposure_tiab": "..." ou null
    }},
    
    "research_level": 1 ou 2 ou 3
}}"""

def parse_response(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return json.loads(clean.strip())


def analyze_with_claude(question: str, intent: str = "structure") -> dict:
    client = get_anthropic_client()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(question=question, intent=intent)}]
    )
    return parse_response(message.content[0].text)


def analyze_with_openai(question: str, intent: str = "structure") -> dict:
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(question=question, intent=intent)}]
    )
    return parse_response(response.choices[0].message.content)


def analyze_research_question(question: str, intent: str = "structure") -> dict:
    for attempt in range(2):
        try:
            return analyze_with_claude(question, intent)
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 1:
                time.sleep(3)
            else:
                break
        except Exception:
            break

    try:
        return analyze_with_openai(question, intent)
    except Exception as e:
        raise Exception("Both AI providers are unavailable. Please try again later.")

if __name__ == "__main__":
    questions = [
        ("est-ce qu'il y a des études sur l'hyperkaliémie chez les enfants", "explore"),
        ("connaissance des médecins sur la prise en charge de l'hyperkaliémie au Bénin", "structure"),
        ("prévalence du diabète chez les enfants au Mali", "structure")
    ]
    
    for question, intent in questions:
        print(f"\n=== {intent.upper()} ===")
        print(f"Question: {question}")
        result = analyze_research_question(question, intent=intent)
        print(result)