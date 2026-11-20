"""Detailed, safety-bounded diabetes education assistant.

Works offline with a topic-specific knowledge base. An optional OpenAI-compatible
provider can be enabled by backend environment variables; no secrets are exposed
in the browser. This is education, not clinical decision support.
"""
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

URGENT_TERMS = (
    "unconscious", "seizure", "can't breathe", "cannot breathe", "difficulty breathing",
    "chest pain", "severe confusion", "not responding", "fainted", "blue lips",
)

SYSTEM_GUIDANCE = """You are GlucoRAG's diabetes patient-education assistant. Answer the user's actual
question with a structured, detailed, plain-language explanation. Use short headings and
practical examples where useful. Explain uncertainty and distinguish general education from
individual care. Never diagnose, prescribe, recommend medication changes, calculate insulin
doses, or override a clinician's plan. Do not infer that model predictions are clinically valid.
For severe symptoms (unconsciousness, seizure, difficulty breathing, chest pain, severe
confusion), advise emergency help immediately; India emergency number 112. For low/high
readings, tell the user to confirm according to their usual monitoring method and follow their
own clinician-provided action plan. Do not claim to monitor the patient in real time."""

KNOWLEDGE = {
    "diabetes_basics": ("Understanding diabetes", "Diabetes is a long-term condition in which glucose regulation is affected. Glucose is a major energy source; insulin helps move glucose from the blood into cells. When insulin is absent or does not work effectively, blood glucose can rise. Diabetes includes Type 1, Type 2 and gestational diabetes, which have different causes and care needs.", "A diagnosis and treatment plan require a qualified healthcare professional and appropriate laboratory/clinical assessment. Regular follow-up, glucose monitoring when advised, food, activity and prescribed treatment can all be part of care. This chatbot cannot diagnose diabetes."),
    "symptoms": ("Common symptoms and signs of diabetes", "Possible symptoms of high glucose include increased thirst, frequent urination, increased hunger, tiredness, blurred vision, slow-healing cuts and unexplained weight change. Some people, particularly with Type 2 diabetes, may have few or no obvious symptoms for a long time. Symptoms alone cannot confirm diabetes.", "If you notice persistent symptoms, arrange a medical assessment and ask whether glucose or HbA1c testing is appropriate. Severe vomiting, difficult breathing, confusion or marked drowsiness needs urgent medical assessment. Do not use this app to self-diagnose."),
    "type_comparison": ("Type 1 and Type 2 diabetes: key differences", "Type 1 is usually an autoimmune condition that damages insulin-producing beta cells; insulin replacement is essential. Type 2 commonly involves insulin resistance and may also involve reduced insulin production over time. Both can cause high glucose and both need individualized ongoing care. Neither type is a personal failure, and people of different ages can develop either type.", "A clinician determines the diabetes type using medical history and appropriate tests. Type 1 requires insulin; Type 2 treatment may include lifestyle support and prescribed medicines, and some people need insulin. Never start, stop or change insulin or medicines based on chatbot advice."),
    "hba1c": ("Understanding HbA1c", "HbA1c is a blood test that reflects average glucose exposure over roughly the previous two to three months. It is different from a single finger-stick or CGM reading, which shows glucose at a particular time. Some conditions affecting red blood cells, pregnancy and certain medical factors can affect how HbA1c is interpreted.", "Ask your clinician what HbA1c target is appropriate for you and how often to test. The result should be interpreted with your health history and other glucose information; this app cannot diagnose or set your target."),
    "low_glucose": ("Low blood glucose (hypoglycemia)", "A glucose value below 70 mg/dL is commonly treated as a low alert; below 54 mg/dL is a more serious low range. Possible symptoms include shaking, sweating, sudden hunger, palpitations, dizziness, headache, irritability and difficulty concentrating. Some people have few warning symptoms.", "If this is a real current reading, confirm it as instructed in your care plan and follow the low-glucose treatment steps your diabetes team gave you. Recheck at the interval they specified. Keep the supplies recommended by your clinician available. Do not drive or operate machinery while low or symptomatic. Severe confusion, seizure or unconsciousness is an emergency: call 112 in India. This app cannot choose a treatment amount for you."),
    "high_glucose": ("High blood glucose (hyperglycemia)", "A value above 180 mg/dL is above a commonly used reference target, although personal targets differ. Symptoms can include increased thirst, frequent urination, tiredness, blurred vision and headache; symptoms may be absent.", "Confirm a concerning real reading using your usual meter/CGM instructions. Follow your personal high-glucose plan and contact your diabetes team if readings remain high or you feel unwell. Use ketone testing only if it is part of your clinician-provided plan. Vomiting, abdominal pain, deep or difficult breathing, marked drowsiness or confusion need urgent medical assessment. Never change insulin or medicines based on this chatbot."),
    "nutrition": ("Building a balanced diabetes-friendly meal", "A practical plate pattern is: about half non-starchy vegetables, one quarter protein, and one quarter carbohydrate foods. Examples include leafy vegetables, beans, gourds or cauliflower; dal, chana, eggs, fish, tofu or curd; and a measured portion of rice, roti, millet or another staple. Fibre-rich pulses, vegetables and whole grains can slow digestion. Whole fruit is generally preferable to juice because it retains fibre.", "Portion size and carbohydrate needs depend on medicines, activity, diabetes type, culture and individual targets. Pairing carbohydrate with protein/fibre may make a meal more balanced, but it does not guarantee a particular glucose response. Avoid extreme restriction. A registered dietitian can adapt portions to your needs. People using insulin should follow their own carbohydrate-counting plan."),
    "activity": ("Physical activity and glucose", "Muscle activity can increase glucose use and may improve insulin sensitivity. Walking, cycling, swimming, strength exercises and daily movement can all contribute. Glucose responses vary: activity may lower glucose during or after exercise, while intense activity can sometimes raise it temporarily.", "Follow your clinician's advice about activity, especially if you use insulin or medicines that can cause hypoglycemia, have complications, or are unwell. Use your prescribed glucose-checking plan around exercise and keep the supplies your care team recommends nearby. Stop and seek help for chest pain, fainting or severe breathlessness. This app cannot clear you for exercise."),
    "type_1": ("Type 1 diabetes", "Type 1 diabetes is an autoimmune condition in which the body's insulin-producing beta cells are damaged. People with Type 1 diabetes need insulin replacement. Glucose monitoring, food, activity, illness and insulin all interact, and needs vary throughout the day.", "Never stop basal insulin or change insulin doses based on an app or chatbot. Work with your diabetes team on insulin timing, carbohydrate counting, low-glucose treatment, sick-day rules and ketone testing. If you are ill or have persistent high glucose, use the sick-day instructions provided by your team."),
    "type_2": ("Type 2 diabetes", "Type 2 diabetes commonly involves insulin resistance and, over time, the pancreas may not make enough insulin to meet the body's needs. Management can include food choices, physical activity, glucose monitoring and prescribed medicines; some people also use insulin.", "Treatment is individual and may change over time. Do not stop or adjust medicines based on this app. Discuss glucose patterns, side effects, meal planning and activity goals with your clinician. A dietitian can help adapt familiar foods and portions rather than requiring a restrictive diet."),
    "cgm": ("Understanding CGM readings", "A continuous glucose monitor measures glucose in interstitial fluid, not directly in blood. Its value can lag behind blood glucose when levels are changing quickly. Trend arrows and repeated patterns can add context beyond one number.", "Follow the device instructions for symptoms that do not match the sensor value, unexpected readings, sensor errors and confirmatory finger-stick checks. Review time-in-range and recurring patterns with your care team. Do not make treatment decisions from this prototype's forecast."),
    "prediction": ("How to read this GlucoRAG forecast", "The supplied model returns two numeric forecast outputs from the glucose readings entered. They are model estimates, not measurements. The output labels (6-step and 12-step) describe output positions; they must not be interpreted as minutes unless the dataset sampling interval and target definition are verified.", "The model and risk rules in this academic prototype are not clinically validated. Forecasts can be wrong, especially with missing, irregular or unusual readings. Compare with your actual CGM/meter, follow your clinician's plan, and never change medication or insulin based on this result."),
    "sick_day": ("Diabetes and illness (sick-day planning)", "Illness, fever, infection, vomiting, reduced food intake and dehydration can change glucose and medication needs. The direction and size of change vary by person and illness.", "Ask your diabetes team for written sick-day instructions before you become ill. Follow their directions for monitoring, fluids, medicines and ketone checks. Do not stop or change medicines or insulin using chatbot advice. Seek urgent care for repeated vomiting, inability to keep fluids down, difficulty breathing, confusion or severe weakness."),
    "hydration": ("Hydration", "Water is a useful everyday drink. High glucose can increase urination and fluid loss, so thirst and frequent urination deserve attention, particularly when readings remain high.", "Follow any fluid restrictions given for heart, kidney or other conditions. Persistent high glucose, dehydration symptoms or feeling unwell should be discussed with your care team. Vomiting, difficulty breathing or confusion require urgent assessment."),
}


