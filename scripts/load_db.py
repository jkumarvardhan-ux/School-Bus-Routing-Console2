#!/usr/bin/env python3
"""Rebuild school_bus.db from the CSV files in ../data.
Idempotent – drops and recreates tables.
Matches the exact columns produced by data_generator/generate_data.py.
"""
import csv
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from operations import init_schema

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "school_bus.db"

# Schema must match the CSV headers exactly
SCHEMA = {
    "AddressZone": """
        zone_id TEXT PRIMARY KEY,
        zone_name TEXT,
        centroid_lat REAL,
        centroid_lon REAL,
        is_approved INTEGER,
        school_district TEXT,
        created_at TEXT
    """,
    "Stop": """
        stop_id TEXT PRIMARY KEY,
        stop_name TEXT,
        lat REAL,
        lon REAL,
        address_zone_id TEXT,
        is_approved INTEGER,
        capacity_hint INTEGER,
        created_at TEXT
    """,
    "Bus": """
        bus_id TEXT PRIMARY KEY,
        plate_number TEXT,
        capacity INTEGER,
        accessible INTEGER,
        status TEXT,
        current_capacity_override INTEGER,
        created_at TEXT
    """,
    "Driver": """
        driver_id TEXT PRIMARY KEY,
        name TEXT,
        license_number TEXT,
        phone TEXT,
        status TEXT,
        hired_date TEXT,
        created_at TEXT
    """,
    "Student": """
        student_id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        grade INTEGER,
        date_of_birth TEXT,
        accessibility_needs TEXT,
        address_zone_id TEXT,
        is_active INTEGER,
        created_at TEXT,
        effective_from TEXT,
        effective_to TEXT,
        address_line TEXT,
        pickup_window_start TEXT,
        pickup_window_end TEXT
    """,
    "GuardianContact": """
        contact_id TEXT PRIMARY KEY,
        student_id TEXT,
        name TEXT,
        relationship TEXT,
        phone TEXT,
        email TEXT,
        is_primary INTEGER,
        is_valid INTEGER,
        created_at TEXT
    """,
    "Route": """
        route_id TEXT PRIMARY KEY,
        route_name TEXT,
        bus_id TEXT,
        driver_id TEXT,
        school_id TEXT,
        direction TEXT,
        is_active INTEGER,
        effective_from TEXT,
        effective_to TEXT,
        created_at TEXT
    """,
    "RouteStop": """
        route_stop_id TEXT PRIMARY KEY,
        route_id TEXT,
        stop_id TEXT,
        sequence INTEGER,
        planned_arrival_min INTEGER,
        travel_time_from_prev_min INTEGER,
        created_at TEXT,
        pickup_window_start TEXT,
        pickup_window_end TEXT
    """,
    "Assignment": """
        assignment_id TEXT PRIMARY KEY,
        student_id TEXT,
        route_id TEXT,
        stop_id TEXT,
        school_year TEXT,
        assigned_at TEXT,
        status TEXT,
        is_compatible INTEGER,
        notes TEXT
    """,
    "AttendanceEvent": """
        event_id TEXT PRIMARY KEY,
        student_id TEXT,
        assignment_id TEXT,
        event_date TEXT,
        status TEXT,
        recorded_at TEXT,
        notes TEXT
    """,
    "Notification": """
        notification_id TEXT PRIMARY KEY,
        student_id TEXT,
        contact_id TEXT,
        event_type TEXT,
        message TEXT,
        sent_at TEXT,
        delivery_status TEXT,
        related_event_id TEXT
    """,
    "ground_truth": """
        entity_type TEXT,
        entity_id TEXT,
        issue_type TEXT,
        description TEXT,
        expected_decision TEXT,
        severity TEXT
    """,
}

def coerce(v):
    if v is None or v == "":
        return None
    if v in ("True", "true", "1"):
        return 1
    if v in ("False", "false", "0"):
        return 0
    return v

def load_csv(table: str, conn: sqlite3.Connection) -> int:
    path = DATA / f"{table}.csv"
    if not path.exists():
        print(f"  skip {table} (no CSV)")
        return 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ",".join("?" * len(cols))
    col_list = ",".join(cols)
    data = [tuple(coerce(r[c]) for c in cols) for r in rows]
    conn.executemany(
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})", data
    )
    return len(data)

def main():
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(str(DB))
    for table, ddl in SCHEMA.items():
        conn.execute(f"CREATE TABLE {table} ({ddl})")
        n = load_csv(table, conn)
        print(f"  {table}: {n} rows")
    init_schema(conn)
    conn.commit()
    conn.close()
    print(f"Database written to {DB} (operational workflow schema included)")

if __name__ == "__main__":
    main()
