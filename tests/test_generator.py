"""Validation tests against the generated data artifacts."""
import csv
import json
from pathlib import Path
from collections import Counter

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

def load_csv(name):
    with open(DATA / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

@pytest.fixture(scope="module")
def tables():
    names = [
        "Student", "GuardianContact", "AddressZone", "Stop", "Bus", "Driver",
        "Route", "RouteStop", "Assignment", "AttendanceEvent", "Notification", "ground_truth"
    ]
    return {n: load_csv(n) for n in names}

def test_volume_targets(tables):
    assert len(tables["Student"]) == 5000
    assert len(tables["Bus"]) == 100
    assert len(tables["Stop"]) == 300
    assert len(tables["Route"]) == 150
    assert len(tables["Assignment"]) >= 4900

def test_primary_keys_unique(tables):
    for table, rows in tables.items():
        if table == "ground_truth":
            continue
        if not rows:
            continue
        pk = list(rows[0].keys())[0]
        ids = [r[pk] for r in rows]
        assert len(ids) == len(set(ids)), f"Duplicate PK in {table}"

def test_id_nomenclature(tables):
    assert all(r["student_id"].startswith("STU-") for r in tables["Student"])
    assert all(r["stop_id"].startswith("STOP-") for r in tables["Stop"])
    assert all(r["bus_id"].startswith("BUS-") for r in tables["Bus"])
    assert all(r["route_id"].startswith("ROUTE-2026-") for r in tables["Route"])
    assert all(r["assignment_id"].startswith("ASN-STU-") for r in tables["Assignment"])
    assert all(r["notification_id"].startswith("NOT-2026-") for r in tables["Notification"])

def test_foreign_keys(tables):
    zones = {r["zone_id"] for r in tables["AddressZone"]}
    stops = {r["stop_id"] for r in tables["Stop"]}
    buses = {r["bus_id"] for r in tables["Bus"]}
    routes = {r["route_id"] for r in tables["Route"]}
    students = {r["student_id"] for r in tables["Student"]}

    for r in tables["Student"]:
        assert r["address_zone_id"] in zones
    for r in tables["Stop"]:
        assert r["address_zone_id"] in zones
    for r in tables["Route"]:
        assert r["bus_id"] in buses
    for r in tables["RouteStop"]:
        assert r["route_id"] in routes
        assert r["stop_id"] in stops
    for r in tables["Assignment"]:
        assert r["student_id"] in students
        assert r["stop_id"] in stops
        assert r["route_id"] in routes
    for r in tables["GuardianContact"]:
        assert r["student_id"] in students

def test_ground_truth_all_required_types(tables):
    gt = tables["ground_truth"]
    assert len(gt) > 50
    issue_types = {r["issue_type"] for r in gt}
    required = {
        "bus_capacity_exceeded",
        "student_assigned_to_incompatible_route",
        "impossible_travel_time",
        "notification_sent_to_invalid_contact",
        "unapproved_address_exposed",
    }
    missing = required - issue_types
    assert not missing, f"Missing ground-truth types: {missing}"

def test_attendance_covers_200_days(tables):
    dates = {r["event_date"] for r in tables["AttendanceEvent"]}
    assert len(dates) == 200, f"Expected 200 unique school days, got {len(dates)}"

def test_validation_summary_clean():
    summary = json.load(open(DATA / "validation_summary.json"))
    assert summary.get("fk_ok") is True
    assert summary.get("issues") == []
    assert all(summary["pk_unique"].values())

def test_checksums_file():
    checks = json.load(open(DATA / "checksums.json"))
    assert "Student.csv" in checks
    assert len(checks["Student.csv"]) == 64

def test_capacity_overflows_labelled(tables):
    capacity_gt = [r for r in tables["ground_truth"] if r["issue_type"] == "bus_capacity_exceeded"]
    assert len(capacity_gt) > 0
    notes_with_cap = [r for r in tables["Assignment"] if r.get("notes") and "capacity_exceeded" in r["notes"]]
    assert len(notes_with_cap) > 0


def test_synthetic_addresses_and_pickup_windows(tables):
    from datetime import datetime
    for row in tables['Student']:
        assert 'Synthetic Avenue' in row['address_line']
        start = datetime.strptime(row['pickup_window_start'], '%H:%M')
        end = datetime.strptime(row['pickup_window_end'], '%H:%M')
        assert start < end
    for row in tables['RouteStop']:
        start = datetime.strptime(row['pickup_window_start'], '%H:%M')
        end = datetime.strptime(row['pickup_window_end'], '%H:%M')
        assert start < end


def test_all_injected_anomalies_are_ground_truth_labelled():
    summary = json.load(open(DATA / "validation_summary.json", encoding="utf-8"))
    assert summary["unlabelled_anomalies"] == []
    assert set(summary["labelled_anomalies"]) == {
        "bus_capacity_exceeded", "student_assigned_to_incompatible_route",
        "impossible_travel_time", "notification_sent_to_invalid_contact",
        "unapproved_address_exposed"
    }
    assert all(value > 0 for value in summary["labelled_anomalies"].values())
