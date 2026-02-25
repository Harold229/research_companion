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


PROMPT = """Tu es un expert en méthodologie de recherche scientifique.

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


def analyze_with_claude(question: str) -> dict:
    client = get_anthropic_client()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(question=question)}]
    )
    return parse_response(message.content[0].text)


def analyze_with_openai(question: str) -> dict:
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT.format(question=question)}]
    )
    return parse_response(response.choices[0].message.content)


def analyze_research_question(question: str) -> dict:
    # Essaie Claude d'abord
    for attempt in range(2):
        try:
            return analyze_with_claude(question)
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 1:
                time.sleep(3)
            else:
                break
        except Exception:
            break

    # Fallback sur OpenAI
    try:
        return analyze_with_openai(question)
    except Exception as e:
        raise Exception(f"Both AI providers are unavailable. Please try again later.")


if __name__ == "__main__":
    result = analyze_research_question(
        "je veux étudier si les médecins connaissent bien la prise en charge de l'hyperkaliémie au Bénin"
    )
    print(result)