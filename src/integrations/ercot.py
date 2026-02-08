"""ERCOT grid data client for real-time grid conditions."""

import logging
from datetime import datetime

import httpx

from src.models.threat import ERCOTData

logger = logging.getLogger(__name__)

# ERCOT public data endpoints
ERCOT_BASE_URL = "https://www.ercot.com/api/1/services/read"
ERCOT_DASHBOARD_URL = "https://www.ercot.com/content/cdr/html"


class ERCOTClient:
    """Client for ERCOT grid data.

    Uses ERCOT's public data feeds for real-time grid conditions.
    Falls back to simulated data if API is unavailable.
    """

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=15.0)
        self._override: ERCOTData | None = None
        self._last_data: ERCOTData = ERCOTData()

    def set_override(self, data: ERCOTData) -> None:
        """Set simulation override for ERCOT data."""
        self._override = data

    def clear_override(self) -> None:
        """Clear simulation override."""
        self._override = None

    async def get_grid_conditions(self) -> ERCOTData:
        """Fetch current ERCOT grid conditions."""
        if self._override:
            return self._override

        try:
            # Try ERCOT's public grid info API
            data = await self._fetch_grid_data()
            self._last_data = data
            return data
        except Exception as e:
            logger.warning(f"ERCOT API error: {e}. Using last known data.")
            return self._last_data

    async def _fetch_grid_data(self) -> ERCOTData:
        """Fetch grid data from ERCOT public APIs."""
        try:
            # ERCOT real-time system conditions
            # Using the public dashboard data endpoint
            resp = await self._client.get(
                "https://www.ercot.com/api/1/services/read/dashboards/systemConditions",
                headers={
                    "User-Agent": "SmartHomeAgent/1.0",
                    "Accept": "application/json",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                return self._parse_system_conditions(data)

        except Exception as e:
            logger.debug(f"ERCOT system conditions API failed: {e}")

        # Fallback: try real-time LMP data
        try:
            resp = await self._client.get(
                "https://www.ercot.com/api/1/services/read/dashboards/realTimeMarket",
                headers={
                    "User-Agent": "SmartHomeAgent/1.0",
                    "Accept": "application/json",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                return self._parse_market_data(data)

        except Exception as e:
            logger.debug(f"ERCOT market data API failed: {e}")

        # Return default data if all APIs fail
        logger.warning("All ERCOT APIs unavailable, returning defaults")
        return ERCOTData(
            system_load_mw=45000,
            load_capacity_pct=65,
            lmp_price=25.0,
            operating_reserves_mw=3000,
            grid_alert_level="normal",
            timestamp=datetime.now(),
        )

    def _parse_system_conditions(self, data: dict) -> ERCOTData:
        """Parse ERCOT system conditions response."""
        try:
            # ERCOT API returns nested data
            conditions = data.get("data", data)
            if isinstance(conditions, list) and conditions:
                conditions = conditions[0]

            return ERCOTData(
                system_load_mw=float(conditions.get("systemLoad", 45000)),
                load_capacity_pct=float(conditions.get("loadPercent", 65)),
                lmp_price=float(conditions.get("lmp", 25)),
                operating_reserves_mw=float(conditions.get("operatingReserves", 3000)),
                grid_alert_level=self._determine_alert_level(conditions),
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error parsing ERCOT conditions: {e}")
            return ERCOTData(timestamp=datetime.now())

    def _parse_market_data(self, data: dict) -> ERCOTData:
        """Parse ERCOT real-time market data."""
        try:
            market = data.get("data", data)
            if isinstance(market, list) and market:
                market = market[0]

            lmp = float(market.get("settlementPointPrice", 25))
            return ERCOTData(
                lmp_price=lmp,
                grid_alert_level="normal" if lmp < 100 else "elevated",
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error parsing ERCOT market data: {e}")
            return ERCOTData(timestamp=datetime.now())

    @staticmethod
    def _determine_alert_level(conditions: dict) -> str:
        """Determine grid alert level from conditions."""
        reserves = float(conditions.get("operatingReserves", 3000))
        load_pct = float(conditions.get("loadPercent", 65))

        if reserves < 1000 or load_pct > 95:
            return "eea3"  # Emergency level 3
        elif reserves < 2000 or load_pct > 90:
            return "eea2"
        elif reserves < 2750 or load_pct > 85:
            return "eea1"
        elif load_pct > 80:
            return "conservation"
        elif load_pct > 70:
            return "elevated"
        return "normal"

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
ercot_client = ERCOTClient()
