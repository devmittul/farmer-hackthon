"""
KrishiMitra Backend – Pydantic Schemas
========================================
All request/response schemas for the API layer.
"""
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Enumerations ──────────────────────────────────────────────────────────────
class IntentType(str, Enum):
    """Detected intent types from user messages."""
    CHAT = "CHAT"
    WEATHER = "WEATHER"
    ROUTE = "ROUTE"
    CROP = "CROP"
    VEHICLE = "VEHICLE"
    COURIER = "COURIER"
    SOS = "SOS"
    MARKET = "MARKET"
    VOICE = "VOICE"
    IMAGE = "IMAGE"
    UNKNOWN = "UNKNOWN"


class LanguageCode(str, Enum):
    """Supported language codes."""
    EN = "en"
    HI = "hi"
    GU = "gu"
    PA = "pa"
    MR = "mr"
    TA = "ta"
    TE = "te"
    KN = "kn"
    ML = "ml"
    BN = "bn"


class SoilType(str, Enum):
    SANDY = "sandy"
    LOAMY = "loamy"
    CLAY = "clay"
    SILTY = "silty"
    PEATY = "peaty"
    CHALKY = "chalky"
    RED = "red"
    BLACK = "black"
    ALLUVIAL = "alluvial"


class CourierStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# ── Auth Schemas ──────────────────────────────────────────────────────────────
class UserRegisterRequest(BaseModel):
    """User registration payload."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., pattern=r"^\+?[1-9]\d{9,14}$")
    password: str = Field(..., min_length=8, max_length=128)
    language: LanguageCode = Field(default=LanguageCode.EN)
    location: Optional[str] = Field(default=None)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    """User login payload."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# ── Chat Schemas ──────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    """Incoming chat message payload."""
    message: str = Field(..., min_length=1, max_length=2000)
    language: Optional[LanguageCode] = Field(default=None)
    location: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    field_id: Optional[str] = Field(default=None, description="Field Digital Twin ID for field-specific context")

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        # Strip leading/trailing whitespace and collapse multiple spaces
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        # Basic prompt injection guard: remove common injection patterns
        dangerous = ["ignore previous", "disregard all", "system prompt", "jailbreak"]
        lower = v.lower()
        for pattern in dangerous:
            if pattern in lower:
                raise ValueError("Message contains disallowed content")
        return v


class ChatResponse(BaseModel):
    """Structured chat response."""
    reply: str
    intent: IntentType
    language: LanguageCode
    data: Optional[dict[str, Any]] = None
    audio_url: Optional[str] = None
    session_id: str


# ── Crop Schemas ──────────────────────────────────────────────────────────────
class CropPredictRequest(BaseModel):
    """Crop recommendation request."""
    nitrogen: float = Field(..., ge=0, le=200, description="N in kg/ha")
    phosphorus: float = Field(..., ge=0, le=200, description="P in kg/ha")
    potassium: float = Field(..., ge=0, le=200, description="K in kg/ha")
    temperature: float = Field(..., ge=-10, le=60, description="°C")
    humidity: float = Field(..., ge=0, le=100, description="%")
    ph: float = Field(..., ge=0, le=14, description="Soil pH")
    rainfall: float = Field(..., ge=0, le=5000, description="mm/year")
    soil_type: Optional[SoilType] = Field(default=None)
    location: Optional[str] = Field(default=None)
    language: LanguageCode = Field(default=LanguageCode.EN)


class CropPredictResponse(BaseModel):
    """Crop recommendation output."""
    recommended_crop: str
    confidence: float
    alternatives: List[str]
    explanation: str
    tips: List[str]


# ── Vehicle Schemas ───────────────────────────────────────────────────────────
class VehiclePredictRequest(BaseModel):
    """Vehicle demand prediction request."""
    location: str = Field(..., min_length=2)
    crop_type: str = Field(..., min_length=2)
    quantity_tonnes: float = Field(..., gt=0)
    destination: str = Field(..., min_length=2)
    date: str = Field(..., description="YYYY-MM-DD")
    language: LanguageCode = Field(default=LanguageCode.EN)


class VehiclePredictResponse(BaseModel):
    """Vehicle demand prediction output."""
    demand_level: str
    recommended_vehicles: List[str]
    estimated_cost_inr: dict[str, float]
    best_time_window: str
    explanation: str


# ── Route Schemas ─────────────────────────────────────────────────────────────
class RoutePlanRequest(BaseModel):
    """Route planning request."""
    origin: str = Field(..., min_length=2)
    destination: str = Field(..., min_length=2)
    vehicle_type: Optional[str] = Field(default="car")
    cargo: Optional[str] = Field(default=None)
    language: LanguageCode = Field(default=LanguageCode.EN)


class RouteStep(BaseModel):
    instruction: str
    distance_km: float
    duration_min: float


class RoutePlanResponse(BaseModel):
    """Route planning output."""
    origin_coords: dict[str, float]
    destination_coords: dict[str, float]
    total_distance_km: float
    total_duration_min: float
    steps: List[RouteStep]
    road_quality_advisory: Optional[str] = None
    explanation: str


# ── Weather Schemas ───────────────────────────────────────────────────────────
class WeatherRequest(BaseModel):
    """Weather query request."""
    location: str = Field(..., min_length=2)
    days: int = Field(default=3, ge=1, le=7)
    language: LanguageCode = Field(default=LanguageCode.EN)
    force_refresh: bool = Field(default=False)


class WeatherDay(BaseModel):
    date: str
    temp_min_c: float
    temp_max_c: float
    humidity_pct: float
    rainfall_mm: float
    wind_kmh: float
    condition: str


class WeatherResponse(BaseModel):
    """Weather data output."""
    location: str
    latitude: float
    longitude: float
    current: dict[str, Any]
    forecast: List[WeatherDay]
    advisory: str
    explanation: str


# ── Courier Schemas ───────────────────────────────────────────────────────────
class CourierCreateRequest(BaseModel):
    """Community courier creation request."""
    pickup_location: str = Field(..., min_length=2)
    delivery_location: str = Field(..., min_length=2)
    cargo_description: str = Field(..., min_length=5, max_length=500)
    weight_kg: float = Field(..., gt=0, le=5000)
    preferred_date: str = Field(..., description="YYYY-MM-DD")
    contact_phone: str = Field(..., pattern=r"^\+?[1-9]\d{9,14}$")


class CourierListResponse(BaseModel):
    """Single courier listing in list endpoint."""
    id: str
    pickup_location: str
    delivery_location: str
    cargo_description: str
    weight_kg: float
    preferred_date: str
    status: CourierStatus
    created_at: datetime


# ── SOS Schemas ───────────────────────────────────────────────────────────────
class SOSRequest(BaseModel):
    """Emergency SOS alert request."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    description: str = Field(..., min_length=5, max_length=500)
    emergency_type: str = Field(default="general")
    contact_phone: Optional[str] = Field(default=None)


class SOSResponse(BaseModel):
    """SOS alert confirmation."""
    alert_id: str
    message: str
    nearest_help: Optional[str] = None
    emergency_contacts: List[str] = []
