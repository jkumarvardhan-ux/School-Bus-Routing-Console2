#!/usr/bin/env python3
"""
School Bus Routing & Student Assignment — Synthetic Data Generator
Fixed seed: 20261022
Volumes (full): 5000 students, 100 buses, 300 stops, 200 school days
Parameterized for starter scale via SCALE factor.

All required edge cases are generated and labelled in ground_truth:
- bus_capacity_exceeded
- student_assigned_to_incompatible_route
- impossible_travel_time
- notification_sent_to_invalid_contact
- unapproved_address_exposed
"""

import json
import csv
import hashlib
import random
from datetime import datetime, timedelta, date
from pathlib import Path
from collections import defaultdict, Counter

# ----------------------------- Config -----------------------------
SEED = 20261022
SCALE = 1.0  # 1.0 = full; 0.1 = starter

NUM_STUDENTS = int(5000 * SCALE)
NUM_BUSES = int(100 * SCALE)
NUM_STOPS = int(300 * SCALE)
NUM_ZONES = max(20, int(80 * SCALE))
NUM_DRIVERS = int(120 * SCALE)
NUM_ROUTES = int(150 * SCALE)
NUM_SCHOOL_DAYS = int(200 * SCALE)
SCHOOL_YEAR = "2026"
START_DATE = date(2026, 1, 5)

OUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(SEED)

# ----------------------------- Helpers -----------------------------
def pad_id(prefix: str, n: int, width: int = 6) -> str:
    return f"{prefix}-{n:0{width}d}"

def route_id(n: int) -> str:
    return f"ROUTE-{SCHOOL_YEAR}-{n:06d}"

def asn_id(student_id: str) -> str:
    return f"ASN-{student_id}-{SCHOOL_YEAR}"

def not_id(n: int) -> str:
    return f"NOT-{SCHOOL_YEAR}-{n:06d}"

def ts(dt=None) -> str:
    if dt is None:
        dt = datetime(2025, 11, 1) + timedelta(days=random.randint(0, 30))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def dstr(d: date) -> str:
    return d.strftime("%Y-%m-%d")

FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn",
               "Sam", "Jamie", "Cameron", "Drew", "Blake", "Reese", "Skyler", "Hayden",
               "Parker", "Emerson", "Finley", "Rowan", "Logan", "Harper", "Evelyn", "Lucas",
               "Mia", "Noah", "Olivia", "Liam", "Emma", "Mason", "Sophia", "Ethan"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
              "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
              "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson"]

def synth_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

def synth_phone():
    return f"+1{random.randint(2000000000, 9999999999)}"

def synth_email(name: str):
    clean = name.lower().replace(" ", ".")
    return f"{clean}{random.randint(1,999)}@example.com"

# ----------------------------- Master Data -----------------------------
def gen_zones():
    zones = []
    for i in range(1, NUM_ZONES + 1):
        zid = pad_id("ZONE", i)
        base_lat = 37.77 + random.uniform(-0.15, 0.15)
        base_lon = -122.42 + random.uniform(-0.2, 0.2)
        zones.append({
            "zone_id": zid,
            "zone_name": f"Zone {i} - Sector {chr(64 + (i % 26) or 26)}",
            "centroid_lat": round(base_lat, 6),
            "centroid_lon": round(base_lon, 6),
            "is_approved": True,
            "school_district": "Bayview Unified",
            "created_at": ts()
        })
    if zones:
        zones[-1]["is_approved"] = False
        zones[-1]["zone_name"] = zones[-1]["zone_name"] + " [UNAPPROVED]"
    return zones

def gen_stops(zones):
    stops = []
    approved_zones = [z for z in zones if z["is_approved"]]
    unapproved_zones = [z for z in zones if not z["is_approved"]]
    for i in range(1, NUM_STOPS + 1):
        # Guarantee an approved stop in every approved zone before adding variation.
        if i == 1 and unapproved_zones:
            z = unapproved_zones[0]
        elif 2 <= i <= len(approved_zones) + 1:
            z = approved_zones[i - 2]
        else:
            z = random.choice(approved_zones or zones)
        sid = pad_id("STOP", i)
        is_approved = bool(z["is_approved"] and (i <= len(approved_zones) + 1 or random.random() > 0.01))
        stops.append({
            "stop_id": sid,
            "stop_name": f"Stop {i} @ {z['zone_name']}",
            "lat": round(z["centroid_lat"] + random.uniform(-0.02, 0.02), 6),
            "lon": round(z["centroid_lon"] + random.uniform(-0.02, 0.02), 6),
            "address_zone_id": z["zone_id"],
            "is_approved": is_approved,
            "capacity_hint": random.choice([15, 20, 25, 30, None]),
            "created_at": ts()
        })
    return stops

