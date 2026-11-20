# GLYCOADAPT / GlucoRAG — corrected implementation

A local academic prototype combining the supplied PyTorch glucose forecasting checkpoint with transparent glucose screening, detailed offline diabetes education, action-oriented alerts, general recommendations and an OpenStreetMap healthcare-facility finder.

> **Medical safety:** This is not a medical device and has not been clinically validated. Predictions and threshold alerts are experimental/educational only. They must not be used for diagnosis, insulin dosing, medication changes or emergency triage. Confirm real glucose values and follow the care plan from your diabetes team. In India, call **112** for emergencies.

## What's improved in this version

8. **Patient glucose trend analytics:** Per-review averages, minimum/maximum, standard deviation and direction are calculated from submitted readings. A longitudinal daily-average chart aggregates unique timestamps across saved SQLite prediction records.
9. **Explainable AI:** One-at-a-time occlusion sensitivity replaces each of the last eight submitted readings with the sequence median and measures the change in both model outputs. It is explicitly presented as model sensitivity, not clinical causation.
10. **Prediction uncertainty transparency:** The UI displays deterministic input-sensitivity scenarios after shifting all submitted inputs by ±5 mg/dL. These are not statistical confidence intervals; calibrated uncertainty is marked unavailable.
11. **Downloadable PDF report:** Each saved prediction has a PDF report with submitted readings, latest measured value and screening label, separate model outputs, trend statistics, alerts, recommendations and a safety notice.
12. **Professional interface polish:** Refined spacing, visual hierarchy, responsive analytics cards, clearer forecast explanations, consistent cards and accessible keyboard focus states.

1. **Detailed patient support assistant:** The offline knowledge base now gives topic-specific explanations for low/high glucose, Type 1/Type 2 diabetes, food, activity, CGM lag/trend arrows, hydration, sick-day planning and model forecast interpretation. It works without an API key. An optional OpenAI-compatible provider can be configured only on the backend.
2. **OpenStreetMap finder:** The backend tries multiple public Overpass servers instead of depending on one endpoint. The UI shows the map centered on the selected location even before results load, allows manual latitude/longitude if browser geolocation is blocked, shows facility distances and offers OSM and Google Maps links. OSM coverage and uptime are not guaranteed.
3. **Risk graph:** The prediction API returns chart data for every measured input and both model outputs. The frontend plots measured values and forecast outputs with 70 and 180 mg/dL reference lines.
4. **Specific alerts and patient review:** The headline glucose-risk category is calculated from the latest value submitted by the user. The two model forecasts receive separate risk categories and alerts; they are never presented as measured values or live alerts.
5. **Actionable recommendations:** Suggestions now have priority levels and are based on the highest screening category, while remaining non-prescriptive.
6. **Frontend/backend connection:** Vite proxies `/api` requests to `127.0.0.1:8000` by default, removing the need to hardcode a browser-side backend URL for local development. FastAPI CORS also permits local development origins.
7. **Windows startup scripts:** `run_backend.ps1` and `run_frontend.ps1` start the two services from the extracted project root.

## Project structure

```text
GLYCOADAPT-main/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── model.py
│   │   ├── risk_analysis.py
│   │   ├── trend_analysis.py
│   │   ├── recommendations.py
│   │   ├── chatbot.py
│   │   └── hospitals.py
│   ├── model/glucorag_transformer_multidataset.pth
│   ├── tests/test_support_features.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/App.jsx
│   ├── src/index.css
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
├── run_backend.ps1
├── run_frontend.ps1
└── README.md
```

## Requirements

- Python 3.11 or newer (use a Python version supported by the PyTorch wheel for your Windows setup).
- Node.js 20.19+ or 22.12+ and npm.
- Internet access to install dependencies and to query OpenStreetMap. The model and offline chatbot run locally after installation.

## Run on Windows PowerShell

Extract the ZIP. Open PowerShell in the extracted `GLYCOADAPT-main` folder. If script execution is blocked, run this once in each terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Terminal 1 — backend

```powershell
.\run_backend.ps1
```

Wait until Uvicorn reports that it is running. Verify these URLs:

- API health: http://127.0.0.1:8000/api/health
- Interactive API docs: http://127.0.0.1:8000/docs

Health should return `status: healthy` and `model_loaded: true`.

### Terminal 2 — frontend

Open a second PowerShell window in the same extracted project folder:

```powershell
.\run_frontend.ps1
```

