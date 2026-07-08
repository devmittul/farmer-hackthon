"""
KrishiMitra Backend – Phase 2 Test Suite
==========================================
Unit tests for all modules introduced in Phase 2:
  • IntentDetector
  • ConfidenceEngine
  • ContextBuilder (data structures only – no DB)
  • New ML models: predict_yield, predict_disease_risk, predict_water_stress
  • Repository helpers (unit-level – no live DB)
  • Digital Twin Pydantic models
  • prompt_builder Digital Twin prompt
  • Response formatter

Run with:
    pytest app/tests/test_phase2.py -v --asyncio-mode=auto
"""
import pytest
import os

# Patch env before any import
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB_NAME", "krishimitra_test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_that_is_long_enough_for_hs256_algorithm")
os.environ.setdefault("CLAUDE_API_KEY", "test_key")


# ══════════════════════════════════════════════════════════════════════════════
# ── IntentDetector ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TestIntentDetector:
    """Tests for the standalone IntentDetector module."""

    def test_sos_has_highest_priority(self):
        """SOS must always win over other intents in the same message."""
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        result = IntentDetector.detect("Emergency help! My field is on fire and what is the weather?")
        assert result == IntentType.SOS

    def test_weather_intent_english(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("What is the weather forecast for today?") == IntentType.WEATHER

    def test_weather_intent_hindi(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("kal mausam kaisa rahega?") == IntentType.WEATHER

    def test_crop_intent(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("Which crop should I plant this season?") == IntentType.CROP

    def test_crop_intent_hindi(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("meri fasal ki kya dekhbhal karein") == IntentType.CROP

    def test_vehicle_intent(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("I need to book a truck for my wheat") == IntentType.VEHICLE

    def test_route_intent_regex(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("How do I go from Ahmedabad to Surat?") == IntentType.ROUTE

    def test_market_intent(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("What is the price of rice today?") == IntentType.MARKET

    def test_courier_intent(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("I want to send a parcel to the next village") == IntentType.COURIER

    def test_chat_fallback(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("Hello, how are you?") == IntentType.CHAT

    def test_detect_with_scores_returns_all_intents(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        scores = IntentDetector.detect_with_scores("weather crop price")
        assert IntentType.WEATHER in scores
        assert IntentType.CROP in scores
        assert IntentType.MARKET in scores
        assert scores[IntentType.WEATHER] >= 1
        assert scores[IntentType.CROP] >= 1

    def test_detect_with_scores_sos_highest_for_emergency(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        scores = IntentDetector.detect_with_scores("emergency help bachao")
        assert scores.get(IntentType.SOS, 0) >= 2

    def test_empty_message_returns_chat(self):
        from app.ai.intent_detector import IntentDetector
        from app.schemas.requests import IntentType
        assert IntentDetector.detect("   ") == IntentType.CHAT


# ══════════════════════════════════════════════════════════════════════════════
# ── ConfidenceEngine ───────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TestConfidenceEngine:
    """Tests for the deterministic confidence scoring engine."""

    def _make_ctx(self, **kwargs):
        """Build a minimal StructuredContext for testing."""
        from app.ai.context_builder import StructuredContext
        from app.schemas.requests import IntentType, LanguageCode
        return StructuredContext(
            request_id="test-123",
            timestamp="2026-07-02T00:00:00Z",
            intent=IntentType.CHAT,
            language=LanguageCode.EN,
            raw_message="test",
            location=None,
            **kwargs,
        )

    def test_no_data_returns_50_percent(self):
        from app.ai.confidence_engine import ConfidenceEngine
        ctx = self._make_ctx()
        result = ConfidenceEngine.compute(ctx)
        assert result["overall"] == 50.0
        assert result["level"] == "low"

    def test_weather_data_raises_score(self):
        from app.ai.confidence_engine import ConfidenceEngine
        ctx = self._make_ctx(
            weather={"forecast": [{"date": "2026-07-02"}, {"date": "2026-07-03"}]},
        )
        result = ConfidenceEngine.compute(ctx)
        assert result["overall"] > 50
        assert result["weather"] is not None

    def test_full_data_returns_high_confidence(self):
        from app.ai.confidence_engine import ConfidenceEngine
        ctx = self._make_ctx(
            weather={"forecast": [{"date": "2026-07-02"}]},
            satellite={"ndvi": 0.65},
            crop_prediction={"confidence": 91.0},
            farmer={"name": "Ramesh"},
            field={"soil_type": "loamy"},
            recent_chat=[{"user_said": "hello", "assistant_replied": "hi"}],
        )
        result = ConfidenceEngine.compute(ctx)
        assert result["overall"] >= 80
        assert result["level"] in ("high", "very_high")
        assert result["satellite"] is not None
        assert result["ml_crop"] == 91

    def test_satellite_ndvi_moderate_has_penalty(self):
        """NDVI in 0.3–0.5 range should have a slight confidence penalty."""
        from app.ai.confidence_engine import ConfidenceEngine
        ctx_moderate = self._make_ctx(satellite={"ndvi": 0.4})
        ctx_high = self._make_ctx(satellite={"ndvi": 0.75})
        r_mod = ConfidenceEngine.compute(ctx_moderate)
        r_high = ConfidenceEngine.compute(ctx_high)
        assert r_mod["satellite"] < r_high["satellite"]

    def test_compute_from_dict_no_sources(self):
        from app.ai.confidence_engine import ConfidenceEngine
        result = ConfidenceEngine.compute_from_dict({})
        assert result["overall"] == 50
        assert result["level"] == "low"

    def test_compute_from_dict_with_sources(self):
        from app.ai.confidence_engine import ConfidenceEngine
        result = ConfidenceEngine.compute_from_dict({"weather": True, "farmer": True})
        assert result["overall"] > 80

    def test_confidence_level_labels(self):
        from app.ai.confidence_engine import _confidence_level
        assert _confidence_level(95) == "very_high"
        assert _confidence_level(80) == "high"
        assert _confidence_level(65) == "medium"
        assert _confidence_level(40) == "low"
        assert _confidence_level(20) == "very_low"


# ══════════════════════════════════════════════════════════════════════════════
# ── New ML Models ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TestYieldPrediction:
    """Tests for the yield prediction ML model."""

    def test_returns_expected_keys(self):
        from app.ai.ml.models import predict_yield
        result = predict_yield(
            ndvi=0.65, rainfall_mm=120, temperature_c=25,
            soil_ph=6.5, nitrogen_kg_ha=60, humidity_pct=70, area_ha=2.0,
        )
        assert "yield_kg_per_ha" in result
        assert "total_yield_kg" in result
        assert "confidence" in result
        assert "category" in result

    def test_total_yield_equals_per_ha_times_area(self):
        from app.ai.ml.models import predict_yield
        r = predict_yield(0.7, 150, 24, 6.5, 80, 65, area_ha=3.0)
        assert abs(r["total_yield_kg"] - r["yield_kg_per_ha"] * 3.0) < 10

    def test_high_ndvi_gives_high_confidence(self):
        from app.ai.ml.models import predict_yield
        r_high = predict_yield(0.8, 120, 25, 6.5, 60, 70, 1.0)
        r_low = predict_yield(0.15, 120, 25, 6.5, 60, 70, 1.0)
        assert r_high["confidence"] > r_low["confidence"]

    def test_yield_capped_within_bounds(self):
        from app.ai.ml.models import predict_yield
        r = predict_yield(0.01, 10, 45, 4.0, 5, 20, 1.0)
        assert r["yield_kg_per_ha"] >= 200
        assert r["yield_kg_per_ha"] <= 6000

    def test_category_values(self):
        from app.ai.ml.models import predict_yield, _yield_category
        assert _yield_category(5000) == "excellent"
        assert _yield_category(3000) == "good"
        assert _yield_category(2000) == "moderate"
        assert _yield_category(1000) == "below_average"
        assert _yield_category(500) == "poor"


class TestDiseaseRisk:
    """Tests for the disease risk ML model."""

    def test_returns_expected_keys(self):
        from app.ai.ml.models import predict_disease_risk
        result = predict_disease_risk(
            humidity_pct=80, temperature_c=28, rainfall_mm=50,
            ndvi=0.4, days_since_sowing=60,
        )
        assert "risk_level" in result
        assert "risk_score" in result
        assert "confidence" in result
        assert "common_diseases" in result
        assert "preventive_actions" in result

    def test_risk_level_is_valid(self):
        from app.ai.ml.models import predict_disease_risk, DISEASE_LEVELS
        r = predict_disease_risk(75, 26, 30, 0.5, 45)
        assert r["risk_level"] in DISEASE_LEVELS

    def test_confidence_in_valid_range(self):
        from app.ai.ml.models import predict_disease_risk
        r = predict_disease_risk(85, 27, 60, 0.35, 90)
        assert 0 <= r["confidence"] <= 100

    def test_preventive_actions_not_empty_for_high_risk(self):
        from app.ai.ml.models import _disease_actions
        actions = _disease_actions("HIGH")
        assert len(actions) >= 2

    def test_low_risk_no_diseases(self):
        from app.ai.ml.models import _common_diseases
        diseases = _common_diseases("LOW", 25, 60)
        assert diseases == []


class TestWaterStress:
    """Tests for the rule-based water stress model."""

    def test_no_stress_when_plenty_of_rain(self):
        from app.ai.ml.models import predict_water_stress
        r = predict_water_stress(
            ndvi=0.7, rainfall_mm_7d=100, temperature_c=20,
            humidity_pct=80, soil_type="loamy", days_since_irrigation=1,
        )
        assert r["stress_level"] == "none"
        assert r["irrigate_now"] is False
        assert r["water_need_mm"] == 0

    def test_severe_stress_in_dry_hot_conditions(self):
        from app.ai.ml.models import predict_water_stress
        r = predict_water_stress(
            ndvi=0.2, rainfall_mm_7d=0, temperature_c=42,
            humidity_pct=20, soil_type="sandy", days_since_irrigation=10,
        )
        assert r["stress_level"] in ("moderate", "severe")
        assert r["irrigate_now"] is True
        assert r["water_need_mm"] > 0

    def test_returns_all_required_keys(self):
        from app.ai.ml.models import predict_water_stress
        r = predict_water_stress(0.5, 20, 30, 60)
        required = {"stress_level", "irrigate_now", "water_need_mm",
                    "recommendation", "et_estimate_mm", "rainfall_effective_mm", "confidence"}
        assert required.issubset(r.keys())

    def test_sandy_soil_less_water_retention(self):
        """Sandy soil should result in higher water deficit than clay."""
        from app.ai.ml.models import predict_water_stress
        r_sandy = predict_water_stress(0.5, 20, 30, 50, soil_type="sandy")
        r_clay = predict_water_stress(0.5, 20, 30, 50, soil_type="clay")
        assert r_sandy["rainfall_effective_mm"] < r_clay["rainfall_effective_mm"]


# ══════════════════════════════════════════════════════════════════════════════
# ── Digital Twin Models ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TestDigitalTwinModels:
    """Tests for the Digital Twin Pydantic document models."""

    def test_farmer_profile_defaults(self):
        from app.models.digital_twin import FarmerProfile
        p = FarmerProfile(user_id="u1", name="Ramesh")
        assert p.preferred_language == "en"
        assert p.farm_ids == []
        assert p.field_ids == []
        assert p.total_fields == 0

    def test_field_profile_requires_farm_id(self):
        from app.models.digital_twin import FieldProfile
        f = FieldProfile(field_id="f1", farm_id="farm1", user_id="u1")
        assert f.harvest_history == []
        assert f.satellite_history == []
        assert f.disease_history == []

    def test_harvest_record_model(self):
        from app.models.digital_twin import HarvestRecord
        r = HarvestRecord(season="Kharif 2025", crop="rice", yield_kg_per_ha=3500)
        assert r.crop == "rice"
        assert r.yield_kg_per_ha == 3500

    def test_geo_point_model(self):
        from app.models.digital_twin import GeoPoint
        p = GeoPoint(latitude=23.03, longitude=72.58)
        assert p.latitude == 23.03
        assert p.elevation_m is None

    def test_satellite_snapshot_model(self):
        from app.models.digital_twin import SatelliteSnapshot
        s = SatelliteSnapshot(
            captured_at="2026-07-02",
            ndvi=0.65,
            crop_health="Good crop health",
        )
        assert s.ndvi == 0.65
        assert s.data_source == "Sentinel-2 SR (GEE)"


# ══════════════════════════════════════════════════════════════════════════════
# ── ResponseFormatter ─────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TestResponseFormatter:
    """Tests for the canonical response envelope."""

    def test_format_contains_all_required_keys(self):
        from app.ai.response_formatter import ResponseFormatter
        from app.schemas.requests import IntentType, LanguageCode
        result = ResponseFormatter.format(
            request_id="req-1",
            intent=IntentType.WEATHER,
            language=LanguageCode.HI,
            reply="Aaj mausam saaf hai.",
            session_id="sess-1",
            confidence={"overall": 92, "level": "very_high"},
        )
        assert result["success"] is True
        assert result["request_id"] == "req-1"
        assert "timestamp" in result
        assert result["confidence"]["overall"] == 92
        assert result["metadata"]["intent"] == "WEATHER"
        assert result["metadata"]["language"] == "hi"

    def test_format_error_has_correct_shape(self):
        from app.ai.response_formatter import ResponseFormatter
        result = ResponseFormatter.format_error(
            request_id="req-2",
            message="Something went wrong",
            code=500,
            error_detail="DB timeout",
        )
        assert result["success"] is False
        assert result["code"] == 500
        assert result["data"] is None
        assert result["confidence"] is None

    def test_format_includes_session_id_in_data(self):
        from app.ai.response_formatter import ResponseFormatter
        from app.schemas.requests import IntentType, LanguageCode
        result = ResponseFormatter.format(
            request_id="req-3",
            intent=IntentType.CHAT,
            language=LanguageCode.EN,
            reply="Hello farmer!",
            session_id="sess-abc",
        )
        assert result["data"]["session_id"] == "sess-abc"
        assert result["data"]["reply"] == "Hello farmer!"


# ══════════════════════════════════════════════════════════════════════════════
# ── Prompt Builder – Digital Twin Prompts ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class TestDigitalTwinPrompts:
    """Tests for the new Digital Twin-aware prompt builder functions."""

    class MockContext:
        def __init__(self, **kwargs):
            self.provider_data = kwargs.get("provider_data", {})
            self.provider_metadata = kwargs.get("provider_metadata", {})

    def test_field_intelligence_prompt_contains_ndvi(self):
        from app.ai.prompt_builder import build_digital_twin_prompt_from_context
        from app.schemas.requests import LanguageCode
        
        ctx = self.MockContext(
            provider_data={
                "digital_twin": {
                    "farmer": {"name": "Ramesh", "district": "Ahmedabad", "state": "Gujarat",
                            "preferred_language": "en", "primary_crops": ["wheat"]},
                    "field": {"name": "North Field", "area_ha": 2.5, "soil_type": "loamy",
                           "soil_ph": 6.5, "current_crop": "wheat",
                           "nitrogen_kg_ha": 60, "phosphorus_kg_ha": 40, "potassium_kg_ha": 40,
                           "irrigation_type": "drip", "water_source": "borewell",
                           "sowing_date": "2026-03-01", "expected_harvest_date": "2026-06-01",
                           "current_variety": "HD2967", "growth_stage": "flowering"}
                },
                "weather": {"current": {"temperature_c": 28, "condition": "Partly Cloudy",
                                     "humidity_pct": 65},
                         "forecast": [{"date": "2026-07-02", "condition": "Sunny",
                                       "temp_min_c": 22, "temp_max_c": 34,
                                       "rainfall_mm": 0}]},
                "satellite": {"ndvi": 0.62, "crop_health": "Good crop health",
                           "vegetation_index": 62.0,
                           "harvest_detection": "Grain fill / maturation stage",
                           "analysis_date": "2026-07-01"},
                "ml_inference": {
                    "yield_prediction": {"yield_kg_per_ha": 3200, "total_yield_kg": 8000,
                                   "confidence": 88, "category": "good"},
                    "disease_risk": {"risk_level": "MODERATE", "risk_score": 35.0,
                                  "confidence": 72.0, "common_diseases": ["Rust"],
                                  "preventive_actions": ["Scout field every 3 days",
                                                          "Apply preventive fungicide"]}
                }
            },
            provider_metadata={
                "digital_twin": {"source": "MongoDB", "freshness": "semi_static"},
                "satellite": {"source": "Sentinel-2 SR (GEE)", "freshness": "dynamic"}
            }
        )
        
        prompt = build_digital_twin_prompt_from_context(
            user_message="How is my crop doing?",
            language=LanguageCode.EN,
            ctx=ctx
        )
        # Verify key facts are injected
        assert "Ramesh" in prompt
        assert "North Field" in prompt
        assert "0.62" in prompt
        assert "Ndvi" in prompt  # The generic formatter capitalizes keys
        assert "3200" in prompt  # yield
        assert "MODERATE" in prompt   # disease risk
        assert "wheat" in prompt.lower()
        assert "English" in prompt

    def test_field_intelligence_prompt_with_water_stress(self):
        from app.ai.prompt_builder import build_digital_twin_prompt_from_context
        from app.schemas.requests import LanguageCode
        
        ctx = self.MockContext(
            provider_data={
                "ml_inference": {
                    "water_stress": {"stress_level": "severe", "irrigate_now": True,
                                  "water_need_mm": 45, "recommendation": "Irrigate immediately",
                                  "et_estimate_mm": 38.5, "rainfall_effective_mm": 0}
                }
            }
        )
        
        prompt = build_digital_twin_prompt_from_context(
            user_message="Should I irrigate today?",
            language=LanguageCode.HI,
            ctx=ctx
        )
        assert "severe" in prompt.lower()
        assert "45" in prompt
        assert "Hindi" in prompt

    def test_field_intelligence_prompt_without_field_data_still_works(self):
        from app.ai.prompt_builder import build_digital_twin_prompt_from_context
        from app.schemas.requests import LanguageCode
        
        ctx = self.MockContext(provider_data={})
        
        # Should not raise even if all optional data is missing
        prompt = build_digital_twin_prompt_from_context(
            user_message="What crop should I grow?",
            language=LanguageCode.EN,
            ctx=ctx
        )
        assert len(prompt) > 50
        assert "KrishiMitra" in prompt
