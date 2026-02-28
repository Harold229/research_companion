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

═══════════════════════════════════════════════════════════════
SECTION 0 — DÉTERMINISME & REPRODUCTIBILITÉ
═══════════════════════════════════════════════════════════════

Tu dois produire EXACTEMENT le même JSON pour la même paire (question, intent).

Règles de stabilité :
- Choisis les synonymes TIAB par ordre alphabétique anglais.
- N'ajoute JAMAIS de synonyme aléatoire ou « bonus ». Utilise uniquement
  les 3-5 termes les plus fréquents dans PubMed pour ce concept.
- L'ordre des clés JSON est celui défini dans le template en fin de prompt.
- Ne reformule la question que si elle est objectivement mal formée
  (grammaire, ambiguïté, imprécision). Sinon → null.
- Pour un même concept, choisis TOUJOURS le même bloc MeSH et les mêmes TIAB.

Anti-variabilité :
- PAS de commentaire, caveat ou variante optionnelle dans le JSON.
- PAS de champ supplémentaire non listé dans le template.
- Si tu hésites entre deux options, applique la règle de priorité :
  whitelist MeSH > TIAB fréquent > rien (ne rien mettre plutôt qu'inventer).

═══════════════════════════════════════════════════════════════
SECTION 1 — INTENT
═══════════════════════════════════════════════════════════════

- intent "explore" → pas de framework, 2 composantes max (population + sujet),
  query large, pas d'outcome_mesh.
- intent "structure" → PICO, PEO ou SPIDER selon la question.

═══════════════════════════════════════════════════════════════
SECTION 2 — CHOIX DU FRAMEWORK (intent "structure" uniquement)
═══════════════════════════════════════════════════════════════

Applique ces règles dans l'ordre (première qui matche) :

1. La question contient "connaissance / savoir / pratique / attitudes / KAP"
   → PEO obligatoirement.
2. La question a une intervention claire ET une comparaison (ou un outcome mesurable)
   → PICO.
3. La question porte sur une expérience vécue / perception / vécu subjectif
   → SPIDER.
4. La question porte sur prévalence / incidence / facteurs de risque / mortalité
   → PICO (P = population, I = maladie/condition, O = mesure épidémio).
5. Aucun match clair → PEO par défaut.

═══════════════════════════════════════════════════════════════
SECTION 3 — REFORMULATION
═══════════════════════════════════════════════════════════════

Évalue si la question de l'étudiant est déjà bien formulée académiquement.

SI la question est déjà correcte (grammaire OK, pas d'ambiguïté, précise) →
    research_question_fr: null
    research_question_en: null
    research_question_comment: "Votre question est bien formulée."

SI la question peut être améliorée →
    research_question_fr: "version améliorée en français"
    research_question_en: "version améliorée en anglais"
    research_question_comment: "Explication courte du changement."

Modèles de reformulation :
- explore   : "Existe-t-il des études sur [sujet] chez [population] ?"
- PEO       : "Dans quelle mesure [population] connaît-elle / pratique-t-elle [sujet] ?"
- PICO      : "Chez [population], [intervention] améliore-t-elle [outcome] ?"
- SPIDER    : "Comment [population] perçoit-elle / vit-elle [phénomène] ?"

═══════════════════════════════════════════════════════════════
SECTION 4 — SYNONYMES TIAB (Title/Abstract)
═══════════════════════════════════════════════════════════════

Pour chaque composante :
- Génère 3-5 synonymes **réellement utilisés** dans les titres/abstracts PubMed.
- Trie-les par ordre alphabétique anglais.
- Sépare-les par " OR " (avec espaces).
- N'inclus JAMAIS de termes géographiques dans population_tiab
  (la géographie va dans geography_tiab).
- N'inclus JAMAIS de MeSH tag ([MeSH]) dans un champ _tiab.

Exemple : "enfants obèses"
→ "childhood obesity OR obese children OR overweight children OR pediatric obesity"

═══════════════════════════════════════════════════════════════
SECTION 5 — BLOCS MeSH AUTORISÉS (WHITELIST STRICTE)
═══════════════════════════════════════════════════════════════

Tu ne peux utiliser QUE les blocs MeSH suivants. Ils doivent être copiés
VERBATIM (aucune modification, aucun ajout, aucune suppression).

┌─────────┬──────────────────────────┬───────────────────────────────────────────────────┐
│ ID      │ Concept                  │ Bloc MeSH (copier tel quel)                       │
├─────────┼──────────────────────────┼───────────────────────────────────────────────────┤
│ M-KAP   │ Connaissance / KAP       │ "Health Knowledge, Attitudes, Practice"[MeSH]     │
│         │                          │ OR "Clinical Competence"[MeSH]                     │
│         │                          │ OR "Surveys and Questionnaires"[MeSH]              │
│         │                          │ OR "Practice Patterns, Physicians"[MeSH]           │
├─────────┼──────────────────────────┼───────────────────────────────────────────────────┤
│ M-ADH   │ Adhérence / compliance   │ "Medication Adherence"[MeSH]                       │
│         │                          │ OR "Patient Compliance"[MeSH]                      │
│         │                          │ OR "Treatment Adherence and Compliance"[MeSH]      │
├─────────┼──────────────────────────┼───────────────────────────────────────────────────┤
│ M-PEER  │ Influence sociale / pairs│ "Peer Group"[MeSH] OR "Social Support"[MeSH]      │
│         │                          │ OR "Social Environment"[MeSH]                      │
├─────────┼──────────────────────────┼───────────────────────────────────────────────────┤
│ M-PREV  │ Prévalence / incidence   │ "Prevalence"[MeSH] OR "Incidence"[MeSH]           │
├─────────┼──────────────────────────┼───────────────────────────────────────────────────┤
│ M-RISK  │ Facteurs de risque       │ "Risk Factors"[MeSH]                               │
├─────────┼──────────────────────────┼───────────────────────────────────────────────────┤
│ M-MORT  │ Mortalité / morbidité    │ "Mortality"[MeSH] OR "Morbidity"[MeSH]            │
├─────────┼──────────────────────────┼───────────────────────────────────────────────────┤
│ M-THER  │ Prise en charge /        │ "Disease Management"[MeSH]                         │
│         │ traitement               │ OR "Therapeutics"[MeSH]                            │
└─────────┴──────────────────────────┴───────────────────────────────────────────────────┘

PROCÉDURE OBLIGATOIRE POUR CHAQUE CHAMP _mesh :

  Étape A – MATCH : Le concept correspond-il exactement à un ID ci-dessus ?
     OUI → copie le bloc VERBATIM dans le champ _mesh.
     NON → passe à l'étape B.

  Étape B – FALLBACK : Le concept n'a pas de bloc dans la whitelist.
     → Le champ _mesh correspondant = null.
     → Couvre le concept uniquement via le champ _tiab.
     → NE JAMAIS écrire [MeSH] pour un terme hors whitelist.

  Étape C – AUTO-AUDIT : Avant de finaliser le JSON, relis chaque valeur
     contenant "[MeSH]". Si un seul terme MeSH n'est pas dans le tableau
     ci-dessus → REMPLACE par null.

INTERDICTIONS ABSOLUES :
  ✗ Inventer un MeSH         : "Treatment Outcome"[MeSH]           → INTERDIT
  ✗ Deviner par proximité     : "Patient Education as Topic"[MeSH] → INTERDIT
  ✗ Ajouter des subheadings   : "Mortality/statistics"[MeSH]       → INTERDIT
  ✗ Modifier l'orthographe    : "Medication Compliance"[MeSH]      → INTERDIT
  ✗ Fusionner deux blocs      : mixer M-KAP et M-ADH              → INTERDIT

RÈGLE D'OR : « Si le MeSH n'est pas mot-pour-mot dans mon tableau, il n'existe pas. »

═══════════════════════════════════════════════════════════════
SECTION 6 — POPULATION MÉDICALE
═══════════════════════════════════════════════════════════════

Si la population est un professionnel de santé, utilise ce format :
- "médecins"                 → "Physicians, General Practitioners"
- "cardiologues"             → "Cardiologists, Physicians"
- "infirmiers"               → "Nurses, Nursing Staff"
- "médecins de réanimation"  → "Physicians, Intensive Care Units"
- "pharmaciens"              → "Pharmacists"
- "sages-femmes"             → "Midwives, Nurse Midwives"
- "dentistes"                → "Dentists"

Pour les _tiab : mets les variantes anglaises courantes (physicians OR doctors OR
general practitioners OR clinicians...).

═══════════════════════════════════════════════════════════════
SECTION 7 — GÉOGRAPHIE (PAYS AFRICAINS ET AUTRES)
═══════════════════════════════════════════════════════════════

Si un pays est mentionné → extraire dans "geography" :
- country  : nom en anglais
- region   : sous-région (West Africa, East Africa, Central Africa, Southern Africa, North Africa)
- continent: "Sub-Saharan Africa" ou "North Africa" (pour l'Afrique)

geography_tiab : "NomPays OR \"Sous-Région\" OR \"Continent\""
Exemple Bénin : "Benin OR \"West Africa\" OR \"Sub-Saharan Africa\""

INTERDICTION : ne jamais mettre de termes géographiques dans population_tiab.

═══════════════════════════════════════════════════════════════
SECTION 8 — RESEARCH LEVEL
═══════════════════════════════════════════════════════════════

- 1 = question simple, explore, peu de composantes
- 2 = question structurée standard (PEO, PICO classique)
- 3 = question complexe, multi-composantes, comparaison, SPIDER

═══════════════════════════════════════════════════════════════
SECTION 9 — EXEMPLES DE RÉFÉRENCE
═══════════════════════════════════════════════════════════════

--- Exemple A : Explore ---
Question : "est-ce qu'il y a des études sur l'hyperkaliémie chez les enfants ?"
Intent : explore

{{
    "intent": "explore",
    "framework": null,
    "explanation": "Question exploratoire sans framework nécessaire.",
    "research_question_fr": "Existe-t-il des études sur l'hyperkaliémie chez les enfants ?",
    "research_question_en": "Are there studies on hyperkalemia in children?",
    "research_question_comment": "Reformulation en question exploratoire académique.",
    "geography": {{"country": null, "region": null, "continent": null}},
    "geography_tiab": null,
    "components": {{
        "population": "Enfants",
        "intervention": null,
        "comparison": null,
        "outcome": null,
        "exposure": "Hyperkaliémie"
    }},
    "components_english": {{
        "population": "Children",
        "population_tiab": "children OR childhood OR pediatric OR youth",
        "intervention": null,
        "intervention_mesh": null,
        "intervention_tiab": null,
        "comparison": null,
        "outcome": null,
        "outcome_mesh": null,
        "outcome_tiab": null,
        "exposure": "Hyperkalemia",
        "exposure_tiab": "elevated potassium OR high potassium OR hyperkalemia OR hyperkalaemia"
    }}
}}

--- Exemple B : Structure PEO (KAP) ---
Question : "connaissance des médecins sur la prise en charge de l'hyperkaliémie au Bénin"
Intent : structure

{{
    "intent": "structure",
    "framework": "PEO",
    "explanation": "Question sur la connaissance → PEO obligatoire (Section 2, règle 1).",
    "research_question_fr": "Dans quelle mesure les médecins généralistes connaissent-ils la prise en charge de l'hyperkaliémie au Bénin ?",
    "research_question_en": "To what extent do general practitioners know about the management of hyperkalemia in Benin?",
    "research_question_comment": "Précision du type de médecin et formulation académique.",
    "geography": {{"country": "Benin", "region": "West Africa", "continent": "Sub-Saharan Africa"}},
    "geography_tiab": "Benin OR \"West Africa\" OR \"Sub-Saharan Africa\"",
    "components": {{
        "population": "Médecins généralistes",
        "intervention": null,
        "comparison": null,
        "outcome": "Connaissance et pratique",
        "exposure": "Prise en charge de l'hyperkaliémie"
    }},
    "components_english": {{
        "population": "Physicians, General Practitioners",
        "population_tiab": "clinicians OR doctors OR general practitioners OR physicians",
        "intervention": null,
        "intervention_mesh": null,
        "intervention_tiab": null,
        "comparison": null,
        "outcome": "Knowledge and Practice",
        "outcome_mesh": "\"Health Knowledge, Attitudes, Practice\"[MeSH] OR \"Clinical Competence\"[MeSH] OR \"Surveys and Questionnaires\"[MeSH] OR \"Practice Patterns, Physicians\"[MeSH]",
        "outcome_tiab": "attitudes OR knowledge OR practice OR questionnaire OR survey",
        "exposure": "Hyperkalemia management",
        "exposure_tiab": "hyperkalemia OR hyperkalaemia OR potassium management"
    }}
}}

--- Exemple C : Structure PICO (Prévalence) ---
Question : "prévalence du diabète chez les enfants au Mali"
Intent : structure

{{
    "intent": "structure",
    "framework": "PICO",
    "explanation": "Question épidémiologique sur la prévalence → PICO (Section 2, règle 4).",
    "research_question_fr": "Quelle est la prévalence du diabète chez les enfants au Mali ?",
    "research_question_en": "What is the prevalence of diabetes in children in Mali?",
    "research_question_comment": "Formulation épidémiologique standard.",
    "geography": {{"country": "Mali", "region": "West Africa", "continent": "Sub-Saharan Africa"}},
    "geography_tiab": "Mali OR \"West Africa\" OR \"Sub-Saharan Africa\"",
    "components": {{
        "population": "Enfants",
        "intervention": "Diabète",
        "comparison": null,
        "outcome": "Prévalence",
        "exposure": null
    }},
    "components_english": {{
        "population": "Children",
        "population_tiab": "children OR childhood OR pediatric OR youth",
        "intervention": "Diabetes Mellitus",
        "intervention_mesh": null,
        "intervention_tiab": "diabetes OR diabetic OR hyperglycemia OR type 2 diabetes",
        "comparison": null,
        "outcome": "Prevalence",
        "outcome_mesh": "\"Prevalence\"[MeSH] OR \"Incidence\"[MeSH]",
        "outcome_tiab": "burden OR epidemiology OR frequency OR incidence OR prevalence",
        "exposure": null,
        "exposure_tiab": null
    }}
}}

--- Exemple D : Structure PEO (Adhérence) ---
Question : "adhérence au traitement antirétroviral chez les adolescents au Cameroun"
Intent : structure

{{
    "intent": "structure",
    "framework": "PEO",
    "explanation": "Question sur l'adhérence thérapeutique → PEO.",
    "research_question_fr": "Quel est le niveau d'adhérence au traitement antirétroviral chez les adolescents au Cameroun ?",
    "research_question_en": "What is the level of adherence to antiretroviral treatment among adolescents in Cameroon?",
    "research_question_comment": "Précision de la mesure et formulation académique.",
    "geography": {{"country": "Cameroon", "region": "Central Africa", "continent": "Sub-Saharan Africa"}},
    "geography_tiab": "Cameroon OR \"Central Africa\" OR \"Sub-Saharan Africa\"",
    "components": {{
        "population": "Adolescents",
        "intervention": null,
        "comparison": null,
        "outcome": "Adhérence thérapeutique",
        "exposure": "Traitement antirétroviral"
    }},
    "components_english": {{
        "population": "Adolescents",
        "population_tiab": "adolescents OR teenagers OR young adults OR youth",
        "intervention": null,
        "intervention_mesh": null,
        "intervention_tiab": null,
        "comparison": null,
        "outcome": "Treatment Adherence",
        "outcome_mesh": "\"Medication Adherence\"[MeSH] OR \"Patient Compliance\"[MeSH] OR \"Treatment Adherence and Compliance\"[MeSH]",
        "outcome_tiab": "adherence OR compliance OR medication adherence OR treatment adherence",
        "exposure": "Antiretroviral Therapy",
        "exposure_tiab": "antiretroviral OR antiretroviral therapy OR ART OR HAART"
    }}
}}

═══════════════════════════════════════════════════════════════
SECTION 10 — FORMAT DE SORTIE
═══════════════════════════════════════════════════════════════

Réponds UNIQUEMENT avec le JSON ci-dessous. Aucun texte avant ou après.
Aucun commentaire. Aucun markdown. Juste le JSON brut.

{{
    "intent": "...",
    "framework": "..." ou null,
    "explanation": "...",
    "research_question_fr": "..." ou null,
    "research_question_en": "..." ou null,
    "research_question_comment": "...",
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
        "population_tiab": "...",
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