def gen_buses():
    buses = []
    for i in range(1, NUM_BUSES + 1):
        cap = random.choice([24, 36, 48, 54, 60, 72])
        buses.append({
            "bus_id": pad_id("BUS", i),
            "plate_number": f"SB{random.randint(1000,9999)}{chr(65 + i % 26)}",
            "capacity": cap,
            "accessible": random.random() < 0.25,
            "status": random.choices(["active", "maintenance", "retired"], weights=[0.85, 0.10, 0.05])[0],
            "current_capacity_override": None,
            "created_at": ts()
        })
    if buses:
        buses[0]["current_capacity_override"] = max(10, buses[0]["capacity"] - 10)
    return buses

def gen_drivers():
    drivers = []
    for i in range(1, NUM_DRIVERS + 1):
        fn, ln = synth_name()
        drivers.append({
            "driver_id": pad_id("DRV", i),
            "name": f"{fn} {ln}",
            "license_number": f"DL{random.randint(100000, 999999)}",
            "phone": synth_phone(),
            "status": random.choices(["active", "leave", "terminated"], weights=[0.9, 0.07, 0.03])[0],
            "hired_date": dstr(date(2018, 1, 1) + timedelta(days=random.randint(0, 2500))),
            "created_at": ts()
        })
    return drivers

