CREATE TABLE logistics (
    id BIGSERIAL PRIMARY KEY,

    timestamp TIMESTAMP,
    vehicle_id VARCHAR(100),

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    fuel_consumption_rate DOUBLE PRECISION,
    eta_hours DOUBLE PRECISION,

    traffic_congestion_level DOUBLE PRECISION,
    warehouse_inventory_level DOUBLE PRECISION,

    loading_unloading_time DOUBLE PRECISION,
    equipment_available BOOLEAN,

    order_fulfillment_status VARCHAR(50),

    weather_severity VARCHAR(50),
    port_congestion_level DOUBLE PRECISION,

    shipping_cost DOUBLE PRECISION,
    supplier_reliability DOUBLE PRECISION,
    lead_time DOUBLE PRECISION,

    historic_demand DOUBLE PRECISION,

    iot_temperature DOUBLE PRECISION,
    cargo_condition VARCHAR(50),

    route_risk_level VARCHAR(50),
    customs_clearance_time DOUBLE PRECISION,

    driver_behavior_score DOUBLE PRECISION,
    fatigue_score DOUBLE PRECISION,

    disruption_likelihood DOUBLE PRECISION,
    delay_probability DOUBLE PRECISION,

    risk_classification VARCHAR(50)
);