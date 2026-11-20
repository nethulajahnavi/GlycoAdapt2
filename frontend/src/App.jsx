import { useEffect, useState } from "react";
import {
  Activity, LayoutDashboard, ClipboardList, TrendingUp, MessageCircle,
  MapPinned, Info, Plus, Trash2, ArrowRight, Clock, ShieldCheck,
  AlertTriangle, CheckCircle2, Menu, X, HeartPulse, Utensils, Send,
  MapPin, Phone, ExternalLink, RefreshCw, Bot, Sparkles, ChevronRight, Download
} from "lucide-react";
import {
  ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, LineChart, Line
} from "recharts";
import "./index.css";

// Use Vite proxy by default; set VITE_API_URL only when frontend/backend are on different hosts.
const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "entry", label: "New prediction", icon: ClipboardList },
  { id: "forecast", label: "Glucose insights", icon: TrendingUp },
  { id: "assistant", label: "Patient assistant", icon: MessageCircle },
  { id: "hospitals", label: "Hospital finder", icon: MapPinned },
  { id: "about", label: "About GlucoRAG", icon: Info },
];

function localDateTime(date) {
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function newReading(timestamp = localDateTime(new Date())) {
  return { id: crypto.randomUUID(), timestamp, glucose: "" };
}
function makeReadings(count = 6, interval = 5) {
  const now = new Date();
  return Array.from({ length: count }, (_, index) => {
    const time = new Date(now.getTime() - (count - index - 1) * interval * 60000);
    return newReading(localDateTime(time));
  });
}
function severityClass(severity) {
  if (severity === "critical" || severity === "high") return "danger";
  if (severity === "moderate") return "warning";
  return "success";
}
function riskIcon(severity) {
  if (severity === "critical" || severity === "high") return AlertTriangle;
  if (severity === "moderate") return AlertTriangle;
  return CheckCircle2;
}

function App() {
  const [page, setPage] = useState("overview");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [readings, setReadings] = useState(() => makeReadings(6, 5));
  const [interval, setInterval] = useState("5");
  const [patient, setPatient] = useState({ age: "", gender: "", diabetes_type: "" });
  const [meal, setMeal] = useState({ enabled: false, meal_type: "breakfast", food_name: "", meal_datetime: localDateTime(new Date()), quantity: "" });
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [savedAnalytics, setSavedAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState("");
  const [apiStatus, setApiStatus] = useState("checking");
  const [chatMessages, setChatMessages] = useState([
    { role: "assistant", text: "Hello! I'm the GlucoRAG Patient Support Assistant. I can explain general diabetes topics, glucose readings, food choices and activity. I cannot diagnose or recommend medicine or insulin doses. How can I help?" },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [location, setLocation] = useState(null);
  const [locationError, setLocationError] = useState("");
  const [hospitals, setHospitals] = useState([]);
  const [hospitalNotice, setHospitalNotice] = useState("");
  const [hospitalLoading, setHospitalLoading] = useState(false);
  const [selectedHospital, setSelectedHospital] = useState(null);
  const [manualLat, setManualLat] = useState("");
  const [manualLon, setManualLon] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/health`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => setApiStatus(data.model_loaded ? "online" : "model unavailable"))
      .catch(() => setApiStatus("offline"));

    fetch(`${API_URL}/api/analytics?limit=500`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => setSavedAnalytics(data))
      .catch(() => {});
    // Restore saved prediction history and the most recent review after refresh/restart.
    fetch(`${API_URL}/api/history?limit=100`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then(async (data) => {
        const items = (data.items || []).map((item) => ({
          id: item.id,
          time: new Date(item.created_at).toLocaleString(),
          latest: item.latest_glucose,
          six: item.six_step,
          twelve: item.twelve_step,
          risk: item.risk_label,
        }));
        setHistory(items);
        if (items.length) {
          const detailResponse = await fetch(`${API_URL}/api/history/${items[0].id}`);
          if (detailResponse.ok) {
            const detail = await detailResponse.json();
            setResult({ ...detail.result, history_id: detail.id, saved_at: detail.created_at });
          }
        }
      })
      .catch(() => {});
  }, []);

  const navigate = (nextPage) => {
    setPage(nextPage);
    setMobileMenu(false);
    setError("");
  };

  const updateReading = (id, field, value) => {
    setReadings((current) => current.map((item) => item.id === id ? { ...item, [field]: value } : item));
  };
  const addReading = () => {
    if (readings.length >= 24) return;
    const last = readings[readings.length - 1];
    const next = last?.timestamp ? new Date(new Date(last.timestamp).getTime() + Number(interval) * 60000) : new Date();
    setReadings((current) => [...current, newReading(localDateTime(next))]);
  };
  const removeReading = (id) => {
    if (readings.length > 1) setReadings((current) => current.filter((item) => item.id !== id));
  };

  const submitPrediction = async (event) => {
    event.preventDefault();
    setError("");
    const complete = readings.every((item) => item.timestamp && item.glucose !== "");
    if (!complete) return setError("Please provide a timestamp and glucose value for every reading.");
    if (readings.some((item) => !Number.isFinite(Number(item.glucose)) || Number(item.glucose) <= 0 || Number(item.glucose) > 1000)) {
      return setError("Glucose values must be greater than 0 and no more than 1000 mg/dL.");
    }
    if (patient.age && (!Number.isInteger(Number(patient.age)) || Number(patient.age) < 1 || Number(patient.age) > 120)) {
      return setError("Age must be a whole number between 1 and 120.");
    }
    setLoading(true);
    try {
      const payload = {
        readings: readings.map((item) => ({ timestamp: item.timestamp, glucose: Number(item.glucose) })),
        static_features: {
          ...(patient.age ? { age: Number(patient.age) } : {}),
          ...(patient.gender ? { gender: patient.gender } : {}),
          ...(patient.diabetes_type ? { diabetes_type: patient.diabetes_type } : {}),
        },
        ...(meal.enabled ? { meal: {
          meal_type: meal.meal_type,
          food_name: meal.food_name.trim(),
          meal_datetime: meal.meal_datetime,
          ...(meal.quantity.trim() ? { quantity: meal.quantity.trim() } : {}),
        } } : {}),
      };
      if (meal.enabled && (!meal.food_name.trim() || !meal.meal_datetime)) {
        setLoading(false);
        return setError("Enter the food name and meal date/time, or turn off meal tracking.");
      }
      const response = await fetch(`${API_URL}/api/predict`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Prediction request failed (HTTP ${response.status}).`);
      setResult(data);
      fetch(`${API_URL}/api/analytics?limit=500`).then((response) => response.ok ? response.json() : Promise.reject()).then(setSavedAnalytics).catch(() => {});
      setHistory((current) => [{ id: data.history_id, time: new Date(data.saved_at || Date.now()).toLocaleString(), latest: data.latest_glucose, six: data.predictions.six_step.glucose_mg_dl, twelve: data.predictions.twelve_step.glucose_mg_dl, risk: data.risk_analysis.overall_label }, ...current.filter((item) => item.id !== data.history_id)]);
      navigate("forecast");
    } catch (requestError) {
      setError(requestError.message === "Failed to fetch" ? "Cannot reach the backend. Start the FastAPI server and try again." : requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async () => {
    if (!result?.history_id || reportLoading) return;
    setReportLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/history/${result.history_id}/report.pdf`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `PDF download failed (HTTP ${response.status}).`);
      }
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/pdf")) {
        throw new Error(`The server returned ${contentType || "an unexpected response"}, not a PDF. Restart the updated backend and try again.`);
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error("The server returned an empty PDF file.");
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `glucorag-patient-review-${result.history_id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (downloadError) {
      setError(downloadError.message === "Failed to fetch" ? "Could not reach the PDF endpoint. Confirm that the updated FastAPI backend is running on port 8000." : downloadError.message);
    } finally {
      setReportLoading(false);
    }
  };

  const sendChat = async (event, suggestedText) => {
    event?.preventDefault();
    const message = (suggestedText ?? chatInput).trim();
    if (!message || chatLoading) return;
    setChatMessages((current) => [...current, { role: "user", text: message }]);
    setChatInput("");
    setChatLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, context: result ? { latest_glucose: result.latest_glucose, risk: result.risk_analysis?.overall_label } : {} }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Assistant request failed (HTTP ${response.status}).`);
      setChatMessages((current) => [...current, { role: "assistant", text: data.reply || "The support service returned an empty response." }]);
    } catch (chatError) {
      setChatMessages((current) => [...current, { role: "assistant", text: `I could not reach the support service: ${chatError.message}. Check the backend health status and try again.` }]);
    } finally {
      setChatLoading(false);
    }
  };

  const requestLocation = () => {
    setLocationError("");
    if (!navigator.geolocation) return setLocationError("Your browser does not support location access. You can still search by entering coordinates in your device's map app.");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocation({ lat: position.coords.latitude, lon: position.coords.longitude });
        setLocationError("");
      },
      (geoError) => setLocationError(geoError.code === 1 ? "Location permission was denied. Allow location access in your browser to find nearby facilities." : "Could not determine your location. Check device location settings and try again."),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
    );
  };

  const useManualLocation = () => {
    const lat = Number(manualLat);
    const lon = Number(manualLon);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) {
      setLocationError("Enter a valid latitude (-90 to 90) and longitude (-180 to 180).");
      return;
    }
    setLocation({ lat, lon });
    setLocationError("");
    setHospitals([]);
    setSelectedHospital(null);
    setHospitalNotice("Location set manually. Select Find nearby hospitals to search OpenStreetMap.");
  };

  const searchHospitals = async () => {
    if (!location) return;
    setHospitalLoading(true);
    setHospitalNotice("");
    try {
      const response = await fetch(`${API_URL}/api/hospitals?lat=${location.lat}&lon=${location.lon}&radius=10000`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Hospital search failed (HTTP ${response.status}).`);
      setHospitals(data.hospitals || []);
      setHospitalNotice(data.notice || data.message || (data.count ? `${data.count} facilities found.` : "No facilities found in this area."));
      setSelectedHospital(data.hospitals?.[0] || null);
    } catch (requestError) {
      setHospitalNotice(requestError.message || "Could not retrieve nearby hospitals.");
    } finally {
      setHospitalLoading(false);
    }
  };

  const latestRisk = result?.risk_analysis;
  const navTitle = navigation.find((item) => item.id === page)?.label || "Overview";

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Activity size={23} /></div>
          <div><div className="brand-name">GlucoRAG</div><div className="brand-caption">GLUCOSE INTELLIGENCE</div></div>
          <button className="mobile-close" onClick={() => setMobileMenu(false)} aria-label="Close menu"><X size={19} /></button>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${page === id ? "active" : ""}`} onClick={() => navigate(id)}>
              <Icon size={18} /><span>{label}</span>{page === id && <span className="nav-indicator" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-status"><span className={`status-dot ${apiStatus !== "online" ? "status-muted" : ""}`} /> API {apiStatus}</div>
          <p>Academic research prototype for glucose forecasting and patient education.</p>
          <div className="sidebar-version">GLUCORAG · VERSION 2.0</div>
        </div>
      </aside>
      {mobileMenu && <button className="mobile-overlay" onClick={() => setMobileMenu(false)} aria-label="Close navigation" />}

      <main className="main-content">
        <header className="topbar">
          <button className="mobile-menu-button" onClick={() => setMobileMenu(true)} aria-label="Open menu"><Menu size={20} /></button>
          <div className="breadcrumb">Workspace <span>/</span> <strong>{navTitle}</strong></div>
          <div className="topbar-right"><div className="prototype-pill"><span /> Research prototype</div><div className="user-avatar">G</div></div>
        </header>

        <div className="page-container">
          {page === "overview" && (
            <>
              <section className="welcome-card">
                <div className="welcome-copy">
                  <div className="welcome-tag"><Sparkles size={14} /> TRANSFORMER-POWERED GLUCOSE INSIGHTS</div>
                  <h1>Understand your glucose trends with more context.</h1>
                  <p>Enter historical CGM readings, generate experimental glucose forecasts, and see a clearly labelled glucose-risk review based on the submitted values.</p>
                  <button className="welcome-button" onClick={() => navigate("entry")}>Start a prediction <ArrowRight size={16} /></button>
                </div>
                <div className="welcome-art"><div className="art-ring ring-one" /><div className="art-ring ring-two" /><div className="art-icon"><HeartPulse size={58} /></div><div className="art-label">GLUCOSE<br />MONITORING</div></div>
              </section>

              <section className="section-heading"><div><h2>Workspace overview</h2><p>Quick access to the tools in your GlucoRAG prototype.</p></div></section>
              <section className="stats-grid">
                <div className="stat-card"><div className="stat-top"><span>Saved predictions</span><TrendingUp /></div><div className="stat-value">{history.length}</div><div className="stat-foot">Stored in the local SQLite database</div></div>
                <div className="stat-card"><div className="stat-top"><span>Latest glucose</span><Activity /></div><div className="stat-value">{result ? `${result.latest_glucose} ` : "—"}<small>{result ? "mg/dL" : "No reading yet"}</small></div><div className="stat-foot">Latest value entered for this prediction</div></div>
                <div className="stat-card"><div className="stat-top"><span>Latest risk screening</span><ShieldCheck /></div><div className="stat-value">{latestRisk?.overall_label || "Not assessed"}</div><div className="stat-foot">Based on the latest value entered</div></div>
                <div className="stat-card"><div className="stat-top"><span>Support tools</span><HeartPulse /></div><div className="stat-value">3 modules</div><div className="stat-foot">Assistant, recommendations and hospitals</div></div>
              </section>

              <section className="feature-grid">
                <button className="feature-card" onClick={() => navigate("entry")}><div className="feature-icon teal"><ClipboardList /></div><div><h3>Glucose prediction</h3><p>Submit historical CGM values, view two forecasts, and see the glucose-risk category for the latest entered value.</p></div><ChevronRight /></button>
                <button className="feature-card" onClick={() => navigate("assistant")}><div className="feature-icon purple"><MessageCircle /></div><div><h3>Patient support assistant</h3><p>Ask general questions about glucose, food, activity and diabetes.</p></div><ChevronRight /></button>
                <button className="feature-card" onClick={() => navigate("hospitals")}><div className="feature-icon blue"><MapPinned /></div><div><h3>Nearby hospitals</h3><p>Use your permission-based location to look up nearby facilities.</p></div><ChevronRight /></button>
              </section>

              <div className="info-strip"><div className="info-icon"><AlertTriangle size={19} /></div><div><strong>Important medical safety notice</strong><p>GlucoRAG is an academic prototype. Its predictions and educational guidance are not clinically validated and must not be used for diagnosis, medication changes, insulin dosing, or emergency triage.</p></div></div>
              {history.length > 0 && <section className="entry-card history-card"><div className="entry-card-heading"><div><h2>Recent session activity</h2><p>Prediction records are saved locally and remain available after restarting the app.</p></div></div><HistoryList history={history} onSelect={async (id) => { try { const response = await fetch(`${API_URL}/api/history/${id}`); if (!response.ok) throw new Error("Could not load saved review."); const saved = await response.json(); setResult({ ...saved.result, history_id: saved.id, saved_at: saved.created_at }); navigate("forecast"); } catch (e) { setError(e.message); } }} /></section>}
            </>
          )}

          {page === "entry" && (
            <>
              <PageHeading eyebrow="MODEL INPUT" title="Enter glucose readings" description="Enter historical timestamped glucose values. GlucoRAG analyses these inputs; it does not monitor a live glucose sensor." />
              <form onSubmit={submitPrediction}>
                <section className="entry-card">
                  <div className="entry-card-heading"><div><h2>Historical CGM readings</h2><p>Enter 1 to 24 historical readings from your CGM or glucose log. These are manually submitted values, not a live data stream.</p></div><span className="input-count">{readings.length} / 24 readings</span></div>
                  <div className="entry-table-wrap"><table className="entry-table"><thead><tr><th>#</th><th>Date and time</th><th>Glucose value</th><th /></tr></thead><tbody>
                    {readings.map((item, index) => <tr key={item.id}><td className="row-number">{String(index + 1).padStart(2, "0")}</td><td><input className="table-input" type="datetime-local" value={item.timestamp} onChange={(event) => updateReading(item.id, "timestamp", event.target.value)} required /></td><td><div className="glucose-input-wrap"><input className="table-input glucose-input" type="number" min="1" max="1000" step="0.1" placeholder="e.g. 112" value={item.glucose} onChange={(event) => updateReading(item.id, "glucose", event.target.value)} required /><span>mg/dL</span></div></td><td><button type="button" className="remove-row" onClick={() => removeReading(item.id)} disabled={readings.length <= 1} aria-label="Remove reading"><Trash2 size={16} /></button></td></tr>)}
                  </tbody></table></div>
                  <div className="entry-actions"><button type="button" className="secondary-button" onClick={addReading} disabled={readings.length >= 24}><Plus size={16} /> Add reading</button><div className="interval-control"><label htmlFor="interval">Expected interval</label><select id="interval" value={interval} onChange={(event) => setInterval(event.target.value)}><option value="1">1 minute</option><option value="5">5 minutes</option><option value="10">10 minutes</option><option value="15">15 minutes</option><option value="30">30 minutes</option></select></div></div>
                </section>
                <section className="entry-card meal-entry-card">
                  <div className="entry-card-heading"><div><h2>Optional meal tracking</h2><p>Record a meal to compare actual submitted CGM readings before and after eating. This does not change the Transformer prediction.</p></div><label className="meal-toggle"><input type="checkbox" checked={meal.enabled} onChange={(event) => setMeal({ ...meal, enabled: event.target.checked })} /> Track a meal</label></div>
                  {meal.enabled && <div className="meal-fields">
                    <label>Meal type<select value={meal.meal_type} onChange={(event) => setMeal({ ...meal, meal_type: event.target.value })}><option value="breakfast">Breakfast</option><option value="lunch">Lunch</option><option value="dinner">Dinner</option><option value="snack">Snack</option><option value="other">Other</option></select></label>
                    <label>Food / meal name<input type="text" maxLength="200" placeholder="e.g. rice, dal and curd" value={meal.food_name} onChange={(event) => setMeal({ ...meal, food_name: event.target.value })} required={meal.enabled} /></label>
                    <label>Meal date and time<input type="datetime-local" value={meal.meal_datetime} onChange={(event) => setMeal({ ...meal, meal_datetime: event.target.value })} required={meal.enabled} /></label>
                    <label>Quantity (optional)<input type="text" maxLength="100" placeholder="e.g. 1 bowl" value={meal.quantity} onChange={(event) => setMeal({ ...meal, quantity: event.target.value })} /></label>
                    <p className="meal-help">For a complete comparison, include measured readings within 60 minutes before the meal and 1–3 hours after it. Missing matches will be shown clearly.</p>
                  </div>}
                </section>
                <section className="entry-card patient-card"><div className="entry-card-heading"><div><h2>Optional patient context</h2><p>These details are stored with the response for context; the current Transformer checkpoint does not use them as model inputs.</p></div></div><div className="patient-fields"><label>Age<input type="number" min="1" max="120" placeholder="Age in years" value={patient.age} onChange={(event) => setPatient({ ...patient, age: event.target.value })} /></label><label>Gender<select value={patient.gender} onChange={(event) => setPatient({ ...patient, gender: event.target.value })}><option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></select></label><label>Diabetes type<select value={patient.diabetes_type} onChange={(event) => setPatient({ ...patient, diabetes_type: event.target.value })}><option value="">Not specified</option><option value="type_1">Type 1</option><option value="type_2">Type 2</option><option value="other">Other / unsure</option></select></label></div></section>
                {error && <div className="error-message"><AlertTriangle size={17} />{error}</div>}
                <div className="submit-row"><p><Clock size={15} /> The backend sorts readings by timestamp and checks intervals.</p><button className="primary-button" type="submit" disabled={loading}>{loading ? "Generating forecast…" : "Generate glucose insights"}<ArrowRight size={16} /></button></div>
              </form>
            </>
          )}

          {page === "forecast" && (
            <>
              <PageHeading eyebrow="MODEL OUTPUT + EDUCATIONAL INSIGHTS" title="Glucose insights" description="See the risk category for your latest submitted glucose value, then review the two separate experimental model forecasts." action={<div className="heading-actions"><button className="secondary-button" onClick={downloadReport} disabled={!result?.history_id || reportLoading}>{reportLoading ? <RefreshCw className="spin" size={16} /> : <Download size={16} />} {reportLoading ? "Preparing PDF…" : "Download PDF"}</button><button className="secondary-button" onClick={() => navigate("entry")}><Plus size={16} /> New prediction</button></div>} />
              {!result ? <EmptyState icon={TrendingUp} title="No forecast generated yet" description="Enter timestamped glucose readings to view predictions and supporting insights." action={() => navigate("entry")} actionLabel="Enter readings" /> : <>
                <div className="result-meta"><CheckCircle2 size={17} /> Prediction generated <span>Last reading: {new Date(result.last_reading_timestamp).toLocaleString()}</span></div>
                <section className="forecast-grid"><ForecastCard label="FIRST OUTPUT" step="6-step ahead" value={result.predictions.six_step.glucose_mg_dl} /><ForecastCard label="SECOND OUTPUT" step="12-step ahead" value={result.predictions.twelve_step.glucose_mg_dl} accent /></section>
                <section className="analytics-grid">
                  <article className="analytics-card"><span>AVERAGE SUBMITTED GLUCOSE</span><strong>{result.patient_analytics?.average_mg_dl ?? "—"} <small>mg/dL</small></strong><p>Across {result.patient_analytics?.count ?? 0} readings in this review</p></article>
                  <article className="analytics-card"><span>RECORDED RANGE</span><strong>{result.patient_analytics?.minimum_mg_dl ?? "—"}–{result.patient_analytics?.maximum_mg_dl ?? "—"}</strong><p>Minimum to maximum · mg/dL</p></article>
                  <article className="analytics-card"><span>READING VARIABILITY</span><strong>{result.patient_analytics?.standard_deviation_mg_dl ?? "—"} <small>mg/dL</small></strong><p>Descriptive standard deviation</p></article>
                  <article className="analytics-card"><span>OVERALL DIRECTION</span><strong className="capitalize">{result.patient_analytics?.direction ?? "—"}</strong><p>First to latest submitted reading</p></article>
                </section>
                {result.meal_response_analysis && <section className="insight-panel meal-result-panel">
                  <div className="panel-heading"><div><div className="eyebrow">MEAL TRACKING</div><h2>Observed glucose response around this meal</h2><p>{result.meal_response_analysis.meal?.meal_type} · {result.meal_response_analysis.meal?.food_name} · {new Date(result.meal_response_analysis.meal?.meal_datetime).toLocaleString()}</p></div><Utensils size={21} /></div>
                  <div className="meal-result-grid">
                    <article><span>BEFORE MEAL</span><strong>{result.meal_response_analysis.before_meal?.glucose_mg_dl ?? "Not available"}{result.meal_response_analysis.before_meal && <small> mg/dL</small>}</strong><p>{result.meal_response_analysis.before_meal ? new Date(result.meal_response_analysis.before_meal.timestamp).toLocaleString() : "No reading within 60 minutes before meal"}</p></article>
                    <article><span>AFTER MEAL</span><strong>{result.meal_response_analysis.after_meal?.glucose_mg_dl ?? "Not available"}{result.meal_response_analysis.after_meal && <small> mg/dL</small>}</strong><p>{result.meal_response_analysis.after_meal ? new Date(result.meal_response_analysis.after_meal.timestamp).toLocaleString() : "No reading 1–3 hours after meal"}</p></article>
                    <article><span>OBSERVED CHANGE</span><strong>{result.meal_response_analysis.observed_change_mg_dl === null ? "Not available" : `${result.meal_response_analysis.observed_change_mg_dl > 0 ? "+" : ""}${result.meal_response_analysis.observed_change_mg_dl}`} {result.meal_response_analysis.observed_change_mg_dl !== null && <small>mg/dL</small>}</strong><p>{result.meal_response_analysis.status === "complete" ? "After-meal value minus before-meal value" : "Add matching readings to calculate the difference"}</p></article>
                  </div>
                  <p className="meal-result-note">{result.meal_response_analysis.note} {result.meal_response_analysis.matching_rule}</p>
                </section>}
                <section className="insight-panel patient-review-panel">
                  <div className="panel-heading"><div><div className="eyebrow">PATIENT GLUCOSE REVIEW</div><h2>Risk assessment summary</h2><p>This review uses only the glucose values entered in this prediction request. It is not connected to a live glucose sensor.</p></div><span className={`risk-badge ${severityClass(latestRisk?.overall_severity)}`}><ShieldCheck size={15} />{latestRisk?.overall_label}</span></div>
                  <div className="patient-review-grid">
                    <div className={`patient-review-primary ${severityClass(latestRisk?.overall_severity)}`}><span>RISK FROM LATEST SUBMITTED VALUE</span><strong>{result.latest_glucose} <small>mg/dL</small></strong><b>{latestRisk?.overall_label}</b><p>{latestRisk?.latest_submitted_reading?.message}</p><small>Timestamp: {new Date(result.last_reading_timestamp).toLocaleString()}</small><small>Patient context: {result.patient_context?.age ? `${result.patient_context.age} years` : "Age not provided"} · {result.patient_context?.diabetes_type?.replaceAll("_", " ") || "Diabetes type not specified"}</small></div>
                    <div className="patient-review-forecast"><span>RISK INDICATED BY MODEL OUTPUTS</span><strong>{latestRisk?.forecast_label || "Not available"}</strong><p>First forecast: {result.predictions.six_step.glucose_mg_dl} mg/dL ({latestRisk?.assessments?.six_step?.label})</p><p>Second forecast: {result.predictions.twelve_step.glucose_mg_dl} mg/dL ({latestRisk?.assessments?.twelve_step?.label})</p><small>These are experimental model outputs, not measured patient readings.</small></div>
                  </div>
                  <div className="risk-grid">{Object.entries(latestRisk?.assessments || {}).map(([key, assessment]) => <RiskCard key={key} name={key === "current_reading" ? "Latest submitted value" : key === "six_step" ? "First model forecast" : "Second model forecast"} assessment={assessment} isForecast={key !== "current_reading"} />)}</div>
                  <div className="threshold-note">Educational screening bands used: below 54 very low · 54–69 low · 70–180 within the commonly used range · 181–249 elevated · 250+ very high mg/dL. These are broad thresholds, not personalized patient targets or a diagnosis.</div>
                </section>
                <section className="insight-panel alert-panel"><div className="panel-heading"><div><div className="eyebrow">ACTIONABLE RISK NOTIFICATIONS</div><h2>Glucose alerts</h2><p>Alerts clearly separate the latest value you entered from experimental model forecasts. This app does not measure glucose in real time.</p></div><AlertTriangle size={21} /></div>
                  {result.alerts?.length ? <div className="alert-list">{result.alerts.map((alert) => <article className={`action-alert ${severityClass(alert.severity)}`} key={alert.id}><div className="action-alert-top"><strong>{alert.title}</strong><span>{alert.source} · {alert.value_mg_dl} mg/dL</span></div><p>{alert.message}</p><b>{alert.action}</b><p className="alert-recommendation">Recommendation: {alert.recommendation}</p></article>)}</div> : <div className="all-clear"><CheckCircle2 size={18} /><div><strong>All supplied and forecast values are within the screening range</strong><p>No threshold flags were produced for this prediction run. This is not continuous glucose monitoring.</p></div></div>}
                </section>
                <section className="two-column-panels">
                  <div className="insight-panel"><div className="panel-heading"><div><div className="eyebrow">DIRECTION</div><h2>Trend analysis</h2></div><span className="direction-chip">{result.trend_analysis?.recent_direction?.replaceAll("_", " ")}</span></div><p className="trend-copy">{result.trend_analysis?.recent_description}</p><div className="trend-metric"><span>Recent change (last up to 6 readings)</span><strong>{result.trend_analysis?.recent_change_mg_dl > 0 ? "+" : ""}{result.trend_analysis?.recent_change_mg_dl} mg/dL</strong></div><div className="trend-metric"><span>Difference between model outputs</span><strong>{result.trend_analysis?.forecast_change_mg_dl > 0 ? "+" : ""}{result.trend_analysis?.forecast_change_mg_dl} mg/dL</strong></div><p className="muted-small">{result.trend_analysis?.forecast_description}</p></div>
                  <div className="insight-panel"><div className="panel-heading"><div><div className="eyebrow">PATIENT EDUCATION</div><h2>Suggested next steps</h2></div><Utensils size={20} /></div><div className="recommendation-list">{result.recommendations?.items?.map((item) => <div className="recommendation-item" key={item.title}><CheckCircle2 size={16} /><div><strong>{item.title}</strong><span className={`priority-tag ${item.priority || "low"}`}>{item.priority || "general"} priority</span><p>{item.detail}</p></div></div>)}</div><p className="muted-small">{result.recommendations?.context}</p><p className="muted-small safety-text">{result.recommendations?.safety}</p></div>
                </section>
                <section className="chart-card"><div className="chart-heading"><div><h2>Glucose history and forecast graph</h2><p>Measured readings are shown separately from the two model outputs. The forecast steps are not guaranteed clock-time horizons.</p></div><span className="unit-chip">mg/dL</span></div><div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={result.chart_data || []}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e9eff2" /><XAxis dataKey="label" tick={{ fill: "#80919b", fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "#80919b", fontSize: 11 }} axisLine={false} tickLine={false} width={45} domain={[0, "auto"]} /><Tooltip formatter={(value) => value == null ? "—" : [`${value} mg/dL`]} /><ReferenceLine y={70} stroke="#d89b35" strokeDasharray="4 4" label={{ value: "70 low threshold", fill: "#a8792b", fontSize: 10 }} /><ReferenceLine y={180} stroke="#d89b35" strokeDasharray="4 4" label={{ value: "180 high threshold", fill: "#a8792b", fontSize: 10 }} /><Line type="monotone" dataKey="measured" name="Measured CGM" stroke="#159b91" strokeWidth={2.5} connectNulls dot={{ r: 2.5 }} /><Line type="monotone" dataKey="predicted" name="Model forecast" stroke="#5978c7" strokeWidth={2.5} connectNulls dot={{ r: 5 }} /></LineChart></ResponsiveContainer></div></section>
                <section className="two-column-panels advanced-panels">
                  <article className="insight-panel"><div className="panel-heading"><div><div className="eyebrow">EXPLAINABLE AI</div><h2>Why did the model predict this?</h2><p>Reading sensitivity, not clinical causation.</p></div><Sparkles size={20}/></div>
                    <p className="muted-small">{result.explainability?.description}</p>
                    {(result.explainability?.top_influential_readings || []).length ? <div className="explain-list">{result.explainability.top_influential_readings.map((item) => <div className="explain-row" key={item.reading_index}><span>Reading {item.reading_index} <small>({item.glucose_mg_dl} mg/dL)</small></span><b>{item.influence_magnitude} mg/dL sensitivity</b></div>)}</div> : <p className="muted-small">{result.explainability?.message || "This saved review does not yet contain explanation data. Generate a new prediction or reopen this record after restarting the updated backend to calculate it."}</p>}
                    <p className="muted-small">{result.explainability?.caveat}</p>
                  </article>
                  <article className="insight-panel"><div className="panel-heading"><div><div className="eyebrow">MODEL UNCERTAINTY</div><h2>Input sensitivity scenarios</h2><p>Not a calibrated confidence interval.</p></div><Activity size={20}/></div>
                    <div className="scenario-row"><span>6-step scenario range</span><strong>{result.prediction_uncertainty?.six_step_scenario_range?.low}–{result.prediction_uncertainty?.six_step_scenario_range?.high} mg/dL</strong></div>
                    <div className="scenario-row"><span>12-step scenario range</span><strong>{result.prediction_uncertainty?.twelve_step_scenario_range?.low}–{result.prediction_uncertainty?.twelve_step_scenario_range?.high} mg/dL</strong></div>
                    <p className="muted-small">{result.prediction_uncertainty?.assumption}</p><p className="muted-small">{result.prediction_uncertainty?.interpretation}</p>
                  </article>
                </section>
                <section className="chart-card saved-trend-card"><div className="chart-heading"><div><h2>Longitudinal patient trend</h2><p>Daily averages calculated from unique timestamps across saved prediction records.</p></div><span className="unit-chip">{savedAnalytics?.count || 0} saved readings</span></div>
                  {savedAnalytics?.daily?.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={savedAnalytics.daily}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e9eff2"/><XAxis dataKey="date" tick={{fill:"#80919b",fontSize:10}} axisLine={false} tickLine={false}/><YAxis tick={{fill:"#80919b",fontSize:11}} axisLine={false} tickLine={false} width={45}/><Tooltip formatter={(value)=>[`${value} mg/dL`]}/><Line type="monotone" dataKey="average" name="Daily average" stroke="#159b91" strokeWidth={2.5} dot={{r:3}}/></LineChart></ResponsiveContainer></div> : <p className="muted-small saved-trend-empty">Save more prediction sessions to build a multi-day trend view.</p>}
                  {savedAnalytics?.note && <p className="muted-small saved-trend-note">{savedAnalytics.note}</p>}
                </section>
                <div className="info-strip"><div className="info-icon"><AlertTriangle size={19} /></div><div><strong>Interpretation and safety notice</strong><p>{result.notice} Risk categories are broad rule-based educational flags, not clinical alarms. GlucoRAG does not read a live CGM feed; it analyses the timestamped values entered for this prediction run.</p></div></div>
              </>}
              {history.length > 0 && <section className="entry-card history-card"><div className="entry-card-heading"><div><h2>Session prediction history</h2><p>Saved in the local database. Select a record to reopen its full review.</p></div></div><HistoryList history={history} onSelect={async (id) => { try { const response = await fetch(`${API_URL}/api/history/${id}`); if (!response.ok) throw new Error("Could not load saved review."); const saved = await response.json(); setResult({ ...saved.result, history_id: saved.id, saved_at: saved.created_at }); navigate("forecast"); } catch (e) { setError(e.message); } }} /></section>}
            </>
          )}

          {page === "assistant" && (
            <>
              <PageHeading eyebrow="PATIENT EDUCATION" title="AI Patient Support Assistant" description="An always-available educational helper for common diabetes questions." />
              <div className="assistant-layout"><section className="chat-card"><div className="chat-header"><div className="assistant-avatar"><Bot size={21} /></div><div><strong>GlucoRAG Support Assistant</strong><span><span className="status-dot" /> Available · Educational support</span></div></div><div className="chat-messages">{chatMessages.map((message, index) => <div className={`chat-message ${message.role}`} key={index}><div className="chat-bubble">{message.text}</div></div>)}{chatLoading && <div className="chat-message assistant"><div className="chat-bubble typing">Preparing an educational response…</div></div>}</div><form className="chat-input-row" onSubmit={sendChat}><input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask about glucose, food, activity…" aria-label="Your question" /><button className="primary-button" type="submit" disabled={chatLoading || !chatInput.trim()}><Send size={16} /> Send</button></form><div className="chat-disclaimer">Detailed offline diabetes education is available without an API key. An optional language-model provider can be configured on the backend. This assistant does not diagnose or provide medication or insulin doses.</div></section><aside className="suggestion-panel"><h3>Suggested questions</h3>{["What are signs of low glucose?", "What foods can fit into a balanced diabetes meal?", "How can physical activity affect glucose?", "What is the difference between Type 1 and Type 2 diabetes?"].map((question) => <button className="suggestion-button" key={question} onClick={() => sendChat(null, question)}>{question}<ArrowRight size={15} /></button>)}<div className="urgent-card"><AlertTriangle size={18} /><strong>Need urgent help?</strong><p>For severe symptoms such as unconsciousness, seizure, difficulty breathing or confusion, contact emergency services immediately. In India, call 112.</p></div></aside></div>
            </>
          )}

          {page === "hospitals" && (
            <>
              <PageHeading eyebrow="LOCATION-BASED SUPPORT" title="Nearby hospital finder" description="Find mapped healthcare facilities around your current location. Location is requested only when you choose." />
              <section className="location-card"><div className="location-icon"><MapPin size={22} /></div><div className="location-copy"><h2>Find healthcare facilities near you</h2><p>Allow browser location or enter coordinates manually. The app uses coordinates only for this search; they are not saved by this prototype.</p></div><button className="primary-button" onClick={requestLocation}><MapPin size={16} /> Share my location</button></section>
              <section className="manual-location entry-card"><div><strong>Location permission not available?</strong><p>Enter latitude and longitude from your map app to continue.</p></div><input aria-label="Latitude" placeholder="Latitude (e.g. 17.385)" value={manualLat} onChange={(event) => setManualLat(event.target.value)} /><input aria-label="Longitude" placeholder="Longitude (e.g. 78.4867)" value={manualLon} onChange={(event) => setManualLon(event.target.value)} /><button className="secondary-button" onClick={useManualLocation}>Use coordinates</button></section>
              {locationError && <div className="error-message"><AlertTriangle size={17} />{locationError}</div>}
              {location && <section className="entry-card hospital-results"><div className="entry-card-heading"><div><h2>Healthcare facilities within 10 km</h2><p>Search center: {location.lat.toFixed(4)}, {location.lon.toFixed(4)}</p></div><button className="primary-button" onClick={searchHospitals} disabled={hospitalLoading}>{hospitalLoading ? <RefreshCw className="spin" size={16} /> : <MapPinned size={16} />}{hospitalLoading ? "Searching…" : "Find nearby hospitals"}</button></div>{hospitalNotice && <div className="hospital-notice">{hospitalNotice}</div>}<div className="hospital-layout"><div className="hospital-list">{hospitals.length ? hospitals.map((hospital) => <button key={hospital.id} className={`hospital-item ${selectedHospital?.id === hospital.id ? "selected" : ""}`} onClick={() => setSelectedHospital(hospital)}><div className="hospital-item-icon"><HeartPulse size={17} /></div><div className="hospital-item-copy"><strong>{hospital.name}</strong><span>{hospital.facility_type}{typeof hospital.distance_km === "number" ? ` · ${hospital.distance_km} km away` : ""}{hospital.address ? ` · ${hospital.address}` : ""}</span>{hospital.phone && <span><Phone size={12} /> {hospital.phone}</span>}</div><ChevronRight size={16} /></button>) : <div className="empty-hospital-list">No facility results yet. Select Find nearby hospitals. If OpenStreetMap is unavailable, open the map app links.</div>}</div><div className="hospital-map"><iframe title={selectedHospital ? `Map showing ${selectedHospital.name}` : "Map centered on selected location"} src={`https://www.openstreetmap.org/export/embed.html?bbox=${(selectedHospital?.longitude ?? location.lon) - 0.025}%2C${(selectedHospital?.latitude ?? location.lat) - 0.018}%2C${(selectedHospital?.longitude ?? location.lon) + 0.025}%2C${(selectedHospital?.latitude ?? location.lat) + 0.018}&layer=mapnik&marker=${selectedHospital?.latitude ?? location.lat}%2C${selectedHospital?.longitude ?? location.lon}`} loading="lazy" referrerPolicy="no-referrer" /><div className="map-caption"><strong>{selectedHospital?.name || "Your search area"}</strong><div><a href={selectedHospital?.maps_url || `https://www.openstreetmap.org/?mlat=${location.lat}&mlon=${location.lon}#map=14/${location.lat}/${location.lon}`} target="_blank" rel="noreferrer">Open OSM <ExternalLink size={13} /></a><a href={selectedHospital?.google_maps_url || `https://www.google.com/maps/search/hospitals/@${location.lat},${location.lon},13z`} target="_blank" rel="noreferrer">Google Maps <ExternalLink size={13} /></a></div></div></div></div></section>}
              <div className="emergency-strip"><AlertTriangle size={19} /><div><strong>Emergency reminder</strong><p>If you or someone nearby has a medical emergency, call India's emergency number <b>112</b> or go to the nearest emergency department. Do not wait for this app to find a facility.</p></div><a href="tel:112">Call 112 <ExternalLink size={14} /></a></div>
              <p className="muted-small source-note">Hospital listings are sourced from OpenStreetMap contributors and may be incomplete, outdated, or missing phone numbers. Always confirm services, opening hours and emergency capability directly with the facility.</p>
            </>
          )}

          {page === "about" && (
            <>
              <PageHeading eyebrow="PROJECT INFORMATION" title="About GlucoRAG" description="Transformer-based glucose forecasting with supporting educational tools." />
              <section className="about-hero"><div className="about-icon"><Activity size={32} /></div><h2>From glucose forecasting to patient education</h2><p>GlucoRAG combines an existing PyTorch Transformer checkpoint with separate modules for descriptive risk screening, trend summaries, optional meal-response analysis from submitted CGM readings, general food and lifestyle education, an offline support assistant, and nearby healthcare facility lookup.</p></section>
              <section className="section-heading"><div><h2>Core model configuration</h2><p>Architecture loaded from the existing checkpoint implementation.</p></div></section><section className="stats-grid"><Stat label="Input sequence" value="24 × 1" foot="Glucose-only sequence" icon={DatabaseIcon} /><Stat label="Embedding size" value="128" foot="Model dimension" icon={Activity} /><Stat label="Encoder layers" value="3" foot="Transformer encoder" icon={BrainCircuitIcon} /><Stat label="Attention heads" value="4" foot="Multi-head attention" icon={TrendingUp} /></section>
              <section className="entry-card about-limitations"><h2>Important limitations and transparency</h2><ul><li>The original Transformer checkpoint and architecture are preserved. Patient demographics are collected as optional context but are not fed into this checkpoint.</li><li>The two outputs are 6-step and 12-step positions. Their exact time horizon cannot be guaranteed from this prototype's current metadata.</li><li>Risk screening uses simple glucose thresholds for education and does not account for an individual's prescribed target range or full clinical context.</li><li>The patient assistant is a transparent offline rule-based knowledge helper, not a connected large language model and not a clinician.</li><li>Food suggestions are general education, not a personalized diet prescription.</li><li>Meal response analysis compares submitted measured readings around a recorded meal. It is descriptive only, may be incomplete when matching readings are missing, and does not prove the meal caused a glucose change.</li><li>Hospital search uses OpenStreetMap data and depends on internet access. Listings may be incomplete or inaccurate.</li><li>Prediction history is stored in a local SQLite database on the backend computer. This prototype has no patient login, encryption, or multi-user access controls; do not store identifiable patient information or use it as a clinical record.</li><li>Never use this research prototype for diagnosis, medication changes, insulin dosing, or emergency decisions.</li></ul></section>
            </>
          )}

          <footer className="footer"><span>© 2026 GlucoRAG · Academic research prototype</span><span>React · FastAPI · PyTorch · OpenStreetMap</span></footer>
        </div>
      </main>
    </div>
  );
}

