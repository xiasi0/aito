from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VehicleControl(StrEnum):
    AIR_CONDITIONER = "air_conditioner"
    RAPID_AIR_CONDITIONER = "rapid_air_conditioner"
    FRONT_DEFROST = "front_defrost"


@dataclass(frozen=True)
class ControlDefinition:
    """Verified APIG command contract, not an entity-registration rule."""

    client_method: str
    state_paths: tuple[tuple[str, ...], ...]


CONTROL_DEFINITIONS = {
    VehicleControl.AIR_CONDITIONER: ControlDefinition(
        client_method="control_air_conditioner",
        state_paths=(("hvac", "acStatus"),),
    ),
    VehicleControl.RAPID_AIR_CONDITIONER: ControlDefinition(
        client_method="control_air_conditioner_rapid",
        state_paths=(("hvac", "maxColdSwitch"), ("hvac", "maxHeatSwitch")),
    ),
    VehicleControl.FRONT_DEFROST: ControlDefinition(
        client_method="control_defrost",
        state_paths=(("hvac", "defrostStatus"),),
    ),
}
