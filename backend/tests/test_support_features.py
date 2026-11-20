"""Small deterministic tests for GlucoRAG's supporting feature modules."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chatbot import answer_question
from app.recommendations import build_recommendations
from app.risk_analysis import assess_predictions, classify_glucose
from app.trend_analysis import analyze_trend


def test_glucose_risk_boundaries():
    assert classify_glucose(53.9)["level"] == "critical_low"
    assert classify_glucose(69.9)["level"] == "low"
    assert classify_glucose(70)["level"] == "in_range"
    assert classify_glucose(180)["level"] == "in_range"
    assert classify_glucose(181)["level"] == "high"
    assert classify_glucose(250)["level"] == "very_high"


def test_headline_risk_uses_latest_submitted_value_and_forecast_is_separate():
    result = assess_predictions(110, 68, 130)
    assert result["overall_level"] == "in_range"
    assert result["overall_label"] == "Within common reference range"
    assert result["forecast_level"] == "low"
    assert result["assessments"]["six_step"]["level"] == "low"


def test_trend_analysis_direction():
    result = analyze_trend([100, 105, 112, 120], 125, 145)
    assert result["recent_direction"] == "rising"
    assert result["forecast_direction"] == "rising"


def test_recommendations_are_non_prescriptive():
    risk = assess_predictions(100, 260, 240)
    result = build_recommendations(risk, "type_2")
    assert result["items"]
    assert "Do not start" in result["safety"]


def test_chatbot_urgent_routing():
    result = answer_question("My family member is unconscious")
    assert result["topic"] == "urgent_safety"
    assert "112" in result["reply"]


def test_prediction_api_integrates_existing_model_and_support_features():
    from datetime import datetime, timedelta
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    start = datetime(2026, 11, 17, 10, 0)
    values = [110, 112, 115, 117, 120, 122, 119, 118, 116, 115, 114, 112,
              110, 108, 106, 104, 102, 101, 100, 98, 99, 100, 102, 105]
    readings = [
        {"timestamp": (start + timedelta(minutes=5 * index)).isoformat(), "glucose": value}
        for index, value in enumerate(values)
    ]
    response = client.post("/api/predict", json={"readings": readings})
    assert response.status_code == 200
    body = response.json()
    assert "six_step" in body["predictions"]
    assert "risk_analysis" in body
    assert "trend_analysis" in body
    assert len(body["chart_data"]) == len(readings) + 2
    assert "alerts" in body
    assert body["recommendations"]["items"]
    assert body["patient_analytics"]["count"] == len(readings)
    assert body["explainability"]["top_influential_readings"]
    assert body["prediction_uncertainty"]["calibrated_confidence_interval_available"] is False
    assert body["history_id"]
    saved_list = client.get("/api/history")
    assert saved_list.status_code == 200
    assert any(item["id"] == body["history_id"] for item in saved_list.json()["items"])
    saved_detail = client.get(f"/api/history/{body['history_id']}")
    assert saved_detail.status_code == 200
    assert saved_detail.json()["result"]["latest_glucose"] == body["latest_glucose"]
    analytics = client.get("/api/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["count"] >= len(readings)


def test_hospital_lookup_parses_and_sorts_nearest_first(monkeypatch):
    import asyncio
    from app import hospitals as hospital_module

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "elements": [
                    {"type": "node", "id": 2, "lat": 17.41, "lon": 78.51,
                     "tags": {"name": "Far Clinic", "amenity": "clinic"}},
                    {"type": "node", "id": 1, "lat": 17.40, "lon": 78.50,
                     "tags": {"name": "Nearby Hospital", "amenity": "hospital"}},
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(hospital_module.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(hospital_module.find_nearby_hospitals(17.40, 78.50))
    assert result["status"] == "success"
    assert result["hospitals"][0]["name"] == "Nearby Hospital"
    assert result["hospitals"][0]["distance_km"] == 0


def test_chatbot_returns_topic_specific_detail():
    low = answer_question("What should I know about low glucose?")
    assert low["topic"] == "low_glucose"
    assert "below 70 mg/dL" in low["reply"]
    assert "hypoglycemia" in low["reply"].lower() and "follow" in low["reply"].lower()


def test_alerts_distinguish_measured_and_forecast_values():
    from app.risk_analysis import build_alerts
    risk = assess_predictions(62, 205, 268)
    alerts = build_alerts(risk)
    assert len(alerts) == 3
    assert alerts[0]["source"] == "Measured value"
    assert alerts[1]["source"] == "Experimental forecast"
    assert alerts[2]["value_mg_dl"] == 268
    assert "must not trigger medication" in alerts[1]["recommendation"].lower()


def test_chatbot_compares_type_one_and_type_two():
    result = answer_question("What is the difference between Type 1 and Type 2 diabetes?")
    assert result["topic"] == "type_comparison"
    assert "autoimmune" in result["reply"]
    assert "insulin resistance" in result["reply"]


def test_prediction_history_is_persisted_and_retrievable(tmp_path, monkeypatch):
    from app import database
    monkeypatch.setenv("GLUCORAG_DB_PATH", str(tmp_path / "history.db"))
    database.initialize_database()
    request_data = {"readings": [{"timestamp": "2026-11-18T10:00:00", "glucose": 184.4}]}
    response_data = {
        "latest_glucose": 184.4,
        "risk_analysis": {"overall_label": "Elevated glucose"},
        "predictions": {
            "six_step": {"glucose_mg_dl": 150.37},
            "twelve_step": {"glucose_mg_dl": 150.17},
        },
    }
    saved = database.save_prediction(request_data, response_data)
    assert saved["id"] == 1
    assert database.list_predictions()[0]["latest_glucose"] == 184.4
    detail = database.get_prediction(saved["id"])
    assert detail["request"] == request_data
    assert detail["result"] == response_data



def test_pdf_report_endpoint_for_saved_prediction():
    from datetime import datetime, timedelta
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    start = datetime(2026, 11, 17, 10, 0)
    readings = [{"timestamp": (start + timedelta(minutes=5*i)).isoformat(), "glucose": 100 + i} for i in range(6)]
    response = client.post("/api/predict", json={"readings": readings})
    assert response.status_code == 200
    record_id = response.json()["history_id"]
    report = client.get(f"/api/history/{record_id}/report.pdf")
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content.startswith(b"%PDF")


def test_legacy_history_record_is_enriched_with_explainability():
    from datetime import datetime, timedelta
    from app.main import enrich_saved_record

    start = datetime(2026, 11, 18, 10, 0)
    readings = [
        {"timestamp": (start + timedelta(minutes=5 * i)).isoformat(), "glucose": 100 + i * 3}
        for i in range(6)
    ]
    record = {
        "id": 77,
        "created_at": start.isoformat(),
        "request": {"readings": readings},
        "result": {
            "latest_glucose": 115,
            "input_readings": 6,
            "predictions": {
                "six_step": {"glucose_mg_dl": 130.0},
                "twelve_step": {"glucose_mg_dl": 135.0},
            },
        },
    }
    enriched = enrich_saved_record(record)
    assert enriched["result"]["explainability"]["top_influential_readings"]
    assert enriched["result"]["patient_analytics"]["count"] == 6
    assert enriched["result"]["prediction_uncertainty"]["six_step_scenario_range"]


def test_meal_tracking_uses_measured_readings_before_and_after_meal():
    from datetime import datetime, timedelta
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    start = datetime(2026, 11, 18, 12, 5)
    meal_time = datetime(2026, 11, 18, 13, 0)
    readings = []
    for index in range(24):
        stamp = start + timedelta(minutes=5 * index)
        value = 115 if stamp < meal_time else 165
        readings.append({"timestamp": stamp.isoformat(), "glucose": value})

    response = client.post("/api/predict", json={
        "readings": readings,
        "meal": {
            "meal_type": "lunch",
            "food_name": "rice and dal",
            "meal_datetime": meal_time.isoformat(),
            "quantity": "1 bowl",
        },
    })
    assert response.status_code == 200
    analysis = response.json()["meal_response_analysis"]
    assert analysis["status"] == "complete"
    assert analysis["before_meal"]["glucose_mg_dl"] == 115
    assert analysis["after_meal"]["glucose_mg_dl"] == 165
    assert analysis["observed_change_mg_dl"] == 50

    detail = client.get(f"/api/history/{response.json()['history_id']}")
    assert detail.status_code == 200
    assert detail.json()["request"]["meal"]["food_name"] == "rice and dal"