def gen_students(zones):
    students = []
    approved_zones = [z for z in zones if z["is_approved"]] or zones
    for i in range(1, NUM_STUDENTS + 1):
        fn, ln = synth_name()
        grade = random.randint(1, 12)
        birth_year = 2026 - (5 + grade)
        dob = date(birth_year, random.randint(1, 12), random.randint(1, 28))
        access = random.choices(
            ["none", "wheelchair", "visual", "hearing", "other"],
            weights=[0.88, 0.06, 0.03, 0.02, 0.01]
        )[0]
        z = random.choice(approved_zones)
        student_id = pad_id("STU", i)
        address_hash = int(hashlib.sha256(student_id.encode()).hexdigest()[:8], 16)
        pickup_start_hour = 6 + (address_hash % 2)
        pickup_start_minute = ((address_hash // 3) % 4) * 15
        pickup_end_total = pickup_start_hour * 60 + pickup_start_minute + 120
        students.append({
            "student_id": student_id,
            "first_name": fn,
            "last_name": ln,
            "grade": grade,
            "date_of_birth": dstr(dob),
            "accessibility_needs": access,
            "address_zone_id": z["zone_id"],
            "address_line": f"{100 + address_hash % 8900} Synthetic Avenue, Unit {1 + address_hash % 40}",
            "pickup_window_start": f"{pickup_start_hour:02d}:{pickup_start_minute:02d}",
            "pickup_window_end": f"{pickup_end_total // 60:02d}:{pickup_end_total % 60:02d}",
            "is_active": random.random() > 0.01,
            "created_at": ts(),
            "effective_from": "2026-01-01",
            "effective_to": None
        })
    return students

def gen_guardians(students):
    contacts = []
    cid = 1
    for s in students:
        n_contacts = random.choices([1, 2, 3], weights=[0.55, 0.35, 0.10])[0]
        for j in range(n_contacts):
            fn, ln = synth_name()
            contacts.append({
                "contact_id": pad_id("GDN", cid),
                "student_id": s["student_id"],
                "name": f"{fn} {ln}",
                "relationship": random.choice(["parent", "parent", "guardian", "other"]),
                "phone": synth_phone(),
                "email": synth_email(f"{fn}.{ln}"),
                "is_primary": (j == 0),
                "is_valid": True,
                "created_at": ts()
            })
            cid += 1
    for idx in range(max(5, len(contacts) // 150)):
        c = contacts[-(idx + 1)]
        c["is_valid"] = False
        c["phone"] = "INVALID"
        c["email"] = "bad@"
    return contacts

# ----------------------------- Routes & Assignments -----------------------------
def gen_routes(buses, drivers):
    routes = []
    active_buses = [b for b in buses if b["status"] == "active"] or buses
    active_drivers = [d for d in drivers if d["status"] == "active"] or drivers
    for i in range(1, NUM_ROUTES + 1):
        bus = random.choice(active_buses)
        drv = random.choice(active_drivers)
        routes.append({
            "route_id": route_id(i),
            "route_name": f"Route {i} {'AM' if i % 2 else 'PM'}",
            "bus_id": bus["bus_id"],
            "driver_id": drv["driver_id"] if drv else None,
            "school_id": "SCH-001",
            "direction": "morning" if i % 2 else "afternoon",
            "is_active": True,
            "effective_from": "2026-01-01",
            "effective_to": None,
            "created_at": ts()
        })
    return routes

def gen_route_stops(routes, stops):
    route_stops = []
    rs_id = 1
    approved_stops = [s for s in stops if s["is_approved"]] or stops
    stops_by_zone = defaultdict(list)
    for stop in approved_stops:
        stops_by_zone[stop["address_zone_id"]].append(stop)
    zone_ids = sorted(stops_by_zone)
    for route_index, r in enumerate(routes):
        n_stops = random.randint(14, 16)
        start_zone = (route_index * n_stops) % max(1, len(zone_ids))
        chosen_zones = [zone_ids[(start_zone + j) % len(zone_ids)] for j in range(min(n_stops, len(zone_ids)))]
        chosen = [random.choice(stops_by_zone[zid])["stop_id"] for zid in chosen_zones]
        prev_time = 0
        for seq, sid in enumerate(chosen, 1):
            travel = random.randint(3, 12)
            planned = prev_time + travel
            route_stops.append({
                "route_stop_id": pad_id("RS", rs_id),
                "route_id": r["route_id"],
                "stop_id": sid,
                "sequence": seq,
                "planned_arrival_min": planned,
                "travel_time_from_prev_min": travel,
                "pickup_window_start": f"{(6 + planned // 60):02d}:{planned % 60:02d}",
                "pickup_window_end": f"{(6 + (planned + 20) // 60):02d}:{(planned + 20) % 60:02d}",
                "created_at": ts()
            })
            prev_time = planned
            rs_id += 1
    return route_stops

def gen_assignments(students, routes, route_stops, buses, stops):
    """Generate a valid baseline: no capacity, accessibility, stop, driver or travel-time violations."""
    assignments = []
    stop_by_id = {s["stop_id"]: s for s in stops}
    bus_by_id = {b["bus_id"]: b for b in buses}
    driver_by_id = {d["driver_id"]: d for d in gen_driver_cache}
    route_by_id = {r["route_id"]: r for r in routes}
    route_stop_map = defaultdict(list)
    for rs in route_stops:
        route_stop_map[rs["route_id"]].append(rs)
    bus_cap = {b["bus_id"]: (b["current_capacity_override"] if b["current_capacity_override"] is not None else b["capacity"]) for b in buses}
    route_load = defaultdict(int)
    routes_by_zone = defaultdict(list)
    for route in routes:
        bus = bus_by_id[route["bus_id"]]
        driver = driver_by_id.get(route["driver_id"])
        if bus["status"] != "active" or not driver or driver["status"] != "active":
            continue
        for rs in route_stop_map[route["route_id"]]:
            stop = stop_by_id[rs["stop_id"]]
            if not stop["is_approved"] or rs["travel_time_from_prev_min"] > 60:
                continue
            routes_by_zone[stop["address_zone_id"]].append((route, rs, bus))

    approved_zone_ids = {z["zone_id"] for z in gen_zone_cache if z["is_approved"]}
    active_students = [s for s in students if s["is_active"] and s["address_zone_id"] in approved_zone_ids]
    random.shuffle(active_students)
    for student in active_students:
        candidates = []
        for route, rs, bus in routes_by_zone.get(student["address_zone_id"], []):
            if student["accessibility_needs"] == "wheelchair" and not bus["accessible"]:
                continue
            # Student and stop pickup windows must overlap.
            if max(student["pickup_window_start"], rs["pickup_window_start"]) > min(student["pickup_window_end"], rs["pickup_window_end"]):
                continue
            cap = bus_cap[bus["bus_id"]]
            if route_load[route["route_id"]] < cap:
                candidates.append((route, rs, bus, cap))
        if not candidates:
            continue
        random.shuffle(candidates)
        candidates.sort(key=lambda x: route_load[x[0]["route_id"]] / max(1, x[3]))
        route, rs, bus, cap = candidates[0]
        assignments.append({
            "assignment_id": asn_id(student["student_id"]),
            "student_id": student["student_id"],
            "route_id": route["route_id"],
            "stop_id": rs["stop_id"],
            "school_year": SCHOOL_YEAR,
            "assigned_at": ts(datetime(2025, 12, 15)),
            "status": "active",
            "is_compatible": True,
            "notes": None
        })
        route_load[route["route_id"]] += 1
    return assignments, route_load, 0, 0


def inject_edge_cases(students, routes, route_stops, buses, stops, drivers, assignments, guardians, attendance):
    """Inject a small, explicit and labelled set of negative examples after valid baseline generation."""
    bus_by_id = {b["bus_id"]: b for b in buses}
    driver_by_id = {d["driver_id"]: d for d in drivers}
    stop_by_id = {s["stop_id"]: s for s in stops}
    route_by_id = {r["route_id"]: r for r in routes}
    load = Counter(a["route_id"] for a in assignments)
    route_stops_by_route = defaultdict(list)
    for route_stop in route_stops:
        route_stops_by_route[route_stop["route_id"]].append(route_stop)

    # 1) Capacity: lower one bus's effective capacity beneath its already-valid route load.
    capacity_routes = [r for r in routes if load[r["route_id"]] >= 2 and bus_by_id[r["bus_id"]]["status"] == "active"]
    if capacity_routes:
        target = max(capacity_routes, key=lambda r: load[r["route_id"]])
        bus_by_id[target["bus_id"]]["current_capacity_override"] = 1
        affected_routes = {r["route_id"] for r in routes if r["bus_id"] == target["bus_id"]}
        for a in assignments:
            if a["route_id"] in affected_routes:
                a["notes"] = "capacity_exceeded_injected"

    # 2) Accessibility: move one wheelchair student to a non-accessible route with spare capacity.
    wheelchair = [s for s in students if s["accessibility_needs"] == "wheelchair" and any(a["student_id"] == s["student_id"] for a in assignments)]
    alternate = None
    for student in wheelchair:
        for route in routes:
            bus = bus_by_id[route["bus_id"]]
            if bus["status"] != "active" or bus["accessible"] or not route["is_active"]:
                continue
            driver = driver_by_id.get(route["driver_id"])
            if not driver or driver["status"] != "active":
                continue
            cap = bus["current_capacity_override"] or bus["capacity"]
            if load[route["route_id"]] >= cap:
                continue
            for rs in [x for x in route_stops_by_route[route["route_id"]] if x["travel_time_from_prev_min"] <= 60]:
                stop = stop_by_id[rs["stop_id"]]
                if stop["is_approved"] and stop["address_zone_id"] == student["address_zone_id"]:
                    if max(student["pickup_window_start"], rs["pickup_window_start"]) <= min(student["pickup_window_end"], rs["pickup_window_end"]):
                        alternate = (student, route, rs)
                        break
            if alternate: break
        if alternate: break
    if alternate:
        student, route, rs = alternate
        a = next(x for x in assignments if x["student_id"] == student["student_id"])
        a["route_id"], a["stop_id"], a["is_compatible"] = route["route_id"], rs["stop_id"], False
        a["notes"] = ((a["notes"] + ";") if a["notes"] else "") + "incompatible_route_injected"
        load[a["route_id"]] += 1

    # 3) Impossible travel time: inject one unrealistic travel leg after route construction.
    if route_stops:
        rs = route_stops[-1]
        rs["travel_time_from_prev_min"] = 120

    # 4) Unapproved address exposure: change one assigned student's zone to the unapproved synthetic zone.
    unapproved_zones = [z for z in gen_zone_cache if not z["is_approved"]]
    if unapproved_zones and assignments:
        a = assignments[-1]
        student = next(s for s in students if s["student_id"] == a["student_id"])
        student["address_zone_id"] = unapproved_zones[0]["zone_id"]

    # 5) Invalid notification target: append one explicitly injected notification to an invalid synthetic contact.
    assigned_ids = {a["student_id"] for a in assignments}
    invalid_contacts = [g for g in guardians if not g["is_valid"] and g["student_id"] in assigned_ids]
    if invalid_contacts:
        contact = invalid_contacts[0]
        related = next((e for e in attendance if e["student_id"] == contact["student_id"]), None)
        if related is None:
            assignment = next(a for a in assignments if a["student_id"] == contact["student_id"])
            related = {
                "event_id": pad_id("ATT", len(attendance) + 1),
                "student_id": contact["student_id"],
                "assignment_id": assignment["assignment_id"],
                "event_date": "2026-01-05",
                "status": "missed_pickup",
                "recorded_at": "2026-01-05T08:00:00Z",
                "notes": "injected_invalid_contact_test"
            }
            attendance.append(related)
        if related:
            notifs = gen_notification_cache
            notifs.append({
                "notification_id": not_id(len(notifs) + 1),
                "student_id": contact["student_id"],
                "contact_id": contact["contact_id"],
                "event_type": "contact_validation_test",
                "message": f"Injected invalid-contact test notification for {contact['student_id']}",
                "sent_at": related["recorded_at"],
                "delivery_status": "sent",
                "related_event_id": related["event_id"]
            })


# ----------------------------- Events -----------------------------
def gen_school_days():
    days = []
    d = START_DATE
    while len(days) < NUM_SCHOOL_DAYS:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days

def gen_attendance(assignments, school_days):
    """Attendance across all 200 school days (sampled students per day for volume)."""
    events = []
    eid = 1
    active = [a for a in assignments if a["status"] == "active"]
    random.shuffle(active)
    sample_frac = 0.28
    for day in school_days:
        offset = (day.toordinal() * 7) % max(1, len(active))
        n = max(1, int(len(active) * sample_frac))
        day_students = active[offset:offset + n]
        if len(day_students) < n:
            day_students += active[:n - len(day_students)]
        for a in day_students:
            status = random.choices(
                ["present", "absent", "late", "missed_pickup"],
                weights=[0.82, 0.08, 0.05, 0.05]
            )[0]
            events.append({
                "event_id": pad_id("ATT", eid),
                "student_id": a["student_id"],
                "assignment_id": a["assignment_id"],
                "event_date": dstr(day),
                "status": status,
                "recorded_at": ts(datetime.combine(day, datetime.min.time()) + timedelta(hours=8)),
                "notes": None
            })
            eid += 1
    return events

def gen_notifications(attendance, guardians, assignments):
    notifs = []
    nid = 1
    contact_by_student = defaultdict(list)
    for g in guardians:
        contact_by_student[g["student_id"]].append(g)
    for att in attendance:
        if att["status"] not in ("missed_pickup", "absent"):
            continue
        contacts = contact_by_student.get(att["student_id"], [])
        if not contacts:
            continue
        valid_contacts = [c for c in contacts if c["is_valid"]]
        if not valid_contacts:
            continue
        c = next((x for x in valid_contacts if x["is_primary"]), valid_contacts[0])
        delivery = "sent"
        notifs.append({
            "notification_id": not_id(nid),
            "student_id": att["student_id"],
            "contact_id": c["contact_id"],
            "event_type": "missed_pickup" if att["status"] == "missed_pickup" else "attendance",
            "message": f"Alert: student {att['student_id']} marked {att['status']} on {att['event_date']}",
            "sent_at": att["recorded_at"],
            "delivery_status": delivery,
            "related_event_id": att["event_id"]
        })
        nid += 1
    return notifs

# ----------------------------- Ground Truth -----------------------------
def build_ground_truth(zones, stops, buses, route_stops, assignments, guardians, notifications, route_load):
    gt = []
    for z in zones:
        if not z["is_approved"]:
            gt.append({
                "entity_type": "AddressZone",
                "entity_id": z["zone_id"],
                "issue_type": "unapproved_address_exposed",
                "description": "Zone marked unapproved but still linked to stops/students",
                "expected_decision": "reject_or_flag_assignment",
                "severity": "high"
            })
    zone_by_id = {z["zone_id"]: z for z in zones}
    for student in gen_student_cache:
        zone = zone_by_id.get(student["address_zone_id"])
        if zone and not zone["is_approved"]:
            gt.append({
                "entity_type": "Student",
                "entity_id": student["student_id"],
                "issue_type": "unapproved_address_exposed",
                "description": "Student address references an unapproved synthetic address zone",
                "expected_decision": "quarantine_address_and_request_verification",
                "severity": "high"
            })
    for s in stops:
        if not s["is_approved"]:
            gt.append({
                "entity_type": "Stop",
                "entity_id": s["stop_id"],
                "issue_type": "unapproved_address_exposed",
                "description": "Stop linked to unapproved zone or itself unapproved",
                "expected_decision": "remove_from_active_routes",
                "severity": "high"
            })
    for a in assignments:
        notes = a.get("notes") or ""
        if "capacity_exceeded" in notes:
            gt.append({
                "entity_type": "Assignment",
                "entity_id": a["assignment_id"],
                "issue_type": "bus_capacity_exceeded",
                "description": "Student assigned after route/bus reached effective capacity",
                "expected_decision": "reassign_or_add_bus",
                "severity": "medium"
            })
    for a in assignments:
        if a.get("is_compatible") is False or str(a.get("is_compatible")).lower() == "false":
            gt.append({
                "entity_type": "Assignment",
                "entity_id": a["assignment_id"],
                "issue_type": "student_assigned_to_incompatible_route",
                "description": "Wheelchair (or special-need) student on non-accessible vehicle",
                "expected_decision": "move_to_accessible_vehicle",
                "severity": "high"
            })
    for rs in route_stops:
        if rs["travel_time_from_prev_min"] >= 90:
            gt.append({
                "entity_type": "RouteStop",
                "entity_id": rs["route_stop_id"],
                "issue_type": "impossible_travel_time",
                "description": f"Travel time {rs['travel_time_from_prev_min']} min between consecutive stops is unrealistic",
                "expected_decision": "resequence_or_split_route",
                "severity": "medium"
            })
    invalid_contacts = {g["contact_id"] for g in guardians if not g["is_valid"]}
    for n in notifications:
        if n["contact_id"] in invalid_contacts or n["delivery_status"] == "failed":
            gt.append({
                "entity_type": "Notification",
                "entity_id": n["notification_id"],
                "issue_type": "notification_sent_to_invalid_contact",
                "description": "Notification targeted invalid or failed contact record",
                "expected_decision": "update_contact_and_resend",
                "severity": "low"
            })
    return gt

# ----------------------------- I/O & Validation -----------------------------
def write_csv(name, rows, fieldnames=None):
    if not rows:
        return
    path = OUT_DIR / f"{name}.csv"
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return path

def write_json(name, obj):
    path = OUT_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    return path

def checksum_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def validate(tables, route_load, bus_cap, route_bus, ground_truth=None):
    report = {
        "pk_unique": {},
        "fk_ok": True,
        "counts": {},
        "issues": [],
        "capacity_reconciliation": {},
        "labelled_anomalies": {},
        "unlabelled_anomalies": [],
        "seed": SEED
    }
    for name, rows in tables.items():
        report["counts"][name] = len(rows)
        if not rows:
            continue
        pk = list(rows[0].keys())[0]
        ids = [r[pk] for r in rows]
        if len(ids) != len(set(ids)):
            report["pk_unique"][name] = False
            report["issues"].append(f"Duplicate PK in {name}")
        else:
            report["pk_unique"][name] = True

    zone_ids = {r["zone_id"] for r in tables["AddressZone"]}
    stop_ids = {r["stop_id"] for r in tables["Stop"]}
    bus_ids = {r["bus_id"] for r in tables["Bus"]}
    driver_ids = {r["driver_id"] for r in tables["Driver"]}
    route_ids = {r["route_id"] for r in tables["Route"]}
    student_ids = {r["student_id"] for r in tables["Student"]}
    contact_ids = {r["contact_id"] for r in tables["GuardianContact"]}
    asn_ids = {r["assignment_id"] for r in tables["Assignment"]}

    for r in tables["Student"]:
        if r["address_zone_id"] not in zone_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Student {r['student_id']} bad zone")
    for r in tables["Stop"]:
        if r["address_zone_id"] not in zone_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Stop {r['stop_id']} bad zone")
    for r in tables["Route"]:
        if r["bus_id"] not in bus_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Route {r['route_id']} bad bus")
        if r.get("driver_id") and r["driver_id"] not in driver_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Route {r['route_id']} bad driver")
    for r in tables["RouteStop"]:
        if r["route_id"] not in route_ids or r["stop_id"] not in stop_ids:
            report["fk_ok"] = False
            report["issues"].append(f"RouteStop {r['route_stop_id']} bad FK")
    for r in tables["Assignment"]:
        if r["student_id"] not in student_ids or r["route_id"] not in route_ids or r["stop_id"] not in stop_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Assignment {r['assignment_id']} bad FK")
    for r in tables["GuardianContact"]:
        if r["student_id"] not in student_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Guardian {r['contact_id']} bad student")
    for r in tables["AttendanceEvent"]:
        if r["student_id"] not in student_ids or r["assignment_id"] not in asn_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Attendance {r['event_id']} bad FK")
    for r in tables["Notification"]:
        if r["student_id"] not in student_ids or r["contact_id"] not in contact_ids:
            report["fk_ok"] = False
            report["issues"].append(f"Notification {r['notification_id']} bad FK")

    overflows = 0
    over_routes = 0
    for rid, load in route_load.items():
        bid = route_bus.get(rid)
        cap = bus_cap.get(bid, 40)
        if load > cap:
            over_routes += 1
            overflows += load - cap
    report["capacity_reconciliation"] = {
        "routes_over_capacity": over_routes,
        "total_overflow_seats": overflows
    }

    # Verify that deliberate negative examples are explicitly represented in separate ground truth.
    zone_by_id = {z["zone_id"]: z for z in tables["AddressZone"]}
    gt = ground_truth or []
    labelled = {(g["entity_type"], g["entity_id"], g["issue_type"]) for g in gt}
    invalid_contact_ids = {g["contact_id"] for g in tables["GuardianContact"] if not g["is_valid"]}
    checks = {
        "bus_capacity_exceeded": [("Assignment", a["assignment_id"]) for a in tables["Assignment"] if "capacity_exceeded" in (a.get("notes") or "")],
        "student_assigned_to_incompatible_route": [("Assignment", a["assignment_id"]) for a in tables["Assignment"] if not a.get("is_compatible")],
        "impossible_travel_time": [("RouteStop", r["route_stop_id"]) for r in tables["RouteStop"] if r["travel_time_from_prev_min"] > 60],
        "notification_sent_to_invalid_contact": [("Notification", n["notification_id"]) for n in tables["Notification"] if n["contact_id"] in invalid_contact_ids or n["delivery_status"] != "sent"],
        "unapproved_address_exposed": [("Student", s["student_id"]) for s in tables["Student"] if not zone_by_id[s["address_zone_id"]]["is_approved"]],
    }
    for issue_type, entities in checks.items():
        report["labelled_anomalies"][issue_type] = len(entities)
        for entity_type, entity_id in entities:
            if (entity_type, entity_id, issue_type) not in labelled:
                report["unlabelled_anomalies"].append(f"{entity_type} {entity_id} missing {issue_type} ground-truth label")
    if report["unlabelled_anomalies"]:
        report["issues"].extend(report["unlabelled_anomalies"])

    for r in tables["Student"]:
        try:
            start = datetime.strptime(r["pickup_window_start"], "%H:%M")
            end = datetime.strptime(r["pickup_window_end"], "%H:%M")
            if start >= end: report["issues"].append(f"Invalid pickup window {r['student_id']}")
        except (KeyError, ValueError):
            report["issues"].append(f"Malformed pickup window {r['student_id']}")
        if not (1 <= r["grade"] <= 12):
            report["issues"].append(f"Bad grade {r['student_id']}")
    for r in tables["AttendanceEvent"]:
        if r["status"] not in ("present", "absent", "late", "missed_pickup"):
            report["issues"].append(f"Bad attendance status {r['event_id']}")

    return report

def main():
    print(f"Generating with SEED={SEED}, SCALE={SCALE}")
    print(f"Targets: students={NUM_STUDENTS}, buses={NUM_BUSES}, stops={NUM_STOPS}, days={NUM_SCHOOL_DAYS}")

    zones = gen_zones()
    global gen_zone_cache, gen_student_cache, gen_notification_cache, gen_driver_cache
    gen_zone_cache = zones
    stops = gen_stops(zones)
    buses = gen_buses()
    drivers = gen_drivers()
    gen_driver_cache = drivers
    students = gen_students(zones)
    gen_student_cache = students
    guardians = gen_guardians(students)
    routes = gen_routes(buses, drivers)
    route_stops = gen_route_stops(routes, stops)
    assignments, route_load, overflow, incompatible = gen_assignments(
        students, routes, route_stops, buses, stops
    )
    school_days = gen_school_days()
    attendance = gen_attendance(assignments, school_days)
    notifications = gen_notifications(attendance, guardians, assignments)
    gen_notification_cache = notifications
    inject_edge_cases(students, routes, route_stops, buses, stops, drivers, assignments, guardians, attendance)
    route_load = Counter(a["route_id"] for a in assignments)
    bus_cap = {b["bus_id"]: (b["current_capacity_override"] if b["current_capacity_override"] is not None else b["capacity"]) for b in buses}
    route_bus = {r["route_id"]: r["bus_id"] for r in routes}
    overflow = sum(1 for a in assignments if a.get("notes") and "capacity_exceeded" in a["notes"])
    incompatible = sum(1 for a in assignments if not a.get("is_compatible"))
    ground_truth = build_ground_truth(
        zones, stops, buses, route_stops, assignments, guardians, notifications, route_load
    )

    tables = {
        "AddressZone": zones,
        "Stop": stops,
        "Bus": buses,
        "Driver": drivers,
        "Student": students,
        "GuardianContact": guardians,
        "Route": routes,
        "RouteStop": route_stops,
        "Assignment": assignments,
        "AttendanceEvent": attendance,
        "Notification": notifications,
    }

    for p in list(OUT_DIR.glob("*.csv")) + list(OUT_DIR.glob("*.json")):
        if p.name != "school_bus.db":
            try:
                p.unlink()
            except Exception:
                pass

    for name, rows in tables.items():
        write_csv(name, rows)
        write_json(name, rows)

    write_csv("ground_truth", ground_truth)
    write_json("ground_truth", ground_truth)

    bus_cap = {b["bus_id"]: (b["current_capacity_override"] if b["current_capacity_override"] is not None else b["capacity"]) for b in buses}
    route_bus = {r["route_id"]: r["bus_id"] for r in routes}

    report = validate(tables, route_load, bus_cap, route_bus, ground_truth)

    gt_types = Counter(g["issue_type"] for g in ground_truth)
    manifest = {
        "seed": SEED,
        "scale": SCALE,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "volumes": {k: len(v) for k, v in tables.items()},
        "school_days_generated": len(school_days),
        "attendance_unique_dates": len({a["event_date"] for a in attendance}),
        "ground_truth_count": len(ground_truth),
        "ground_truth_by_type": dict(gt_types),
        "overflow_assignments": overflow,
        "incompatible_assignments": incompatible,
        "files": sorted([p.name for p in OUT_DIR.glob("*") if p.suffix in (".csv", ".json")])
    }
    write_json("manifest", manifest)
    write_json("validation_summary", report)

    checksums = {}
    for p in sorted(OUT_DIR.glob("*.csv")):
        checksums[p.name] = checksum_file(p)
    write_json("checksums", checksums)

    print("Done. Files written to", OUT_DIR)
    print("Counts:", {k: len(v) for k, v in tables.items()})
    print("School days:", len(school_days), "| Attendance unique dates:", manifest["attendance_unique_dates"])
    print("Ground truth rows:", len(ground_truth))
    print("  by type:", dict(gt_types))
    print("Overflow assignments:", overflow, "| Incompatible:", incompatible)
    print("Validation issues:", report.get("issues", []))
    print("Capacity recon:", report.get("capacity_reconciliation"))

if __name__ == "__main__":
    main()
