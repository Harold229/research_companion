import streamlit as st 
import streamlit as st

st.title("Research Companion")
st.subheader("🔬 Build your research question using the PICO framework")
st.divider()

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

    # Validation
    if level == "Level 1" and not population:
        st.warning("⚠️ Please fill in at least Population.")
    elif level == "Level 2" and not (population and outcome):
        st.warning("⚠️ Level 2 requires Population and Outcome.")
    elif level == "Level 3" and not (population and intervention and outcome):
        st.warning("⚠️ Level 3 requires Population, Intervention and Outcome.")

    else:
        # Construction de la question
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