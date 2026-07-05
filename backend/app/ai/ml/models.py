"""
KrishiMitra Backend – Machine Learning Models
===============================================
Scikit-learn prediction pipelines for:
  - Crop Recommendation
  - Vehicle Demand Prediction
  - Yield Prediction

Models are lazy-loaded on first use and are fully independent from Gemini.
Gemini only receives the OUTPUT of these models, never executes them.
"""
import logging
from pathlib import Path
from typing import Any, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "saved_models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Singleton model holders ───────────────────────────────────────────────────
_crop_model: Optional[Pipeline] = None
_vehicle_model: Optional[Pipeline] = None
_crop_label_encoder: Optional[LabelEncoder] = None

# ── Crop classes (representative set for India) ───────────────────────────────
CROP_CLASSES = [
    "rice", "wheat", "maize", "chickpea", "kidneybeans", "pigeonpeas",
    "mothbeans", "mungbean", "blackgram", "lentil", "pomegranate",
    "banana", "mango", "grapes", "watermelon", "muskmelon", "apple",
    "orange", "papaya", "coconut", "cotton", "jute", "coffee",
    "tomato", "potato", "onion", "groundnut", "sugarcane",
]

DEMAND_LEVELS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
VEHICLE_TYPES = {
    "LOW": ["Motorcycle (small cargo)", "Auto-rickshaw"],
    "MEDIUM": ["Mini-truck (1T)", "Tractor-trolley"],
    "HIGH": ["Medium truck (5T)", "Pick-up van"],
    "VERY_HIGH": ["Large truck (10T)", "Container truck"],
}


# ── Crop Model ────────────────────────────────────────────────────────────────
def _build_synthetic_crop_training_data() -> tuple[np.ndarray, np.ndarray]:
    """
    Generate representative synthetic training data for demonstration.
    In production, replace with the Kaggle Crop Recommendation dataset.
    """
    rng = np.random.RandomState(42)
    n = 2200

    crop_params = {
        "rice":       ([70, 45, 40, 25, 80, 6.0, 200], [10, 5, 5, 2, 5, 0.5, 30]),
        "wheat":      ([40, 60, 60, 18, 65, 6.5, 75],  [10, 5, 5, 3, 5, 0.5, 20]),
        "maize":      ([80, 60, 70, 22, 65, 6.0, 65],  [15, 5, 5, 3, 5, 0.5, 15]),
        "tomato":     ([18, 10, 15, 25, 70, 6.0, 100], [5, 3, 3, 3, 5, 0.5, 20]),
        "potato":     ([20, 60, 65, 15, 80, 5.5, 85],  [5, 5, 5, 3, 5, 0.5, 15]),
        "cotton":     ([20, 25, 25, 30, 70, 6.5, 80],  [5, 5, 5, 3, 5, 0.5, 20]),
        "sugarcane":  ([26, 15, 20, 25, 70, 6.5, 90],  [5, 3, 3, 3, 5, 0.5, 20]),
        "groundnut":  ([22, 40, 27, 25, 60, 6.5, 55],  [5, 5, 5, 3, 5, 0.5, 15]),
        "banana":     ([100, 82, 50, 27, 80, 5.5, 100],[15, 10, 10, 3, 5, 0.5, 20]),
        "coconut":    ([22, 16, 45, 27, 94, 5.5, 200], [5, 3, 5, 3, 5, 0.5, 30]),
    }

    X_list, y_list = [], []
    per_class = n // len(crop_params)

    for crop, (means, stds) in crop_params.items():
        samples = rng.normal(means, stds, (per_class, 7))
        X_list.append(samples)
        y_list.extend([crop] * per_class)

    X = np.vstack(X_list)
    y = np.array(y_list)
    return X, y


def _get_crop_model() -> tuple[Pipeline, LabelEncoder]:
    """Lazy-load or train the crop recommendation model."""
    global _crop_model, _crop_label_encoder

    model_path = MODELS_DIR / "crop_model.joblib"
    encoder_path = MODELS_DIR / "crop_label_encoder.joblib"

    if _crop_model is not None and _crop_label_encoder is not None:
        return _crop_model, _crop_label_encoder

    if model_path.exists() and encoder_path.exists():
        logger.info("Loading saved crop model …")
        _crop_model = joblib.load(model_path)
        _crop_label_encoder = joblib.load(encoder_path)
        return _crop_model, _crop_label_encoder

    logger.info("Training crop recommendation model (first run) …")
    X, y_raw = _build_synthetic_crop_training_data()
    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=150, random_state=42, n_jobs=-1)),
        ]
    )
    pipeline.fit(X, y)

    joblib.dump(pipeline, model_path)
    joblib.dump(le, encoder_path)
    logger.info("Crop model trained and saved.")

    _crop_model = pipeline
    _crop_label_encoder = le
    return _crop_model, _crop_label_encoder


