import anthropic
import streamlit as st
import os
import time
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from prompt_core import PROMPT_CORE

load_dotenv()


# ═══════════════════════════════════════════════════════════════
# CLIENTS API
# ═══════════════════════════════════════════════════════════════

def get_anthropic_client():
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"].strip()
    except Exception:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return anthropic.Anthropic(api_key=api_key)


def get_openai_client():
    try:
        api_key = st.secrets["OPENAI_API_KEY"].strip()
    except Exception:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
    return OpenAI(api_key=api_key)


# ═══════════════════════════════════════════════════════════════
# CHARGEMENT DES EXEMPLES
# ═══════════════════════════════════════════════════════════════

_EXAMPLES_CACHE = None

def load_examples() -> list:
    """Charge examples.json une seule fois (cache mémoire)."""
    global _EXAMPLES_CACHE
    if _EXAMPLES_CACHE is not None:
        return _EXAMPLES_CACHE

    examples_path = Path(__file__).parent / "examples.json"
    if not examples_path.exists():
        raise FileNotFoundError(
            f"examples.json introuvable dans {examples_path.parent}. "
            "Place-le à côté de claude_helper.py."
        )
    with open(examples_path, "r", encoding="utf-8") as f:
        _EXAMPLES_CACHE = json.load(f)
    return _EXAMPLES_CACHE


# ═══════════════════════════════════════════════════════════════
# SÉLECTION DYNAMIQUE DES EXEMPLES
# ═══════════════════════════════════════════════════════════════

KEYWORD_TO_TAGS = {
    # Framework / concept triggers
    "connaissance": ["M-KAP", "PEO"],
    "savoir": ["M-KAP", "PEO"],
    "pratique": ["M-KAP", "PEO"],
    "attitudes": ["M-KAP", "PEO"],
    "adhérence": ["M-ADH", "PEO"],
    "observance": ["M-ADH", "PEO"],
    "compliance": ["M-ADH", "PEO"],
    "vécu": ["SPIDER", "qualitative"],
    "perception": ["SPIDER", "qualitative"],
    "expérience": ["SPIDER", "qualitative"],
    "barrières": ["SPIDER", "qualitative"],
    "prévalence": ["M-PREV", "PICO"],
    "incidence": ["M-PREV", "PICO"],
    "facteurs de risque": ["M-RISK", "PICO"],
    "déterminants": ["M-RISK", "PICO"],
    "mortalité": ["M-MORT", "PICO"],
    "morbidité": ["M-MORT", "PICO"],
    "survie": ["M-MORT", "PICO"],
    "traitement": ["M-THER", "PICO"],
    "prise en charge": ["M-THER", "PICO"],
    "efficacité": ["PICO", "comparison"],
    "vs": ["PICO", "comparison"],
    "éducation": ["M-EDU", "PICO"],
    "pairs": ["M-PEER", "PEO"],
    "influence sociale": ["M-PEER", "PEO"],
    # Geo triggers
    "afrique": ["geo_africa"],
    "bénin": ["geo_africa"],
    "mali": ["geo_africa"],
    "sénégal": ["geo_africa"],
    "cameroun": ["geo_africa"],
    "togo": ["geo_africa"],
    "niger": ["geo_africa"],
    "rwanda": ["geo_africa"],
    "éthiopie": ["geo_africa"],
    "burkina": ["geo_africa"],
    "côte d'ivoire": ["geo_africa"],
}


