"""FastAPI entry point for GlucoRAG.

The existing Transformer checkpoint remains the prediction backbone. Supporting
features are separate, readable modules so they can be maintained independently.
"""

from datetime import datetime
from io import BytesIO
import math
from typing import List, Optional

import torch
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.chatbot import answer_question
from app.database import initialize_database, save_prediction, list_predictions, get_prediction
from app.hospitals import find_nearby_hospitals
from app.model import load_glucorag_model
from app.recommendations import build_recommendations
from app.risk_analysis import assess_predictions, build_alerts
from app.trend_analysis import analyze_trend

model, device = load_glucorag_model()
initialize_database()


def _run_model(values):
    tensor = torch.tensor(values, dtype=torch.float32).reshape(1, len(values), 1).to(device)
    with torch.no_grad():
        p6, p12 = model(tensor)
    return float(p6.item()), float(p12.item())


def explain_prediction(values, base6, base12):
    """Occlusion sensitivity: replace one input at a time with the sequence median."""
    baseline = float(sorted(values)[len(values) // 2])
    impacts = []
    start_index = max(0, len(values) - 8)
    for index in range(start_index, len(values)):
        original = values[index]
        altered = list(values)
        altered[index] = baseline
        try:
            alt6, alt12 = _run_model(altered)
            impacts.append({
                "reading_index": index + 1,
                "glucose_mg_dl": round(float(original), 2),
                "timestamp_position": f"Reading {index + 1}",
                "six_step_change_mg_dl": round(base6 - alt6, 3),
                "twelve_step_change_mg_dl": round(base12 - alt12, 3),
                "influence_magnitude": round((abs(base6 - alt6) + abs(base12 - alt12)) / 2, 3),
            })
        except Exception:
            continue
    impacts.sort(key=lambda item: item["influence_magnitude"], reverse=True)
    return {
        "method": "One-at-a-time occlusion sensitivity",
        "description": "Each submitted reading is replaced with the sequence median and the model is run again. The output change indicates model sensitivity, not causation.",
        "top_influential_readings": impacts[:5],
        "caveat": "Influence scores are model sensitivity explanations, not clinical causes or proof of feature importance.",
    }


def build_input_sensitivity(values):
    """Scenario analysis under a stated +/-5 mg/dL perturbation of every input."""
    low_values = [max(1.0, value - 5.0) for value in values]
    high_values = [value + 5.0 for value in values]
    low6, low12 = _run_model(low_values)
    high6, high12 = _run_model(high_values)
    return {
        "method": "Deterministic input perturbation scenario",
        "assumption": "All submitted inputs are shifted together by -5 or +5 mg/dL.",
        "six_step_scenario_range": {"low": round(min(low6, high6), 2), "high": round(max(low6, high6), 2)},
        "twelve_step_scenario_range": {"low": round(min(low12, high12), 2), "high": round(max(low12, high12), 2)},
        "calibrated_confidence_interval_available": False,
        "interpretation": "These are sensitivity scenarios, NOT statistical confidence or prediction intervals. The model has no calibrated uncertainty estimate.",
    }


def build_meal_response_analysis(meal, readings):
    """Compare submitted measured CGM values around a recorded meal.

    A pre-meal match must be within 60 minutes before the meal. A post-meal
    match must be 60 to 180 minutes after it. This is descriptive matching,
    not a causal or clinical assessment.
    """
    if meal is None:
        return None
    meal_time = meal.meal_datetime
    before_candidates = []
    after_candidates = []
    for reading in readings:
        stamp = reading.timestamp
        # Browser datetime-local values and the entered meal time are both naive.
        # If an offset-aware timestamp is supplied, normalize both to naive UTC.
        if stamp.tzinfo is not None and meal_time.tzinfo is None:
            stamp = stamp.astimezone().replace(tzinfo=None)
        elif meal_time.tzinfo is not None and stamp.tzinfo is None:
            meal_stamp = meal_time.astimezone().replace(tzinfo=None)
            meal_time = meal_stamp
        delta_minutes = (stamp - meal_time).total_seconds() / 60
        if -60 <= delta_minutes < 0:
            before_candidates.append((abs(delta_minutes), reading))
        elif 60 <= delta_minutes <= 180:
            after_candidates.append((delta_minutes, reading))

    before = min(before_candidates, key=lambda item: item[0])[1] if before_candidates else None
    after = min(after_candidates, key=lambda item: item[0])[1] if after_candidates else None
    result = {
        "meal": meal.model_dump(mode="json", exclude_none=True),
        "before_meal": None,
        "after_meal": None,
        "observed_change_mg_dl": None,
        "status": "insufficient_data",
        "matching_rule": "Nearest submitted measured reading within 60 minutes before the meal and nearest submitted measured reading 60–180 minutes after the meal.",
        "note": "This is an observed difference between entered readings. It does not prove the meal caused the change and is not medical advice.",
    }
    if before:
        result["before_meal"] = {
            "timestamp": before.timestamp.isoformat(),
            "glucose_mg_dl": round(float(before.glucose), 2),
            "minutes_from_meal": round((before.timestamp - meal_time).total_seconds() / 60, 1),
        }
    if after:
        result["after_meal"] = {
            "timestamp": after.timestamp.isoformat(),
            "glucose_mg_dl": round(float(after.glucose), 2),
            "minutes_from_meal": round((after.timestamp - meal_time).total_seconds() / 60, 1),
        }
    if before and after:
        result["observed_change_mg_dl"] = round(float(after.glucose) - float(before.glucose), 2)
        result["status"] = "complete"
    elif before:
        result["status"] = "missing_post_meal_reading"
    elif after:
        result["status"] = "missing_pre_meal_reading"
    return result


def build_reading_analytics(readings):
    ordered = sorted(readings, key=lambda row: row["timestamp"])
    vals = [float(row["glucose"]) for row in ordered]
    if not vals:
        return {"count": 0, "message": "No submitted readings available."}
    mean = sum(vals) / len(vals)
    variance = sum((x - mean) ** 2 for x in vals) / len(vals)
    changes = [vals[i] - vals[i-1] for i in range(1, len(vals))]
    return {
        "count": len(vals), "average_mg_dl": round(mean, 2),
        "minimum_mg_dl": round(min(vals), 2), "maximum_mg_dl": round(max(vals), 2),
        "standard_deviation_mg_dl": round(variance ** 0.5, 2),
        "net_change_mg_dl": round(vals[-1] - vals[0], 2),
        "direction": "rising" if len(vals) > 1 and vals[-1] > vals[0] else "falling" if len(vals) > 1 and vals[-1] < vals[0] else "stable",
        "points": [{"timestamp": row["timestamp"].isoformat() if isinstance(row["timestamp"], datetime) else str(row["timestamp"]), "glucose": round(float(row["glucose"]), 2)} for row in ordered],
        "note": "Descriptive statistics of submitted readings only; not continuous monitoring or a clinical interpretation.",
    }

app = FastAPI(
    title="GlucoRAG API",
    description="Transformer glucose forecasting with educational risk screening and patient-support tools.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GlucoseReading(BaseModel):
    timestamp: datetime
    glucose: float = Field(gt=0, le=1000)


class StaticFeatures(BaseModel):
    age: Optional[int] = Field(default=None, ge=1, le=120)
    gender: Optional[str] = None
    diabetes_type: Optional[str] = None


class MealEntry(BaseModel):
    meal_type: str = Field(min_length=1, max_length=30)
    food_name: str = Field(min_length=1, max_length=200)
    meal_datetime: datetime
    quantity: Optional[str] = Field(default=None, max_length=100)


class PredictionRequest(BaseModel):
    readings: List[GlucoseReading]
    static_features: Optional[StaticFeatures] = None
    meal: Optional[MealEntry] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    context: Optional[dict] = None


class RecommendationRequest(BaseModel):
    risk: dict
    diabetes_type: Optional[str] = None


@app.get("/")
def root():
    return {"name": "GlucoRAG API", "version": "2.0.0", "docs": "/docs"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "model_loaded": model is not None, "device": str(device)}


@app.get("/api/model-info")
def model_info():
    return {
        "model_name": "GlucoRAG Transformer",
        "input_readings": 24,
        "input_features": 1,
        "d_model": 128,
        "attention_heads": 4,
        "transformer_layers": 3,
        "prediction_heads": ["6-step ahead", "12-step ahead"],
        "device": str(device),
        "note": "Demographic form fields are collected as context but are not model input features in this checkpoint.",
    }


@app.post("/api/predict")
def predict(request: PredictionRequest):
    if not 1 <= len(request.readings) <= 24:
        raise HTTPException(status_code=400, detail="Enter between 1 and 24 glucose readings.")

    readings = sorted(request.readings, key=lambda item: item.timestamp)
    timestamps = [item.timestamp for item in readings]
    if len(set(timestamps)) != len(timestamps):
        raise HTTPException(status_code=400, detail="Duplicate timestamps are not allowed.")

    intervals = [(timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps))]
    first_interval = intervals[0] if intervals else None
    if first_interval is not None and first_interval <= 0:
        raise HTTPException(status_code=400, detail="Timestamps must be in chronological order.")
    if first_interval is not None and any(abs(value - first_interval) > 60 for value in intervals):
        raise HTTPException(status_code=400, detail="Readings must have consistent measurement intervals.")

    glucose_values = [float(item.glucose) for item in readings]
    input_tensor = torch.tensor(glucose_values, dtype=torch.float32).reshape(1, len(glucose_values), 1).to(device)
    try:
        with torch.no_grad():
            prediction_6, prediction_12 = model(input_tensor)
        value_6 = float(prediction_6.item())
        value_12 = float(prediction_12.item())
        if not math.isfinite(value_6) or not math.isfinite(value_12):
            raise ValueError("The model returned a non-finite prediction.")
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {error}") from error

    explainability = explain_prediction(glucose_values, value_6, value_12)
    uncertainty = build_input_sensitivity(glucose_values)
    analytics = build_reading_analytics([{"timestamp": item.timestamp, "glucose": item.glucose} for item in readings])
    meal_analysis = build_meal_response_analysis(request.meal, readings)
    risk = assess_predictions(glucose_values[-1], value_6, value_12)
    trend = analyze_trend(glucose_values, value_6, value_12)
    diabetes_type = request.static_features.diabetes_type if request.static_features else None
    recommendations = build_recommendations(risk, diabetes_type)
    alerts = build_alerts(risk)

    response_data = {
        "status": "success",
        "input_readings": len(readings),
        "last_reading_timestamp": timestamps[-1].isoformat(),
        "measurement_interval_minutes": round(first_interval / 60, 2) if first_interval is not None else None,
        "latest_glucose": glucose_values[-1],
        "chart_data": [
            {"label": item.timestamp.strftime("%H:%M"), "timestamp": item.timestamp.isoformat(), "measured": round(float(item.glucose), 2), "predicted": None}
            for item in readings
        ] + [
            {"label": "First forecast", "timestamp": None, "measured": None, "predicted": round(value_6, 2)},
            {"label": "Second forecast", "timestamp": None, "measured": None, "predicted": round(value_12, 2)},
        ],
        "predictions": {
            "six_step": {"label": "6-step ahead prediction", "glucose_mg_dl": round(value_6, 2)},
            "twelve_step": {"label": "12-step ahead prediction", "glucose_mg_dl": round(value_12, 2)},
        },
        "risk_analysis": risk,
        "trend_analysis": trend,
        "patient_analytics": analytics,
        "meal_response_analysis": meal_analysis,
        "explainability": explainability,
        "prediction_uncertainty": uncertainty,
        "recommendations": recommendations,
        "alerts": alerts,
        "patient_context": request.static_features.model_dump(exclude_none=True) if request.static_features else {},
        "notice": "Research prototype. Predictions are experimental and are not validated for clinical decisions. Output steps are not guaranteed clock-time horizons.",
    }
    saved = save_prediction(request.model_dump(mode="json", exclude_none=True), response_data)
    response_data["history_id"] = saved["id"]
    response_data["saved_at"] = saved["created_at"]
    return response_data


@app.get("/api/history")
def prediction_history(limit: int = Query(100, ge=1, le=500)):
    """Return saved prediction summaries from the local SQLite database."""
    items = list_predictions(limit)
    return {"items": items, "count": len(items)}


def enrich_saved_record(record):
    """Backfill advanced insights for prediction records saved by older app versions."""
    result = record.get("result", {})
    saved_request = record.get("request", {})
    readings = saved_request.get("readings", [])
    values = [float(item["glucose"]) for item in readings if item.get("glucose") is not None]
    predictions = result.get("predictions", {})
    six = predictions.get("six_step", {}).get("glucose_mg_dl")
    twelve = predictions.get("twelve_step", {}).get("glucose_mg_dl")

    if values and six is not None and twelve is not None:
        if not result.get("explainability"):
            result["explainability"] = explain_prediction(values, float(six), float(twelve))
        if not result.get("prediction_uncertainty"):
            result["prediction_uncertainty"] = build_input_sensitivity(values)
        if not result.get("patient_analytics"):
            parsed = []
            for item in readings:
                try:
                    stamp = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00"))
                except (KeyError, TypeError, ValueError):
                    stamp = str(item.get("timestamp", ""))
                parsed.append({"timestamp": stamp, "glucose": float(item["glucose"])})
            result["patient_analytics"] = build_reading_analytics(parsed)
    record["result"] = result
    return record


@app.get("/api/history/{record_id}")
def prediction_history_detail(record_id: int):
    record = get_prediction(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Saved prediction was not found.")
    return enrich_saved_record(record)


@app.get("/api/analytics")
def saved_glucose_analytics(limit: int = Query(500, ge=1, le=500)):
    """Aggregate submitted glucose readings across persistent prediction history."""
    unique = {}
    for summary in list_predictions(limit):
        record = get_prediction(summary["id"])
        if not record:
            continue
        for reading in record.get("request", {}).get("readings", []):
            stamp = reading.get("timestamp")
            if stamp:
                unique[stamp] = float(reading.get("glucose", 0))
    points = sorted(unique.items(), key=lambda item: item[0])
    if not points:
        return {"count": 0, "daily": [], "message": "No saved submitted readings yet."}
    from collections import defaultdict
    buckets = defaultdict(list)
    for stamp, value in points:
        try:
            day = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            day = str(stamp)[:10]
        buckets[day].append(value)
    values = [value for _, value in points]
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    daily = [{"date": day, "average": round(sum(vals)/len(vals), 2), "minimum": round(min(vals), 2),
              "maximum": round(max(vals), 2), "count": len(vals)} for day, vals in sorted(buckets.items())]
    return {"count": len(values), "average_mg_dl": round(mean, 2), "minimum_mg_dl": round(min(values), 2),
            "maximum_mg_dl": round(max(values), 2), "standard_deviation_mg_dl": round(variance ** 0.5, 2),
            "daily": daily, "note": "Aggregated from unique timestamps in saved submissions; repeat timestamps are deduplicated. This is not a live feed."}


@app.get("/api/history/{record_id}/report.pdf")
def download_patient_report(record_id: int):
    record = get_prediction(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Saved prediction was not found.")
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError as error:
        raise HTTPException(status_code=503, detail="PDF export dependency is missing. Install backend requirements and restart.") from error
    record = enrich_saved_record(record)
    result = record["result"]
    from xml.sax.saxutils import escape as xml_escape
    safe = lambda value: xml_escape(str(value if value is not None else "—"))
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallNote", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#64748b")))
    story = [
        Paragraph("GlucoRAG | Patient Glucose Review", styles["Title"]),
        Paragraph(f"Saved review: {safe(record['created_at'])}", styles["SmallNote"]), Spacer(1, 8*mm),
        Paragraph("Submitted glucose review", styles["Heading2"]),
    ]
    risk = result.get("risk_analysis", {})
    story.append(Paragraph(f"Latest submitted glucose: <b>{safe(result.get('latest_glucose', '—'))} mg/dL</b> · Screening category: <b>{safe(risk.get('overall_label', 'Not available'))}</b>", styles["BodyText"]))
    story.append(Paragraph(f"Submitted readings: {safe(result.get('input_readings', 0))} · Last reading timestamp: {safe(result.get('last_reading_timestamp', 'Not available'))}", styles["BodyText"]))
    story += [Spacer(1, 4*mm), Paragraph("Experimental model outputs", styles["Heading2"])]
    preds = result.get("predictions", {})
    story.append(Paragraph(f"First output (6-step): {safe(preds.get('six_step', {}).get('glucose_mg_dl', '—'))} mg/dL<br/>Second output (12-step): {safe(preds.get('twelve_step', {}).get('glucose_mg_dl', '—'))} mg/dL", styles["BodyText"]))
    story += [Spacer(1, 4*mm), Paragraph("Submitted reading details", styles["Heading2"])]
    table_data = [["Timestamp", "Glucose (mg/dL)"]]
    for row in record.get("request", {}).get("readings", []):
        table_data.append([safe(row.get("timestamp", "")), safe(row.get("glucose", ""))])
    table = Table(table_data, repeatRows=1, colWidths=[105*mm, 45*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e7f3f1")),("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#164e55")),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#dbe5e7")),("PADDING",(0,0),(-1,-1),6),("FONTSIZE",(0,0),(-1,-1),8)]))
    story += [table, Spacer(1, 5*mm)]
    meal_analysis = result.get("meal_response_analysis")
    if meal_analysis:
        meal = meal_analysis.get("meal", {})
        story.append(Paragraph("Meal tracking and observed glucose response", styles["Heading2"]))
        story.append(Paragraph(f"Meal: {safe(meal.get('meal_type'))} · {safe(meal.get('food_name'))} · Time: {safe(meal.get('meal_datetime'))}", styles["BodyText"]))
        before = meal_analysis.get("before_meal") or {}
        after = meal_analysis.get("after_meal") or {}
        story.append(Paragraph(f"Before meal: {safe(before.get('glucose_mg_dl', 'No matching reading'))} mg/dL · After meal: {safe(after.get('glucose_mg_dl', 'No matching reading'))} mg/dL · Observed change: {safe(meal_analysis.get('observed_change_mg_dl', 'Not available'))} mg/dL", styles["BodyText"]))
        story.append(Paragraph(safe(meal_analysis.get("note")), styles["SmallNote"]))
        story += [Spacer(1, 5*mm)]
    story.append(Paragraph("Trend analytics", styles["Heading2"]))
    analytics = result.get("patient_analytics", {})
    story.append(Paragraph(f"Average: {safe(analytics.get('average_mg_dl', '—'))} mg/dL · Minimum: {safe(analytics.get('minimum_mg_dl', '—'))} mg/dL · Maximum: {safe(analytics.get('maximum_mg_dl', '—'))} mg/dL · Standard deviation: {safe(analytics.get('standard_deviation_mg_dl', '—'))} mg/dL", styles["BodyText"]))
    story += [Spacer(1, 4*mm), Paragraph("Explainable AI - input sensitivity", styles["Heading2"])]
    explanation = result.get("explainability", {})
    story.append(Paragraph(safe(explanation.get("description", "No explanation available for this saved record.")), styles["BodyText"]))
    for item in explanation.get("top_influential_readings", []):
        story.append(Paragraph(f"Reading {safe(item.get('reading_index'))} ({safe(item.get('glucose_mg_dl'))} mg/dL): {safe(item.get('influence_magnitude'))} mg/dL sensitivity", styles["BodyText"]))
    if explanation.get("caveat"):
        story.append(Paragraph(safe(explanation["caveat"]), styles["SmallNote"]))
    story += [Spacer(1, 4*mm), Paragraph("Alerts and recommendations", styles["Heading2"])]
    for alert in result.get("alerts", []):
        story.append(Paragraph(f"<b>{safe(alert.get('title', 'Alert'))}</b> ({safe(alert.get('source', ''))}): {safe(alert.get('message', ''))}", styles["BodyText"]))
        story.append(Spacer(1, 2*mm))
    for item in result.get("recommendations", {}).get("items", []):
        story.append(Paragraph(f"- <b>{safe(item.get('title', ''))}</b>: {safe(item.get('detail', ''))}", styles["BodyText"]))
    story += [Spacer(1, 6*mm), Paragraph("Research prototype only. Forecasts are experimental, not clinically validated. Scenario ranges are not confidence intervals. This report is not for diagnosis, medication changes, insulin dosing or emergency decisions.", styles["SmallNote"])]
    try:
        doc.build(story)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not generate PDF report: {error}") from error
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="glucorag-patient-review-{record_id}.pdf"' })


@app.post("/api/recommendations")
def recommendations(request: RecommendationRequest):
    return build_recommendations(request.risk, request.diabetes_type)


@app.post("/api/chat")
def chat(request: ChatRequest):
    return answer_question(request.message, request.context)


@app.get("/api/hospitals")
async def nearby_hospitals(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(10000, ge=1000, le=30000),
):
    return await find_nearby_hospitals(lat, lon, radius)