def predict_crop(
    nitrogen: float,
    phosphorus: float,
    potassium: float,
    temperature: float,
    humidity: float,
    ph: float,
    rainfall: float,
) -> dict[str, Any]:
    """
    Predict the most suitable crop for given soil/climate parameters.

    Args:
        nitrogen, phosphorus, potassium: Soil NPK values (kg/ha).
        temperature: Average temperature (°C).
        humidity: Relative humidity (%).
        ph: Soil pH.
        rainfall: Annual rainfall (mm).

    Returns:
        Dict with 'recommended_crop', 'confidence', and 'alternatives'.
    """
    model, le = _get_crop_model()

    X = np.array([[nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall]])
    proba = model.predict_proba(X)[0]
    top_indices = np.argsort(proba)[::-1][:5]

    recommended_idx = top_indices[0]
    recommended_crop = le.inverse_transform([recommended_idx])[0]
    confidence = round(float(proba[recommended_idx]) * 100, 2)

    alternatives: List[str] = [
        le.inverse_transform([i])[0]
        for i in top_indices[1:]
        if proba[i] > 0.05
    ]

    return {
        "recommended_crop": recommended_crop,
        "confidence": confidence,
        "alternatives": alternatives,
    }


# ── Vehicle Demand Model ──────────────────────────────────────────────────────
_vehicle_model_obj: Optional[Pipeline] = None


def _get_vehicle_model() -> Pipeline:
    """Lazy-load or train the vehicle demand prediction model."""
    global _vehicle_model_obj

    model_path = MODELS_DIR / "vehicle_model.joblib"

    if _vehicle_model_obj is not None:
        return _vehicle_model_obj

    if model_path.exists():
        logger.info("Loading saved vehicle model …")
        _vehicle_model_obj = joblib.load(model_path)
        return _vehicle_model_obj

    logger.info("Training vehicle demand model …")
    rng = np.random.RandomState(99)
    n = 1000

    # Synthetic features: [quantity_tonnes, distance_km, is_perishable, season_code]
    quantity = rng.uniform(0.5, 50, n)
    distance = rng.uniform(10, 500, n)
    perishable = rng.randint(0, 2, n)
    season = rng.randint(0, 4, n)  # 0=winter,1=spring,2=summer,3=monsoon

    X = np.column_stack([quantity, distance, perishable, season])
    # Demand: higher for large quantities, perishables, and long distances
    score = quantity * 0.3 + distance * 0.02 + perishable * 5 + season * 0.5
    y = np.digitize(score, bins=[5, 12, 20]) % 4  # 0-3

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(n_estimators=100, random_state=42)),
        ]
    )
    pipeline.fit(X, y)
    joblib.dump(pipeline, model_path)
    logger.info("Vehicle model trained and saved.")
    _vehicle_model_obj = pipeline
    return _vehicle_model_obj


def predict_vehicle_demand(
    quantity_tonnes: float,
    destination: str,
    crop_type: str,
    date: str,
) -> dict[str, Any]:
    """
    Predict vehicle demand level for a given cargo shipment.

    Returns:
        Dict with 'demand_level', 'recommended_vehicles', 'estimated_cost_inr'.
    """
    model = _get_vehicle_model()

    # Heuristic feature engineering from inputs
    is_perishable = int(
        any(p in crop_type.lower() for p in ["tomato", "banana", "mango", "milk", "fish"])
    )
    # Approximate distance from destination string length (demo only)
    approx_distance = min(len(destination) * 10, 500)
    season_code = _date_to_season(date)

    X = np.array([[quantity_tonnes, approx_distance, is_perishable, season_code]])
    demand_idx = int(model.predict(X)[0])
    demand_level = DEMAND_LEVELS[demand_idx]

    vehicles = VEHICLE_TYPES[demand_level]
    cost_per_km = {"LOW": 8, "MEDIUM": 14, "HIGH": 22, "VERY_HIGH": 35}[demand_level]
    cost_estimate = round(approx_distance * cost_per_km * quantity_tonnes, 0)

    return {
        "demand_level": demand_level,
        "recommended_vehicles": vehicles,
        "estimated_cost_inr": {
            "min": round(cost_estimate * 0.85, 0),
            "max": round(cost_estimate * 1.15, 0),
        },
        "best_time_window": _best_time_window(season_code),
    }


