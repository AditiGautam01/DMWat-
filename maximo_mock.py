"""
maximo_mock.py
==============
Synthetic Maximo data generator for local development and demos.

Produces realistic work orders, assets, and service requests that mirror
the shape of real IBM Maximo OSLC API responses. Supports both batch and
streaming (async generator) output so the frontend can consume records
as they "arrive" from a simulated data pipeline.

Usage:
    from maximo_mock import MockMaximoClient
    client = MockMaximoClient()
    orders = client.get_work_orders(limit=20)       # Batch
    async for record in client.stream_work_orders(): # Stream
        print(record)
"""

import random
import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator

# ---------------------------------------------------------------------------
# Seed data pools — curated for a realistic industrial / facilities scenario
# ---------------------------------------------------------------------------

_LOCATIONS = [
    "BLDG-100", "BLDG-200", "BLDG-300", "PLANT-A", "PLANT-B",
    "WAREHOUSE-1", "WAREHOUSE-2", "SUBSTATION-01", "SUBSTATION-02",
    "OFFICE-N", "OFFICE-S", "COOLING-TOWER-1", "BOILER-ROOM",
    "MAINT-SHOP", "PARKING-DECK", "DATA-CENTER-1", "DATA-CENTER-2",
]

_ASSET_PREFIXES = [
    ("PUMP", "Centrifugal Pump"),
    ("COMP", "Air Compressor"),
    ("CONV", "Belt Conveyor"),
    ("XFMR", "Power Transformer"),
    ("CHIL", "Industrial Chiller"),
    ("GENR", "Diesel Generator"),
    ("HVAC", "HVAC Unit"),
    ("ELEV", "Passenger Elevator"),
    ("FIRE", "Fire Suppression Panel"),
    ("CRANE", "Overhead Crane"),
    ("MOTOR", "Induction Motor"),
    ("VLV", "Control Valve"),
    ("TANK", "Storage Tank"),
    ("UPS", "Uninterruptible Power Supply"),
    ("AHU", "Air Handling Unit"),
]

_MANUFACTURERS = [
    "ABB", "Siemens", "GE Industrial", "Honeywell", "Emerson",
    "Schneider Electric", "Caterpillar", "Trane", "Carrier",
    "Daikin", "Grundfos", "Parker Hannifin", "Rockwell Automation",
]

_WO_DESCRIPTIONS = [
    "Routine preventive maintenance — lubrication and filter replacement",
    "Corrective repair: abnormal vibration detected during inspection",
    "Emergency repair — complete motor failure, production line stopped",
    "Scheduled calibration of pressure sensors and flow meters",
    "Replace worn drive belt; belt showing signs of cracking",
    "Inspect and clean cooling coils; performance degradation noted",
    "Quarterly electrical panel thermography scan",
    "Replenish refrigerant charge; system running low on R-410A",
    "Annual safety inspection per OSHA requirements",
    "Bearing replacement — elevated temperature readings on bearing #2",
    "Install new VFD (variable frequency drive) for energy savings",
    "Investigate intermittent tripping of circuit breaker CB-42",
    "Steam trap survey and replacement of failed traps",
    "Alignment check and correction after motor reinstallation",
    "Replace corroded section of chilled water piping",
    "Re-lamp exterior lighting — LED retrofit project Phase 2",
    "Fire alarm panel firmware upgrade to v4.2.1",
    "Test and certify emergency generator under full load",
    "Oil sampling and analysis for transformer XFMR-004",
    "HVAC duct cleaning and IAQ assessment for Building 200",
    "Elevator annual load test and safety certification",
    "Conveyor belt tracking adjustment — belt drifting left",
    "Welding repair on structural steel support bracket",
    "Replace faulty solenoid valve on boiler feedwater system",
    "Commission new chiller unit CHIL-008 — startup procedure",
]

_WO_STATUSES = [
    ("WAPPR", 0.10),   # Waiting for Approval
    ("APPR", 0.15),    # Approved
    ("INPRG", 0.30),   # In Progress
    ("WMATL", 0.10),   # Waiting on Material
    ("WSCH", 0.05),    # Waiting to be Scheduled
    ("COMP", 0.25),    # Completed
    ("CLOSE", 0.05),   # Closed
]

_ASSET_STATUSES = [
    ("OPERATING", 0.60),
    ("NOT READY", 0.10),
    ("INACTIVE", 0.05),
    ("DECOMMISSIONED", 0.05),
    ("BROKEN", 0.08),
    ("MISSING", 0.02),
    ("OPERATING", 0.10),  # duplicate weight to skew towards operating
]