def _offline_answer(message: str, context: dict | None = None) -> dict:
    q = (message or "").strip().lower()
    if not q:
        return {"reply": "Please type a diabetes or glucose-related question.", "topic": "general", "assistant_type": "offline_knowledge_base"}
    if any(term in q for term in URGENT_TERMS):
        return {"reply": "PLEASE GET EMERGENCY HELP NOW\nThe symptoms you described may be serious. Call 112 in India or go to the nearest emergency department now. Ask someone nearby to stay with the person. Do not wait for this app, a prediction or a map search. I cannot assess an emergency through chat.", "topic": "urgent_safety", "assistant_type": "offline_safety_response"}

    # Specific question patterns are checked before broad topic words.
    if ("type 1" in q or "type-1" in q) and ("type 2" in q or "type-2" in q):
        key = "type_comparison"
    elif any(x in q for x in ("hba1c", "a1c", "glycated hemoglobin", "glycated haemoglobin")):
        key = "hba1c"
    elif any(x in q for x in ("symptom", "signs of diabetes", "signs diabetes", "thirsty", "frequent urination")):
        key = "symptoms"
    elif any(x in q for x in ("what is diabetes", "explain diabetes", "meaning of diabetes", "diabetes basics")):
        key = "diabetes_basics"
    elif any(x in q for x in ("sick day", "sick-day", "fever", "vomit", "illness", "when i am sick")):
        key = "sick_day"
    elif any(x in q for x in ("cgm", "sensor", "continuous glucose", "trend arrow", "interstitial")):
        key = "cgm"
    elif any(x in q for x in ("type 1", "type-1", "t1d", "t1 diabetes")):
        key = "type_1"
    elif any(x in q for x in ("type 2", "type-2", "t2d", "t2 diabetes")):
        key = "type_2"
    elif any(x in q for x in ("low", "hypo", "shaky", "sweat", "trembl", "below 70")):
        key = "low_glucose"
    elif any(x in q for x in ("high", "hyper", "thirst", "urinate", "250", "above 180")):
        key = "high_glucose"
    elif any(x in q for x in ("food", "eat", "diet", "meal", "fruit", "rice", "breakfast", "lunch", "dinner", "snack", "carb")):
        key = "nutrition"
    elif any(x in q for x in ("exercise", "walk", "workout", "activity", "gym")):
        key = "activity"
    elif any(x in q for x in ("water", "hydration", "drink", "dehydrat")):
        key = "hydration"
    elif any(x in q for x in ("predict", "forecast", "model", "result", "reading", "risk graph")):
        key = "prediction"
    else:
        return {"reply": "I can explain low and high glucose, CGM readings, Type 1 and Type 2 diabetes, food choices, exercise, sick-day planning and how this prototype's forecast works.\n\nTry asking a specific question, such as: 'What should I understand about a glucose reading of 210?', 'How do CGM trend arrows work?' or 'What makes a balanced Indian meal?' I cannot diagnose or recommend medicine or insulin doses.", "topic": "general", "assistant_type": "offline_knowledge_base"}

    title, explanation, guidance = KNOWLEDGE[key]
    parts = [title.upper(), explanation, f"What you can do: {guidance}"]
    if context:
        current = context.get("latest_glucose")
        risk = context.get("risk")
        if current is not None or risk:
            parts.append("Your app context: The latest entered value in this session is " + (f"{current} mg/dL" if current is not None else "not available") + (f"; the prototype's screening label is {risk}." if risk else ".") + " This is not a diagnosis; confirm real readings and follow your own care plan.")
    return {"reply": "\n\n".join(parts), "topic": key, "assistant_type": "offline_knowledge_base", "follow_up": "Would you like an explanation of symptoms, common causes, food examples, or what to discuss with your diabetes team?"}


def answer_question(message: str, context: dict | None = None) -> dict:
    text = (message or "").strip()
    if not text or any(term in text.lower() for term in URGENT_TERMS):
        return _offline_answer(text, context)
    api_key = os.getenv("GLUCORAG_CHAT_API_KEY", "").strip()
    model = os.getenv("GLUCORAG_CHAT_MODEL", "").strip()
    base_url = os.getenv("GLUCORAG_CHAT_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if not api_key or not model:
        return _offline_answer(text, context)
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "system", "content": SYSTEM_GUIDANCE}, {"role": "user", "content": text}], "temperature": 0.25},
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, str) and content.strip():
            return {"reply": content.strip(), "topic": "llm_education", "assistant_type": "configured_language_model"}
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        pass
    result = _offline_answer(text, context)
    result["provider_notice"] = "The optional language-model provider was unavailable; a detailed offline answer was used."
    return result