def _date_to_season(date_str: str) -> int:
    """Convert YYYY-MM-DD to season code (0=winter, 1=spring, 2=summer, 3=monsoon)."""
    try:
        month = int(date_str.split("-")[1])
        if month in [12, 1, 2]:
            return 0
        elif month in [3, 4, 5]:
            return 1
        elif month in [6, 7, 8, 9]:
            return 3  # monsoon
        else:
            return 2
    except Exception:
        return 2


def _best_time_window(season_code: int) -> str:
    windows = {
        0: "06:00 - 10:00 (avoid frost during early morning in extreme winters)",
        1: "05:30 - 09:00 or 17:00 - 19:00",
        2: "Early morning 05:00 - 08:00 to avoid heat",
        3: "Check rain forecast before departure; prefer 08:00 - 12:00",
    }
    return windows.get(season_code, "Morning hours recommended")


# ══════════════════════════════════════════════════════════════════════════════
# ── Yield Prediction Model ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

_yield_model_obj: Optional[Pipeline] = None


def _get_yield_model() -> Pipeline:
    """Lazy-load or train the yield prediction model."""
    global _yield_model_obj

    model_path = MODELS_DIR / "yield_model.joblib"

    if _yield_model_obj is not None:
        return _yield_model_obj

    if model_path.exists():
        logger.info("Loading saved yield model …")
        _yield_model_obj = joblib.load(model_path)
        return _yield_model_obj

    logger.info("Training yield prediction model …")
    rng = np.random.RandomState(77)
    n = 1500

    # Features: [ndvi, rainfall_mm, temperature_c, soil_ph, nitrogen, humidity, area_ha]
    ndvi = rng.uniform(0.1, 0.9, n)
    rainfall = rng.uniform(50, 400, n)
    temperature = rng.uniform(15, 40, n)
    ph = rng.uniform(5.0, 8.0, n)
    nitrogen = rng.uniform(10, 120, n)
    humidity = rng.uniform(40, 95, n)
    area = rng.uniform(0.5, 20, n)

    X = np.column_stack([ndvi, rainfall, temperature, ph, nitrogen, humidity, area])

    # Synthetic yield (kg/ha) – higher for good NDVI, moderate temp, adequate rain
    base_yield = (
        ndvi * 3000
        + np.clip(rainfall / 10, 0, 200)
        - np.abs(temperature - 25) * 20
        + (ph - 6.5) * 100
        + nitrogen * 5
        + humidity * 2
    )
    y = np.clip(base_yield + rng.normal(0, 150, n), 200, 6000)

    from sklearn.ensemble import RandomForestRegressor
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("reg", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
    ])
    pipeline.fit(X, y)
    joblib.dump(pipeline, model_path)
    logger.info("Yield model trained and saved.")
    _yield_model_obj = pipeline
    return _yield_model_obj


def predict_yield(
    ndvi: float,
    rainfall_mm: float,
    temperature_c: float,
    soil_ph: float,
    nitrogen_kg_ha: float,
    humidity_pct: float,
    area_ha: float = 1.0,
) -> dict[str, Any]:
    """
    Predict expected crop yield for a field.

    Args:
        ndvi:           Current NDVI from satellite (0.0–1.0).
        rainfall_mm:    Recent rainfall in mm.
        temperature_c:  Average temperature in °C.
        soil_ph:        Soil pH.
        nitrogen_kg_ha: Soil nitrogen in kg/ha.
        humidity_pct:   Relative humidity %.
        area_ha:        Field area in hectares.

    Returns:
        Dict with 'yield_kg_per_ha', 'total_yield_kg', 'confidence', 'category'.
    """
    model = _get_yield_model()
    X = np.array([[ndvi, rainfall_mm, temperature_c, soil_ph,
                   nitrogen_kg_ha, humidity_pct, area_ha]])
    yield_per_ha = float(model.predict(X)[0])
    yield_per_ha = max(200.0, min(yield_per_ha, 6000.0))
    total_yield = round(yield_per_ha * area_ha, 1)

    # Confidence based on NDVI quality
    if ndvi > 0.6:
        confidence = 88
    elif ndvi > 0.4:
        confidence = 75
    elif ndvi > 0.2:
        confidence = 60
    else:
        confidence = 45  # Sparse vegetation → low confidence

    category = _yield_category(yield_per_ha)

    return {
        "yield_kg_per_ha": round(yield_per_ha, 1),
        "total_yield_kg": total_yield,
        "confidence": confidence,
        "category": category,
        "inputs_used": {
            "ndvi": ndvi,
            "rainfall_mm": rainfall_mm,
            "temperature_c": temperature_c,
        },
    }