_SR_DESCRIPTIONS = [
    "Water leak reported in restroom 2nd floor Building 100",
    "Temperature too high in server room — HVAC appears offline",
    "Parking lot light pole #7 is not working",
    "Noise complaint: loud banging from ductwork in conference room B",
    "Elevator stuck on 3rd floor — occupants safely exited",
    "Broken window in east stairwell — security hazard",
    "Foul odor in lobby — possible drain issue",
    "Office 314 — electrical outlet sparking when appliance plugged in",
    "Loading dock door #3 will not close, motor seems jammed",
    "Cafeteria dishwasher leaking — floor wet and slippery",
    "Badge reader at entrance G not scanning properly",
    "Emergency exit sign light burned out in hallway C",
    "Roof leak during heavy rain — water stains on ceiling tiles",
    "Pest sighting reported in warehouse storage area B",
    "Gas smell near boiler room — requesting immediate inspection",
]

_SR_STATUSES = [
    ("NEW", 0.20),
    ("QUEUED", 0.15),
    ("INPROG", 0.30),
    ("PENDING", 0.10),
    ("RESOLVED", 0.20),
    ("CLOSED", 0.05),
]

_REPORTED_BY = [
    "JSMITH", "MGARCIA", "AWILSON", "RJOHNSON", "KLEE",
    "TBROWN", "PATEL", "NDAVIS", "OMARTIN", "CWHITE",
    "HTAYLOR", "FANDERSON", "LTHOMAS", "DJACKSON", "BMOORE",
]