function PageHeading({ eyebrow, title, description, action }) {
  return <section className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</section>;
}
function ForecastCard({ label, step, value, accent }) {
  return <div className={`forecast-card ${accent ? "forecast-card-accent" : ""}`}><div className="forecast-label">{label}<span>{step}</span></div><div className="forecast-number">{value}<small>mg/dL</small></div><p>Experimental output from the existing Transformer model.</p></div>;
}
function RiskCard({ name, assessment, isForecast = false }) {
  const Icon = riskIcon(assessment.severity);
  const guidance = isForecast
    ? "Experimental model output only. It is not a measured value, live alert, diagnosis, or instruction to change treatment."
    : "This category describes the latest value submitted in this prediction run. It is not a live glucose measurement or continuous monitoring result.";
  return <div className={`risk-card ${severityClass(assessment.severity)}`}><div className="risk-card-top"><span>{name}</span><Icon size={17} /></div><strong>{assessment.value} <small>mg/dL</small></strong><b>{assessment.label}</b><p>{assessment.message}</p><div className="risk-guidance">{guidance}</div></div>;
}
function HistoryList({ history, onSelect }) {
  return <div className="history-list">{history.slice(0, 8).map((item) => <button type="button" className="history-row" key={item.id} onClick={() => onSelect?.(item.id)}><div><strong>{item.time}</strong><span>Latest submitted value: {item.latest} mg/dL · Risk: {item.risk}</span></div><div className="history-values"><span>6-step: <b>{item.six}</b></span><span>12-step: <b>{item.twelve}</b></span></div><span className="history-open-label">Open review →</span></button>)}</div>;
}
function EmptyState({ icon: Icon, title, description, action, actionLabel }) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={30} /></div><h2>{title}</h2><p>{description}</p><button className="primary-button" onClick={action}>{actionLabel}<ArrowRight size={16} /></button></div>;
}
function Stat({ label, value, foot, icon: Icon }) {
  return <div className="stat-card"><div className="stat-top"><span>{label}</span><Icon /></div><div className="stat-value">{value}</div><div className="stat-foot">{foot}</div></div>;
}
function DatabaseIcon(props) { return <Activity {...props} />; }
function BrainCircuitIcon(props) { return <HeartPulse {...props} />; }

export default App;