def _yield_category(yield_per_ha: float) -> str:
    if yield_per_ha >= 4000:
        return "excellent"
    elif yield_per_ha >= 2500:
        return "good"
    elif yield_per_ha >= 1500:
        return "moderate"
    elif yield_per_ha >= 800:
        return "below_average"
    else:
        return "poor"


# ══════════════════════════════════════════════════════════════════════════════
# ── Disease Risk Model ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

_disease_model_obj: Optional[Pipeline] = None

DISEASE_LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]


def _get_disease_model() -> Pipeline:
    """Lazy-load or train the disease risk model."""
    global _disease_model_obj

    model_path = MODELS_DIR / "disease_model.joblib"

    if _disease_model_obj is not None:
        return _disease_model_obj

    if model_path.exists():
        logger.info("Loading saved disease model …")
        _disease_model_obj = joblib.load(model_path)
        return _disease_model_obj

    logger.info("Training disease risk model …")
    rng = np.random.RandomState(33)
    n = 1200

    # Features: [humidity, temperature, rainfall, ndvi, days_since_sowing]
    humidity = rng.uniform(40, 100, n)
    temperature = rng.uniform(15, 40, n)
    rainfall = rng.uniform(0, 200, n)
    ndvi = rng.uniform(0.05, 0.9, n)
    days_since_sowing = rng.uniform(0, 180, n)

    X = np.column_stack([humidity, temperature, rainfall, ndvi, days_since_sowing])

    # Risk score: high humidity + moderate temp + declining NDVI = high risk
    risk = (
        humidity * 0.3
        + np.clip(35 - np.abs(temperature - 25), 0, 35) * 0.5
        + np.log1p(rainfall) * 2
        + (0.7 - ndvi) * 30
        + (days_since_sowing / 180) * 10
    )
    y = np.digitize(risk, bins=[20, 35, 50]) % 4

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(n_estimators=100, random_state=42)),
    ])
    pipeline.fit(X, y)
    joblib.dump(pipeline, model_path)
    logger.info("Disease risk model trained and saved.")
    _disease_model_obj = pipeline
    return _disease_model_obj


def predict_disease_risk(
    humidity_pct: float,
    temperature_c: float,
    rainfall_mm: float,
    ndvi: float,
    days_since_sowing: int = 60,
) -> dict[str, Any]:
    """
    Predict crop disease risk based on environmental conditions.

    Args:
        humidity_pct:      Relative humidity %.
        temperature_c:     Average temperature °C.
        rainfall_mm:       Recent rainfall mm.
        ndvi:              Current NDVI (0.0–1.0).
        days_since_sowing: Days since crop was sown.

    Returns:
        Dict with 'risk_level', 'risk_score', 'confidence', 'common_diseases'.
    """
    model = _get_disease_model()
    X = np.array([[humidity_pct, temperature_c, rainfall_mm, ndvi, days_since_sowing]])
    proba = model.predict_proba(X)[0]
    risk_idx = int(np.argmax(proba))
    risk_level = DISEASE_LEVELS[risk_idx]
    confidence = round(float(proba[risk_idx]) * 100, 1)
    risk_score = round(float(risk_idx) / 3 * 100, 1)  # 0–100

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "confidence": confidence,
        "common_diseases": _common_diseases(risk_level, temperature_c, humidity_pct),
        "preventive_actions": _disease_actions(risk_level),
    }


def _common_diseases(risk_level: str, temp: float, humidity: float) -> List[str]:
    if risk_level in ("LOW",):
        return []
    diseases = []
    if humidity > 75:
        diseases += ["Leaf blight", "Downy mildew"]
    if 20 <= temp <= 30:
        diseases += ["Rust", "Anthracnose"]
    if temp > 32:
        diseases += ["Bacterial wilt", "Heat stress"]
    if risk_level == "CRITICAL":
        diseases += ["Brown plant hopper", "Stem rot"]
    return list(set(diseases))[:4]