_WORK_TYPES = ["CM", "PM", "EM", "CAL", "CP"]
_PRIORITIES = [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _weighted_choice(options: list[tuple[str, float]]) -> str:
    """Pick a value from [(value, weight), ...] using weights as probabilities."""
    values, weights = zip(*options)
    return random.choices(values, weights=weights, k=1)[0]


def _random_date(days_back: int = 180) -> str:
    """ISO-format date within the last N days."""
    delta = timedelta(days=random.randint(0, days_back))
    dt = datetime.now() - delta
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _generate_work_order(index: int) -> dict:
    """Generate a single synthetic work order record."""
    wonum = f"WO-{1000 + index:05d}"
    asset_prefix, asset_desc = random.choice(_ASSET_PREFIXES)
    assetnum = f"{asset_prefix}-{random.randint(1, 50):03d}"
    location = random.choice(_LOCATIONS)
    status = _weighted_choice(_WO_STATUSES)
    report_date = _random_date(days_back=120)
    target_start = _random_date(days_back=30)

    return {
        "wonum": wonum,
        "description": random.choice(_WO_DESCRIPTIONS),
        "status": status,
        "statusdate": report_date,
        "reportdate": report_date,
        "assetnum": assetnum,
        "location": location,
        "worktype": random.choice(_WORK_TYPES),
        "wopriority": random.choice(_PRIORITIES),
        "targstartdate": target_start,
        "estdur": round(random.uniform(0.5, 40.0), 1),
        "actlabcost": round(random.uniform(50, 5000), 2) if status in ("COMP", "CLOSE", "INPRG") else 0.0,
        "actmatlcost": round(random.uniform(0, 3000), 2) if status in ("COMP", "CLOSE") else 0.0,
        "_synthetic": True,
    }


def _generate_asset(index: int) -> dict:
    """Generate a single synthetic asset record."""
    prefix, description = _ASSET_PREFIXES[index % len(_ASSET_PREFIXES)]
    assetnum = f"{prefix}-{random.randint(1, 80):03d}"
    serial = f"SN-{random.randint(100000, 999999)}"
    install_date = _random_date(days_back=365 * 3)

    return {
        "assetnum": assetnum,
        "description": f"{description} — Unit {index + 1}",
        "status": _weighted_choice(_ASSET_STATUSES),
        "location": random.choice(_LOCATIONS),
        "manufacturer": random.choice(_MANUFACTURERS),
        "serialnum": serial,
        "installdate": install_date,
        "priority": random.choice(_PRIORITIES),
        "totdowntime": round(random.uniform(0, 200), 1),
        "ytdcost": round(random.uniform(100, 25000), 2),
        "_synthetic": True,
    }


def _generate_service_request(index: int) -> dict:
    """Generate a single synthetic service request (ticket)."""
    ticketid = f"SR-{2000 + index:05d}"
    return {
        "ticketid": ticketid,
        "description": random.choice(_SR_DESCRIPTIONS),
        "status": _weighted_choice(_SR_STATUSES),
        "reportdate": _random_date(days_back=60),
        "reportedby": random.choice(_REPORTED_BY),
        "affectedperson": random.choice(_REPORTED_BY),
        "location": random.choice(_LOCATIONS),
        "urgency": random.choice(_PRIORITIES),
        "_synthetic": True,
    }


# ===========================================================================
# Mock Client — drop-in replacement for MaximoClient
# ===========================================================================
class MockMaximoClient:
    """
    Simulates Maximo integration by pulling real Aircraft Predictive Maintenance (APM)
    data from Db2 and mapping it to Maximo objects (Work Orders, Assets, SRs).
    """

    def __init__(self):
        random.seed(42)

    def _fetch_db2_apm(self, limit: int = 50) -> list[dict]:
        """Helper to fetch rows from the real AIRCRAFT_PREDICTIVE_MAINTENANCE table."""
        try:
            from db2_watsonx_pipeline import db2_connect, db2_query
            conn = db2_connect()
            try:
                # Ask db2_query for slightly more rows so if we need, we have them
                sql = f'SELECT * FROM AIRCRAFT_PREDICTIVE_MAINTENANCE FETCH FIRST {limit} ROWS ONLY'
                rows = db2_query(conn, sql, max_rows=limit)
                return rows
            finally:
                import ibm_db
                ibm_db.close(conn)
        except Exception as e:
            print(f"Error fetching APM from DB2: {e}")
            return []

    def get_work_orders(self, limit: int = 50) -> list[dict]:
        """Return a batch of work orders mapped from DB2 APM data."""
        rows = self._fetch_db2_apm(limit)
        results = []
        for row in rows:
            results.append({
                "wonum": "WO-" + str(row.get("RECORD_ID", "1000")),
                "description": f"[{row.get('SYSTEM_NAME', 'SYS')} - {row.get('COMPONENT_NAME', 'COMP')}] {row.get('RECOMMENDED_ACTION', 'Inspect')}",
                "status": str(row.get("STATUS", "COMPLETED")).upper(),
                "statusdate": str(row.get("RECORDED_AT", "")),
                "reportdate": str(row.get("CREATED_AT", "")),
                "assetnum": str(row.get("AIRCRAFT_ID", "")),
                "location": str(row.get("BASE_AIRPORT", "")),
                "worktype": "PM" if "predictive" in str(row.get("ML_MODEL_USED", "")).lower() else "CM",
                "wopriority": row.get("SEVERITY_LEVEL", 3),
                "targstartdate": str(row.get("NEXT_SCHEDULED_MAINT", "")),
                "estdur": float(row.get("RUL_HOURS", 10.0)),
                "actlabcost": float(str(row.get("ANOMALY_SCORE", 0))) * 100,
                "actmatlcost": 0.0,
                "_synthetic": False,
                "_db2_source": "AIRCRAFT_PREDICTIVE_MAINTENANCE"
            })
        return results

    def get_assets(self, limit: int = 50) -> list[dict]:
        """Return a batch of assets mapped from DB2 APM data."""
        rows = self._fetch_db2_apm(limit)
        results = []
        for i, row in enumerate(rows):
            status = "OPERATING"
            if str(row.get("STATUS")).upper() in ["CRITICAL", "FAILED"]:
                status = "BROKEN"

            results.append({
                "assetnum": str(row.get("AIRCRAFT_ID", f"AC-{i}")),
                "description": f"{row.get('AIRCRAFT_TYPE', 'Aircraft')} - Tail {row.get('TAIL_NUMBER', '')}",
                "status": status,
                "location": str(row.get("BASE_AIRPORT", "")),
                "manufacturer": str(row.get("AIRLINE_CODE", "")),
                "serialnum": str(row.get("TAIL_NUMBER", "")),
                "installdate": str(row.get("CREATED_AT", "")),
                "priority": row.get("SEVERITY_LEVEL", 3),
                "totdowntime": float(row.get("FLIGHT_HOURS", 0)),
                "ytdcost": 0.0,
                "_synthetic": False,
                "_db2_source": "AIRCRAFT_PREDICTIVE_MAINTENANCE"
            })
        return results

    def get_service_requests(self, limit: int = 50) -> list[dict]:
        """Return a batch of service requests mapped from DB2 APM data."""
        rows = self._fetch_db2_apm(limit)
        results = []
        for i, row in enumerate(rows):
            results.append({
                "ticketid": "SR-" + str(row.get("RECORD_ID", f"{2000+i}")),
                "description": f"Alert: {row.get('ALERT_TYPE', 'General')} on {row.get('SYSTEM_NAME', 'System')}. Remarks: {row.get('REMARKS', '')}",
                "status": str(row.get("STATUS", "NEW")).upper(),
                "reportdate": str(row.get("RECORDED_AT", "")),
                "reportedby": str(row.get("TECHNICIAN_ID", "SYSTEM")),
                "affectedperson": str(row.get("TECHNICIAN_ID", "SYSTEM")),
                "location": str(row.get("BASE_AIRPORT", "")),
                "urgency": row.get("SEVERITY_LEVEL", 3),
                "_synthetic": False,
                "_db2_source": "AIRCRAFT_PREDICTIVE_MAINTENANCE"
            })
        return results

    def get_work_order(self, wonum: str) -> dict:
        """Return a specific work order by number."""
        all_orders = self.get_work_orders(200)
        for wo in all_orders:
            if wo["wonum"] == wonum:
                return wo
        return {}

    # -----------------------------------------------------------------------
    # Streaming generators — async generators that yield records with delay
    # -----------------------------------------------------------------------
    async def stream_work_orders(
        self, limit: int = 50, delay_ms: tuple[int, int] = (80, 400)
    ) -> AsyncGenerator[dict, None]:
        """Yield work orders one at a time with a simulated network delay."""
        orders = self.get_work_orders(limit)
        for order in orders:
            await asyncio.sleep(random.randint(*delay_ms) / 1000.0)
            yield order

    async def stream_assets(
        self, limit: int = 50, delay_ms: tuple[int, int] = (80, 400)
    ) -> AsyncGenerator[dict, None]:
        """Yield assets one at a time with a simulated network delay."""
        assets = self.get_assets(limit)
        for asset in assets:
            await asyncio.sleep(random.randint(*delay_ms) / 1000.0)
            yield asset

    async def stream_service_requests(
        self, limit: int = 50, delay_ms: tuple[int, int] = (80, 400)
    ) -> AsyncGenerator[dict, None]:
        """Yield service requests one at a time with a simulated delay."""
        srs = self.get_service_requests(limit)
        for sr in srs:
            await asyncio.sleep(random.randint(*delay_ms) / 1000.0)
            yield sr

    # -----------------------------------------------------------------------
    # Db2 → Maximo enrichment — correlate Db2 rows with Maximo records
    # -----------------------------------------------------------------------
    def enrich_from_db2(self, db2_rows: list[dict], entity_type: str = "workorders") -> list[dict]:
        """
        Since Maximo data is ALREADY Db2 data in this iteration, we just return
        the corresponding entities and attach the db2_source metadata.
        """
        enriched = []
        limit = len(db2_rows)
        if entity_type == "workorders":
            records = self.get_work_orders(limit)
        elif entity_type == "assets":
            records = self.get_assets(limit)
        elif entity_type == "service_requests":
            records = self.get_service_requests(limit)
        else:
            records = self.get_work_orders(limit)
            
        for i, (db2_row, record) in enumerate(zip(db2_rows, records)):
            keys = list(db2_row.keys())
            # Basic fallback mapping just to show linking
            record["db2_source"] = {
                "id": str(db2_row.get(keys[0], f"ID-{i}")) if keys else f"ID-{i}"
            }
            enriched.append(record)
        return enriched

    async def stream_enriched(
        self,
        db2_rows: list[dict],
        entity_type: str = "workorders",
        delay_ms: tuple[int, int] = (100, 500),
    ) -> AsyncGenerator[dict, None]:
        enriched = self.enrich_from_db2(db2_rows, entity_type)
        for record in enriched:
            await asyncio.sleep(random.randint(*delay_ms) / 1000.0)
            yield record

# ===========================================================================
# Quick CLI demo
# ===========================================================================
if __name__ == "__main__":
    import json

    mock = MockMaximoClient()

    print("=" * 60)
    print("  DB2-Backed Maximo Data — Batch Demo")
    print("=" * 60)

    for label, records in [
        ("Work Orders", mock.get_work_orders(5)),
        ("Assets", mock.get_assets(5)),
        ("Service Requests", mock.get_service_requests(5)),
    ]:
        print(f"\\n--- {label} ({len(records)} records) ---")
        for r in records:
            print(json.dumps(r, indent=2))

