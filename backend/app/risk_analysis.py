"""Transparent threshold-based glucose screening for research/education only."""


def classify_glucose(value: float) -> dict:
    value = float(value)
    if value < 54:
        level, label, severity = "critical_low", "Very low glucose", "critical"
        message = "Below 54 mg/dL: a clinically important low-glucose range."
        guidance = "If this is a real current value, confirm as directed and follow your personal hypoglycemia action plan. Severe confusion, seizure or unconsciousness requires emergency help (112 in India)."
    elif value < 70:
        level, label, severity = "low", "Low glucose", "high"
        message = "Below 70 mg/dL: low-glucose alert range."
        guidance = "Confirm the real reading as appropriate and follow your clinician-provided low-glucose plan. Avoid driving while low or symptomatic."
    elif value <= 180:
        level, label, severity = "in_range", "Within common reference range", "normal"
        message = "70–180 mg/dL: within a commonly used reference range; personal targets may differ."
        guidance = "Continue your individual monitoring and care plan. A single value does not guarantee future values will remain in range."
    elif value < 250:
        level, label, severity = "high", "Elevated glucose", "moderate"
        message = "181–249 mg/dL: above the commonly used reference range."
        guidance = "Confirm the reading and follow your personal high-glucose plan. Consider meal, activity or illness context with your care team. Do not change medication based on this app."
    else:
        level, label, severity = "very_high", "Very high glucose", "high"
        message = "250 mg/dL or higher: high-glucose alert range requiring attention."
        guidance = "Confirm the reading and follow your clinician-provided high-glucose/ketone plan if applicable. Seek urgent medical advice for persistent high readings or feeling unwell. Vomiting, difficult breathing or confusion requires emergency care."
    return {"level": level, "label": label, "severity": severity, "value": round(value, 2), "message": message, "guidance": guidance}


def assess_predictions(latest: float, six_step: float, twelve_step: float) -> dict:
    """Separate submitted-reading screening from experimental forecast screening."""
    assessments = {
        "current_reading": classify_glucose(latest),
        "six_step": classify_glucose(six_step),
        "twelve_step": classify_glucose(twelve_step),
    }
    order = {"normal": 0, "moderate": 1, "high": 2, "critical": 3}
    latest_assessment = assessments["current_reading"]
    forecast_assessments = [assessments["six_step"], assessments["twelve_step"]]
    forecast_worst = max(forecast_assessments, key=lambda item: order[item["severity"]])
    return {
        # The headline risk is based ONLY on the latest value supplied by the user.
        "overall_level": latest_assessment["level"],
        "overall_label": latest_assessment["label"],
        "overall_severity": latest_assessment["severity"],
        "latest_submitted_reading": latest_assessment,
        "forecast_level": forecast_worst["level"],
        "forecast_label": forecast_worst["label"],
        "forecast_severity": forecast_worst["severity"],
        "assessments": assessments,
        "thresholds_mg_dl": {"very_low_below": 54, "low_below": 70, "reference_range": [70, 180], "elevated_above": 180, "very_high_from": 250},
        "disclaimer": "Educational screening only. The latest submitted value is not a live sensor reading. Forecast outputs are experimental and are not validated clinical alarms or treatment instructions."
    }


def build_alerts(risk: dict) -> list[dict]:
    """Create explicit alerts per measured/forecast value; forecasts are labelled."""
    labels = {"current_reading": "Latest measured reading", "six_step": "First model forecast", "twelve_step": "Second model forecast"}
    alerts = []
    for key, assessment in risk.get("assessments", {}).items():
        level = assessment.get("level")
        if level == "in_range":
            continue
        is_current = key == "current_reading"
        source = "Measured value" if is_current else "Experimental forecast"
        if is_current:
            if level == "critical_low":
                action = "LATEST SUBMITTED VALUE IS VERY LOW. This is the value entered for this prediction run, not a live sensor alert. If it represents an actual measurement, follow the low-glucose plan provided by your healthcare professional. Severe symptoms require emergency help (112 in India)."
                recommendation = "This app does not monitor you continuously or prescribe treatment. Do not drive if you are actually low or symptomatic."
            elif level == "low":
                action = "LATEST SUBMITTED VALUE IS LOW. This is a screening of the value you entered, not a live reading. If it represents an actual measurement, follow your personal hypoglycemia plan."
                recommendation = "Discuss repeated low values with your diabetes care team. This app does not provide treatment doses."
            elif level == "very_high":
                action = "LATEST SUBMITTED VALUE IS VERY HIGH. This is the value entered for this prediction run, not a live alert. If it represents an actual measurement, follow your clinician-provided high-glucose plan."
                recommendation = "Persistent high values or feeling unwell warrant medical advice. Vomiting, difficult breathing or confusion requires emergency assessment."
            else:
                action = "LATEST SUBMITTED VALUE IS ELEVATED. This is a screening of the value you entered, not a live reading."
                recommendation = "Review recurring patterns with your care team. Do not change medication based on this prototype."
        else:
            action = f"MODEL FORECAST FLAG: the {labels.get(key, 'forecast')} falls in the {assessment.get('label', 'flagged')} category. This is an experimental prediction, not a measured glucose value or real-time alert."
            recommendation = "Use this forecast only as an educational indication of a possible trend. It must not trigger medication, insulin or emergency decisions."
        alerts.append({"id": key, "source": source, "title": f"{labels.get(key, key)}: {assessment.get('label')}", "level": level, "severity": assessment.get("severity"), "value_mg_dl": assessment.get("value"), "message": assessment.get("message"), "action": action, "recommendation": recommendation})
    return alerts
