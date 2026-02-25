import streamlit as st
from pubmed import build_pico_query
from feedback import save_feedback
from claude_helper import analyze_research_question

st.title("Research Companion")
st.subheader("🔬 From research question to PubMed query")
st.divider()

mode = st.radio(
    "How do you want to start?",
    options=["guided", "natural"],
    format_func=lambda x: {
        "guided": "📋 I know PICO — guide me through the form",
        "natural": "💬 I have a research idea — let AI structure it for me"
    }[x],
    horizontal=True
)

st.divider()

# Variables par défaut pour le feedback
level = "natural"
population = ""
intervention = ""
outcome = ""
comparaison = ""

if mode == "natural":
    question = st.text_area(
        "Describe your research idea",
        placeholder="Ex: je veux étudier si les médecins connaissent bien la prise en charge de l'hyperkaliémie au Bénin",
        height=100
    )

    if st.button("Analyze my question"):
        if question:
            try:
                with st.spinner("Analyzing your question..."):
                    result = analyze_research_question(question)

                st.success(f"✅ Framework identified: **{result['framework']}**")
                st.info(f"💡 {result['explanation']}")
                st.subheader("📊 Your research components:")

                components = result['components']
                components_en = result['components_english']

                for key, value in components.items():
                    if value:
                        st.write(f"**{key.capitalize()}** : {value} → *{components_en[key]}*")

                st.divider()
                st.subheader("🔎 Your PubMed Query")

                query = build_pico_query(
                    population=components_en['population'],
                    intervention=components_en.get('intervention'),
                    outcome=components_en.get('outcome'),
                    comparaison=components_en.get('comparison')
                )

                st.code(query, language="text")
                st.link_button("🔗 Search on PubMed", f"https://pubmed.ncbi.nlm.nih.gov/?term={query}")

            except Exception as e:
                st.error(f"⚠️ {str(e)}")
        else:
            st.warning("⚠️ Please describe your research idea.")
else:
    level = st.radio(
        "📊 Where are you in your research?",
        options=["Level 1", "Level 2", "Level 3"],
        format_func=lambda x: {
            "Level 1": "Level 1 — I'm exploring the topic",
            "Level 2": "Level 2 — I have a research question (Population + Intervention + Outcome)",
            "Level 3": "Level 3 — I have a precise protocol (Full PICO)"
        }[x],
        help="Not sure? Start with Level 1. You can always refine later."
    )

    population = st.text_input(
        label="Population",
        placeholder="Ex: adults over 18 with type 2 diabetes",
        help="Who are the subjects of your study? Define age, medical condition, and context."
    )

    intervention = st.text_input(
        label="Intervention",
        placeholder="Ex: immunotherapy, vaccination, screening program",
        help="What treatment, program or exposure are you studying? Leave empty if no intervention."
    )

    outcome = None
    if level in ["Level 2", "Level 3"]:
        outcome = st.text_input(
            label="Outcome",
            placeholder="Ex: mortality, BMI reduction, quality of life improvement",
            help="What result are you measuring? Be precise — this is the core of your research question."
        )

    comparaison = None
    if level == "Level 3":
        comparaison = st.text_input(
            label="Comparison (optional)",
            placeholder="Ex: standard treatment, placebo",
            help="Leave empty if you are starting your research. Add a comparator only if you know exactly what you want to compare."
        )

    st.divider()

    if st.button("Generate my research question"):
        if level == "Level 1" and not population:
            st.warning("⚠️ Please fill in at least Population.")
        elif level == "Level 2" and not (population and outcome):
            st.warning("⚠️ Level 2 requires Population and Outcome.")
        elif level == "Level 3" and not (population and intervention and outcome):
            st.warning("⚠️ Level 3 requires Population, Intervention and Outcome.")
        else:
            if level == "Level 1":
                if intervention:
                    question = f"In {population}, what are the effects of {intervention}?"
                else:
                    question = f"In {population}, what does the literature say?"
            elif level == "Level 2":
                if intervention:
                    question = f"In {population}, does {intervention} improve/reduce {outcome}?"
                else:
                    question = f"In {population}, what is {outcome}?"
            else:
                if comparaison:
                    question = f"In {population}, does {intervention} compared to {comparaison} improve/reduce {outcome}?"
                else:
                    question = f"In {population}, does {intervention} improve/reduce {outcome}?"

            st.success("✅ Your research question:")
            st.write(question)

            st.divider()
            st.subheader("🔎 Your PubMed Query")

            query = build_pico_query(
                population=population,
                intervention=intervention if intervention else None,
                outcome=outcome if outcome else None,
                comparaison=comparaison if comparaison else None
            )

            st.code(query, language="text")
            st.link_button("🔗 Search on PubMed", f"https://pubmed.ncbi.nlm.nih.gov/?term={query}")

st.divider()
st.subheader("📝 Quick Feedback")
st.write("Before you go — 30 seconds to help us improve.")

rating = st.slider("How useful was this tool?", min_value=1, max_value=5, value=3)

comment = st.text_area(
    "What was missing or confusing?",
    placeholder="Ex: I didn't understand what Level 2 meant...",
    height=100
)

if st.button("Send Feedback"):
    save_feedback(
        level=level,
        population=population,
        intervention=intervention or "",
        outcome=outcome or "",
        comparaison=comparaison or "",
        rating=rating,
        comment=comment
    )
    st.success("✅ Thank you! Your feedback helps us improve.")