Open the Vite address printed in the terminal (normally http://127.0.0.1:5173).

**Keep both terminals running.** Backend and frontend are separate processes. Do not open the frontend by double-clicking `index.html`.

### Manual startup (if preferred)

Backend terminal: run `./run_backend.ps1` from the project root. This creates and uses a dedicated environment under `%LOCALAPPDATA%\GLYCOADAPT\backend-venv` to avoid OneDrive file-locking issues.

Frontend terminal:

```powershell
cd frontend
npm install
npm run dev
```

The Vite proxy sends `/api` calls to `http://127.0.0.1:8000`. If the backend is on another machine, create `frontend/.env` with `VITE_API_URL=http://BACKEND_HOST:8000`, then restart Vite and configure backend CORS for that frontend origin.

## Optional generative chatbot

The assistant already gives detailed offline answers. For generated answers, copy `backend/.env.example` to `backend/.env` and configure a compatible provider:

```env
GLUCORAG_CHAT_API_KEY=your_provider_key
GLUCORAG_CHAT_MODEL=your_provider_model
GLUCORAG_CHAT_BASE_URL=https://api.openai.com/v1
```

Keep the key in `backend/.env` only. Never place it in frontend environment variables or commit it. Without these settings, the offline knowledge base is used.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API identity |
| GET | `/api/health` | Backend/model health |
| GET | `/api/model-info` | Model configuration and limitations |
| POST | `/api/predict` | Forecast, risk screening, graph data, alerts, trends, recommendations and optional meal-response analysis |
| POST | `/api/recommendations` | General suggestions for a supplied risk object |
| POST | `/api/chat` | Detailed offline/optional generated patient education |
| GET | `/api/hospitals?lat=...&lon=...&radius=10000` | Nearby OpenStreetMap healthcare facilities |

## Tests

From `backend/` after installing dependencies:

```powershell
pip install -r requirements-dev.txt
pytest -q
```

The backend support tests cover threshold boundaries, worst-risk selection, trend direction, recommendations, urgent chatbot routing, topic-specific chatbot detail, alert source labels, prediction integration hospital result sorting, analytics aggregation and PDF report generation.

## Important model and data limitations

- The supplied Transformer architecture and checkpoint are preserved. The checkpoint uses glucose-only input; age, gender and diabetes type are context fields and do not change the model output.
- The API accepts 1–24 readings. The architecture has a 24-position input embedding; the original training setup should be verified before interpreting shorter sequences clinically.
- Output heads are labelled 6-step and 12-step. Their clock-time meaning is not guaranteed unless the exact training sampling interval and target definition are verified.
- Risk bands (below 54, 54–69, 70–180, 181–249, 250+ mg/dL) are broad educational thresholds, not individualized targets. The main patient risk label applies only to the latest submitted reading; forecast risks are shown separately.
- The prototype does not connect to a live CGM stream and does not check real-time glucose. It analyses timestamped readings manually submitted for each prediction run.
- Forecast values are model outputs and can be wrong. The app does not independently validate sensor readings.
- OpenStreetMap facility data may be incomplete or stale. Distance is straight-line distance, not road travel time. A listed facility is not guaranteed to be open or provide emergency care; call to confirm.
- Prediction inputs and full prediction outputs are saved in a local SQLite database at `backend/data/glucorag_history.db`. The dashboard reloads saved history after refresh/restart, and selecting a history row reopens that complete review. The database is created automatically on backend startup. Set `GLUCORAG_DB_PATH` to choose a different persistent database path.
- This is local prototype storage only: there are no patient accounts, authentication, encryption, access controls, backups, or multi-user separation. Anyone with access to the backend computer and database file may be able to read its contents. Do not store identifiable patient information or treat it as a clinical record.


## New advanced feature notes

- The longitudinal trend chart is built only from timestamped readings included in saved prediction requests. Repeated timestamps are deduplicated. It does not imply a live CGM connection.
- Explainability uses occlusion sensitivity on up to the last eight inputs. The score reports how much the model output changes when a reading is replaced by the input-sequence median. It is not a causal explanation.
- Sensitivity ranges are scenario analyses under a stated ±5 mg/dL perturbation of all inputs. They are not confidence intervals, calibrated uncertainty bounds, or probabilities.
- PDF reports are generated locally by the backend using ReportLab. Install backend requirements after updating this ZIP.


## Meal tracking behaviour

- Meal details are optional and are entered on the same screen as historical CGM readings.
- The meal record (type, food name, date/time and optional quantity) is stored inside the saved prediction request, so it is available when history is reopened and is included in the downloadable PDF.
- The before-meal match is the nearest submitted measured reading from 0–60 minutes before the meal. The after-meal match is the nearest submitted measured reading from 60–180 minutes after the meal.
- If either match is missing, the review says so instead of estimating a value. The observed change is after-meal measured glucose minus before-meal measured glucose.
- This is a descriptive association only; it does not prove the meal caused the change and is not clinical advice. Meal details are not passed to the existing Transformer checkpoint.

- **Optional meal tracking:** Meal details are entered alongside CGM readings, stored with the existing SQLite prediction history, shown in the review and included in the PDF report. The analysis uses only actual submitted readings and does not alter the Transformer forecast.
