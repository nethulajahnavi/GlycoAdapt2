"""Actionable general food/lifestyle education; never a prescribed care plan."""


def build_recommendations(risk: dict, diabetes_type: str | None = None) -> dict:
    level = risk.get("overall_level", "in_range")
    if level in {"critical_low", "low"}:
        items = [
            {"priority": "high", "title": "Review the low-glucose category", "detail": "The latest value submitted for this prediction is in the low range. If it represents an actual measurement, follow the hypoglycemia plan provided by your diabetes team. This app does not specify a treatment dose."},
            {"priority": "high", "title": "Pause driving and hazardous activity", "detail": "Do not drive or operate machinery while low or symptomatic. Resume only when safe and consistent with your clinician's advice."},
            {"priority": "medium", "title": "Keep recommended supplies accessible", "detail": "Keep the measured fast-acting carbohydrate and emergency supplies recommended by your clinician available."},
            {"priority": "medium", "title": "Review the pattern with your care team", "detail": "Repeated lows, overnight lows or reduced warning symptoms should be discussed with your diabetes team."},
        ]
    elif level in {"high", "very_high"}:
        items = [
            {"priority": "high", "title": "Review the elevated-glucose category", "detail": "The latest value submitted for this prediction is above the broad reference band. If it represents an actual measurement, follow the written plan from your clinician. Do not take extra medication based on this app."},
            {"priority": "high" if level == "very_high" else "medium", "title": "Know when to seek medical help", "detail": "Persistent high readings need advice from your care team. Vomiting, abdominal pain, difficult breathing, confusion or severe weakness requires urgent medical assessment."},
            {"priority": "medium", "title": "Choose water or unsweetened drinks", "detail": "If you have no fluid restriction, water can be a sensible drink choice. Follow any fluid limits from your clinician."},
            {"priority": "medium", "title": "Build a balanced next meal", "detail": "Consider non-starchy vegetables, a protein such as dal, chana, eggs, fish, tofu or curd, and a carbohydrate portion that fits your personal meal plan."},
            {"priority": "low", "title": "Review recent patterns", "detail": "Record meals, activity, illness and repeated readings to discuss patterns with your diabetes team."},
        ]
    else:
        items = [
            {"priority": "medium", "title": "Build balanced meals", "detail": "Include non-starchy vegetables, protein such as dal, beans, eggs, fish, tofu or curd, and a carbohydrate portion suited to your plan."},
            {"priority": "medium", "title": "Choose fibre-rich foods regularly", "detail": "Vegetables, pulses, beans, nuts and whole grains can add fibre where suitable. Adjust portions to your individual needs."},
            {"priority": "low", "title": "Prefer unsweetened drinks", "detail": "Water or unsweetened drinks can be useful everyday choices. Avoid extreme food restrictions."},
            {"priority": "low", "title": "Track patterns, not just one number", "detail": "Note recurring readings alongside meals, activity, sleep and illness; discuss persistent patterns with your care team."},
        ]
    if diabetes_type == "type_1":
        items.append({"priority": "medium", "title": "Use your Type 1 carbohydrate/insulin plan", "detail": "Carbohydrate counting and insulin timing are individual. Follow only the method taught by your diabetes team; this app never calculates insulin."})
        context = "Type 1 context: general education only; no insulin or carbohydrate dose is prescribed."
    elif diabetes_type == "type_2":
        items.append({"priority": "medium", "title": "Adapt portions to your Type 2 care plan", "detail": "Meal portions and timing can interact with medicines and activity. Ask a registered dietitian to adapt familiar foods to your plan."})
        context = "Type 2 context: general education only; no medicine or meal prescription is made."
    else:
        context = "General diabetes education only; not an individualized meal or treatment plan."
    return {"items": items, "context": context, "safety": "Do not start, stop or change insulin, medicines, or carbohydrate treatment based on these suggestions. Seek emergency help for severe symptoms; in India call 112."}
