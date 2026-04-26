from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class NodeType(str, Enum):
    PORT = "port"
    WAREHOUSE = "warehouse"
    HUB = "hub"


class EdgeMode(str, Enum):
    SEA = "sea"
    RAIL = "rail"
    TRUCK = "truck"
    AIR = "air"


class Status(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class Priority(str, Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    CRITICAL = "critical"


class DisruptionSource(str, Enum):
    MANUAL = "manual"
    WEATHER = "weather"
    NEWS = "news"


class DisruptionTarget(str, Enum):
    NODE = "node"
    EDGE = "edge"


class Node(BaseModel):
    id: str
    type: NodeType
    lat: float
    lon: float
    name: str
    country: str
    capacity: int
    current_load: int = 0
    status: Status = Status.NORMAL


class Edge(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    mode: EdgeMode
    base_transit_mean_hours: float = Field(gt=0)
    base_transit_sigma: float = Field(gt=0, default=0.15)
    cost_per_unit: float = Field(ge=0)
    status: Status = Status.NORMAL


class Shipment(BaseModel):
    id: str
    source_node_id: str
    destination_node_id: str
    path: list[str]
    current_node_id: str
    priority: Priority = Priority.STANDARD
    sla_deadline: datetime
    volume: int = 1


class Disruption(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    target_type: DisruptionTarget
    target_id: str
    severity: float = Field(ge=0.0, le=1.0)
    expected_duration_mean_hours: float = Field(gt=0)
    expected_duration_sigma_hours: float = Field(gt=0)
    source: DisruptionSource
    created_at: datetime


class ScenarioBucket(BaseModel):
    label: Literal["optimistic", "expected", "pessimistic"] | str
    probability: float
    eta: datetime


class ETAForecast(BaseModel):
    shipment_id: str
    p10: datetime
    p50: datetime
    p90: datetime
    scenarios: list[ScenarioBucket]
    cascade_impact_ids: list[str] = []
