"""Describe the logistics table so the agent writes correct SQL."""

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

TABLE_NAME = "logistics"

# Meaning and value range of each column, taken from data/logistics.csv.
# Ranges are observed values, not guaranteed constraints.
COLUMN_NOTES = {
    "timestamp": "hourly reading time, 2021 onward (may be stored as text; use CAST(timestamp AS timestamp) for date math)",
    "vehicle_gps_latitude": "vehicle latitude, about 30 to 50",
    "vehicle_gps_longitude": "vehicle longitude, about -120 to -70",
    "fuel_consumption_rate": "about 5 to 20",
    "eta_variation_hours": "ETA change in hours, about -2 to 5",
    "traffic_congestion_level": "0 to 10",
    "warehouse_inventory_level": "0 to 1000",
    "loading_unloading_time": "hours, about 0.5 to 5",
    "handling_equipment_availability": "score 0 to 1",
    "order_fulfillment_status": "score 0 to 1 (not a text status)",
    "weather_condition_severity": "score 0 to 1",
    "port_congestion_level": "0 to 10",
    "shipping_costs": "about 100 to 1000",
    "supplier_reliability_score": "score 0 to 1",
    "lead_time_days": "about 1 to 15",
    "historical_demand": "about 100 to 10000",
    "iot_temperature": "sensor temperature in C, about -10 to 40",
    "cargo_condition_status": "score 0 to 1 (not a text status)",
    "route_risk_level": "score 0 to 10 (not a text label)",
    "customs_clearance_time": "hours, about 0.5 to 5",
    "driver_behavior_score": "score 0 to 1",
    "fatigue_monitoring_score": "score 0 to 1",
    "disruption_likelihood_score": "score 0 to 1",
    "delay_probability": "probability 0 to 1",
    "risk_classification": "text: 'High Risk', 'Moderate Risk' or 'Low Risk'",
    "delivery_time_deviation": "hours, about -2 to 10",
}

# Used when the live schema cannot be read (database down or no access).
FALLBACK_COLUMNS = [
    (name, "text" if name in ("timestamp", "risk_classification")
     else "double precision")
    for name in COLUMN_NOTES
]

_cached_schema = None


def format_schema(columns, source):
    """Build a prompt-ready description from (name, type) pairs."""

    lines = [
        f"Table: {TABLE_NAME} ({source} schema). "
        "One row per hourly vehicle reading. "
        "There is no shipment ID or primary key column.",
        "Columns:",
    ]

    for name, data_type in columns:
        note = COLUMN_NOTES.get(name)
        suffix = f" - {note}" if note else ""
        lines.append(f"- {name} ({data_type}){suffix}")

    lines.append(
        "Use only these column names. Do not guess others. "
        "Always add LIMIT (50 or fewer) to queries that return rows."
    )

    return "\n".join(lines)


def _read_live_columns(engine):
    query = text(
        "SELECT column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = current_schema() "
        "AND table_name = :table "
        "ORDER BY ordinal_position"
    )

    with engine.connect() as connection:
        rows = connection.execute(query, {"table": TABLE_NAME}).fetchall()

    return [(row[0], row[1]) for row in rows]


def get_schema_text(engine=None):
    """Return the schema description, cached after the first live read."""

    global _cached_schema

    if _cached_schema is not None:
        return _cached_schema

    try:
        if engine is None:
            from tools.sql_tool import engine as default_engine

            engine = default_engine

        columns = _read_live_columns(engine)

        if not columns:
            raise RuntimeError("logistics table not found")

        _cached_schema = format_schema(columns, "live")
        return _cached_schema

    except Exception:
        logger.exception("Live schema read failed; using fallback schema")
        # Not cached, so the next call retries the live read.
        return format_schema(FALLBACK_COLUMNS, "fallback")


def reset_schema_cache():
    global _cached_schema
    _cached_schema = None