def _disease_actions(risk_level: str) -> List[str]:
    actions = {
        "LOW": ["Monitor weekly", "Maintain proper field drainage"],
        "MODERATE": [
            "Scout field every 3 days",
            "Apply preventive fungicide",
            "Improve air circulation",
        ],
        "HIGH": [
            "Apply curative fungicide/pesticide immediately",
            "Remove infected plants",
            "Reduce irrigation frequency",
            "Contact local KVK (Krishi Vigyan Kendra)",
        ],
        "CRITICAL": [
            "Emergency: contact extension officer NOW",
            "Apply systemic fungicide",
            "Isolate infected sections",
            "Assess crop insurance claim",
        ],
    }
    return actions.get(risk_level, [])


# ══════════════════════════════════════════════════════════════════════════════
# ── Water Stress / Irrigation Recommendation Model ────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def predict_water_stress(
    ndvi: float,
    rainfall_mm_7d: float,
    temperature_c: float,
    humidity_pct: float,
    soil_type: str = "loamy",
    days_since_irrigation: int = 3,
) -> dict[str, Any]:
    """
    Deterministic water stress assessment and irrigation recommendation.

    This model uses domain-specific agronomic rules rather than ML,
    since the rules are well-established and interpretable.

    Args:
        ndvi:                    Current NDVI.
        rainfall_mm_7d:          Total rainfall in last 7 days.
        temperature_c:           Current temperature °C.
        humidity_pct:            Relative humidity %.
        soil_type:               Soil type string.
        days_since_irrigation:   Days since last irrigation.

    Returns:
        Dict with 'stress_level', 'irrigate_now', 'water_need_mm', 'recommendation'.
    """
    # Evapotranspiration estimate (simplified Penman-Monteith proxy)
    et_daily = max(0.0, (0.408 * (temperature_c - 5) + 0.2 * (100 - humidity_pct)) / 10)
    et_7d = et_daily * 7

    # Soil water retention factor
    retention = {
        "clay": 1.4, "silty": 1.3, "loamy": 1.0, "alluvial": 1.0,
        "sandy": 0.6, "peaty": 0.8, "black": 1.3, "red": 0.7,
    }.get(soil_type.lower(), 1.0)

    water_deficit = max(0.0, et_7d - rainfall_mm_7d * retention)
    days_factor = min(days_since_irrigation / 5.0, 2.0)

    # NDVI-based stress indicator (low NDVI often = water stress)
    ndvi_stress = max(0.0, (0.5 - ndvi) * 40) if ndvi < 0.5 else 0

    stress_score = water_deficit + ndvi_stress * days_factor

    if stress_score < 10:
        stress_level = "none"
        irrigate_now = False
        water_need_mm = 0
    elif stress_score < 25:
        stress_level = "mild"
        irrigate_now = days_since_irrigation >= 4
        water_need_mm = round(stress_score * 0.8, 1)
    elif stress_score < 45:
        stress_level = "moderate"
        irrigate_now = True
        water_need_mm = round(stress_score * 1.0, 1)
    else:
        stress_level = "severe"
        irrigate_now = True
        water_need_mm = round(min(stress_score * 1.2, 80), 1)

    return {
        "stress_level": stress_level,
        "irrigate_now": irrigate_now,
        "water_need_mm": water_need_mm,
        "recommendation": _irrigation_recommendation(stress_level, water_need_mm),
        "et_estimate_mm": round(et_7d, 1),
        "rainfall_effective_mm": round(rainfall_mm_7d * retention, 1),
        "confidence": 82,
    }


def _irrigation_recommendation(stress_level: str, water_mm: float) -> str:
    if stress_level == "none":
        return "No irrigation needed. Monitor soil moisture."
    elif stress_level == "mild":
        return f"Light irrigation of {water_mm}mm recommended within 2 days."
    elif stress_level == "moderate":
        return (
            f"Irrigate {water_mm}mm today. "
            "Drip/sprinkler preferred to minimise evaporation."
        )
    else:
        return (
            f"URGENT: Irrigate {water_mm}mm immediately. "
            "Crop is under severe water stress. "
            "Consider mulching to retain soil moisture."
        )

