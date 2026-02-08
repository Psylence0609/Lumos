"""MQTT topic constants and helpers."""


class Topics:
    """MQTT topic structure for the smart home system."""

    # Device topics
    DEVICE_STATE = "smarthome/devices/{device_id}/state"
    DEVICE_COMMAND = "smarthome/devices/{device_id}/command"
    DEVICE_TELEMETRY = "smarthome/devices/{device_id}/telemetry"

    # Agent topics
    AGENT_STATUS = "smarthome/agents/{agent_id}/status"

    # Threat assessment
    THREAT_ASSESSMENT = "smarthome/threats/assessment"

    # Patterns
    PATTERN_DETECTED = "smarthome/patterns/detected"

    # Energy
    ENERGY_SUMMARY = "smarthome/energy/summary"

    # Simulation overrides
    SIMULATION_OVERRIDE = "smarthome/simulation/override"

    # System events
    SYSTEM_EVENTS = "smarthome/system/events"

    @staticmethod
    def device_state(device_id: str) -> str:
        return Topics.DEVICE_STATE.format(device_id=device_id)

    @staticmethod
    def device_command(device_id: str) -> str:
        return Topics.DEVICE_COMMAND.format(device_id=device_id)

    @staticmethod
    def device_telemetry(device_id: str) -> str:
        return Topics.DEVICE_TELEMETRY.format(device_id=device_id)

    @staticmethod
    def agent_status(agent_id: str) -> str:
        return Topics.AGENT_STATUS.format(agent_id=agent_id)