def select_examples(question: str, intent: str, max_examples: int = 3) -> str:
    """
    Sélectionne les 2-3 exemples les plus pertinents depuis examples.json.
    Retourne le texte formaté prêt à injecter dans le prompt.
    """
    examples_db = load_examples()
    question_lower = question.lower()

    # 1. Construire les tags cibles
    target_tags = {intent}
    for keyword, tags in KEYWORD_TO_TAGS.items():
        if keyword in question_lower:
            target_tags.update(tags)

    # 2. Scorer chaque exemple
    scored = []
    for ex in examples_db:
        ex_tags = set(ex["tags"])
        overlap = len(target_tags & ex_tags)
        scored.append((overlap, ex))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 3. Sélectionner top N en diversifiant les frameworks
    selected = []
    frameworks_seen = set()

    for score, ex in scored:
        if len(selected) >= max_examples:
            break

        fw = None
        for tag in ex["tags"]:
            if tag in ("PEO", "PICO", "SPIDER", "PICOTS"):
                fw = tag
                break

        if fw and fw in frameworks_seen and len(selected) < max_examples - 1:
            continue

        selected.append(ex)
        if fw:
            frameworks_seen.add(fw)

    # 4. Pour structure, toujours inclure l'exemple J (démo null)
    if intent == "structure":
        j_example = next((ex for ex in examples_db if ex["id"] == "J"), None)
        if j_example and j_example not in selected:
            if len(selected) >= max_examples:
                selected[-1] = j_example
            else:
                selected.append(j_example)

    # 5. Formater pour injection
    parts = []
    for ex in selected:
        example_json_str = json.dumps(ex["example_json"], indent=2, ensure_ascii=False)
        parts.append(
            f'--- Exemple {ex["id"]} ---\n'
            f'Question : "{ex["question_fr"]}"\n'
            f'Intent : {ex["intent"]}\n\n'
            f'{example_json_str}'
        )

    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# CONSTRUCTION DU PROMPT FINAL
# ═══════════════════════════════════════════════════════════════

def build_prompt(question: str, intent: str) -> str:
    """Assemble le prompt core + les exemples dynamiques."""
    examples_text = select_examples(question, intent, max_examples=3)
    return PROMPT_CORE.format(
        question=question,
        intent=intent,
        examples=examples_text
    )


# ═══════════════════════════════════════════════════════════════
# PARSING RÉPONSE
# ═══════════════════════════════════════════════════════════════

def parse_response(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return json.loads(clean.strip())


# ═══════════════════════════════════════════════════════════════
# APPELS API
# ═══════════════════════════════════════════════════════════════

def analyze_with_claude(question: str, intent: str = "structure") -> dict:
    client = get_anthropic_client()
    prompt = build_prompt(question, intent)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_response(message.content[0].text)


def analyze_with_openai(question: str, intent: str = "structure") -> dict:
    client = get_openai_client()
    prompt = build_prompt(question, intent)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_response(response.choices[0].message.content)


def analyze_research_question(question: str, intent: str = "structure") -> dict:
    """Essaie Claude, fallback sur OpenAI."""
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
    except Exception:
        raise Exception("Both AI providers are unavailable. Please try again later.")


# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    questions = [
        ("est-ce qu'il y a des études sur l'hyperkaliémie chez les enfants", "explore"),
        ("connaissance des médecins sur la prise en charge de l'hyperkaliémie au Bénin", "structure"),
        ("prévalence du diabète chez les enfants au Mali", "structure"),
        ("adhérence au traitement antirétroviral chez les adolescents au Cameroun", "structure"),
    ]

    for question, intent in questions:
        print(f"\n{'='*60}")
        print(f"INTENT: {intent.upper()}")
        print(f"QUESTION: {question}")

        # Montrer quels exemples sont sélectionnés
        examples_db = load_examples()
        target_tags = {intent}
        q_lower = question.lower()
        for kw, tags in KEYWORD_TO_TAGS.items():
            if kw in q_lower:
                target_tags.update(tags)
        print(f"TAGS DÉTECTÉS: {sorted(target_tags)}")

        examples_text = select_examples(question, intent)
        for line in examples_text.split("\n"):
            if line.startswith("--- Exemple"):
                print(f"  → {line}")

        prompt = build_prompt(question, intent)
        print(f"TAILLE PROMPT: {len(prompt)} caractères")

        # Décommenter pour tester avec l'API :
        # result = analyze_research_question(question, intent=intent)
        # print(json.dumps(result, indent=2, ensure_ascii=False))
