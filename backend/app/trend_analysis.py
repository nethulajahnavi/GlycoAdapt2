"""Explain recent and forecast glucose direction without claiming certainty."""


def analyze_trend(readings: list[float], six_step: float, twelve_step: float) -> dict:
    recent = [float(value) for value in readings[-6:]]
    if len(recent) >= 2:
        change = recent[-1] - recent[0]
        if change >= 15:
            direction = "rising"
            description = "Recent readings show an upward movement."
        elif change <= -15:
            direction = "falling"
            description = "Recent readings show a downward movement."
        else:
            direction = "stable"
            description = "Recent readings are relatively stable."
    else:
        change = 0.0
        direction = "insufficient_data"
        description = "Add more readings to estimate a recent direction."

    future_change = float(twelve_step) - float(six_step)
    if future_change >= 15:
        forecast_direction = "rising"
    elif future_change <= -15:
        forecast_direction = "falling"
    else:
        forecast_direction = "stable"

    return {
        "recent_direction": direction,
        "recent_change_mg_dl": round(change, 2),
        "recent_description": description,
        "forecast_direction": forecast_direction,
        "forecast_change_mg_dl": round(future_change, 2),
        "forecast_description": f"The later model output is {abs(future_change):.1f} mg/dL {'higher than' if future_change > 0 else 'lower than' if future_change < 0 else 'the same as'} the earlier output.",
        "note": "Trend labels are simple descriptive summaries of the supplied readings and model outputs, not validated alarms."
    }
