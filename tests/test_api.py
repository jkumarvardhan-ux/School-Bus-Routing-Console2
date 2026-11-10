"""Lightweight smoke tests for the API layer using sqlite directly
(same queries the server executes).
"""
import sqlite3
from pathlib import Path

import pytest

DB = Path(__file__).resolve().parent.parent / "data" / "school_bus.db"

@pytest.fixture
def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    yield c
    c.close()

def test_stats_counts(conn):
    for table in ["Student", "Bus", "Route", "Assignment", "ground_truth"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert n > 0

def test_capacity_overview_query(conn):
    rows = conn.execute("""
        SELECT r.route_id, b.capacity,
               COUNT(a.assignment_id) as load
        FROM Route r
        JOIN Bus b ON r.bus_id = b.bus_id
        LEFT JOIN Assignment a ON a.route_id = r.route_id
        GROUP BY r.route_id
        LIMIT 5
    """).fetchall()
    assert len(rows) == 5
    for r in rows:
        assert r["load"] >= 0

def test_incompatible_flag_exists(conn):
    n = conn.execute("SELECT COUNT(*) FROM Assignment WHERE is_compatible = 0").fetchone()[0]
    assert n > 0

def test_ground_truth_severity(conn):
    rows = conn.execute("SELECT DISTINCT severity FROM ground_truth").fetchall()
    sevs = {r[0] for r in rows}
    assert "high" in sevs

def test_attendance_missed(conn):
    n = conn.execute("SELECT COUNT(*) FROM AttendanceEvent WHERE status = 'missed_pickup'").fetchone()[0]
    assert n > 0
