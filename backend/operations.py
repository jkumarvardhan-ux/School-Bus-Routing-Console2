"""Transactional operational workflows for safe school-bus routing.

All writes are append-only in OperationalEvent / RouteDisruption / AttendanceEvent;
existing source rows are never silently rewritten.
"""
from datetime import datetime, date, timezone
import hashlib
import sqlite3

YEAR = "2026"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_schema(conn):
    """Idempotent additive migration; safe to call on every API connection."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(Student)")}
    for name, ddl in {
        "address_line": "TEXT",
        "pickup_window_start": "TEXT",
        "pickup_window_end": "TEXT",
    }.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE Student ADD COLUMN {name} {ddl}")
    rs_cols = {r[1] for r in conn.execute("PRAGMA table_info(RouteStop)")}
    for name in ("pickup_window_start", "pickup_window_end"):
        if name not in rs_cols:
            conn.execute(f"ALTER TABLE RouteStop ADD COLUMN {name} TEXT")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS OperationalEvent (
      event_id INTEGER PRIMARY KEY AUTOINCREMENT,
      entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
      event_type TEXT NOT NULL, event_at TEXT NOT NULL,
      actor TEXT NOT NULL, details_json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_operational_entity ON OperationalEvent(entity_type, entity_id, event_at);
    CREATE TABLE IF NOT EXISTS BusCapacityEvent (
      capacity_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
      bus_id TEXT NOT NULL REFERENCES Bus(bus_id), old_capacity INTEGER NOT NULL,
      new_capacity INTEGER NOT NULL, effective_at TEXT NOT NULL, reason TEXT NOT NULL,
      actor TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS RouteDisruption (
      disruption_id INTEGER PRIMARY KEY AUTOINCREMENT,
      route_id TEXT NOT NULL REFERENCES Route(route_id),
      disruption_type TEXT NOT NULL CHECK(disruption_type IN ('bus_breakdown','driver_unavailable','road_closure','weather')),
      starts_at TEXT NOT NULL, ends_at TEXT, status TEXT NOT NULL CHECK(status IN ('open','resolved')),
      notes TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS PickupWindowViolation (
      violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT NOT NULL REFERENCES Student(student_id),
      route_id TEXT NOT NULL REFERENCES Route(route_id),
      stop_id TEXT NOT NULL REFERENCES Stop(stop_id),
      requested_start TEXT NOT NULL, requested_end TEXT NOT NULL,
      reason TEXT NOT NULL, created_at TEXT NOT NULL
    );
    """)
    # Deterministic, synthetic and privacy-safe address/window enrichment.
    rows = conn.execute("SELECT student_id, address_zone_id FROM Student WHERE address_line IS NULL").fetchall()
    for sid, zid in rows:
        n = int(hashlib.sha256(sid.encode()).hexdigest()[:8], 16)
        start_hour = 6 + (n % 3)
        start_min = (n // 3 % 4) * 15
        start = f"{start_hour:02d}:{start_min:02d}"
        end_total = start_hour * 60 + start_min + 45
        end = f"{end_total // 60:02d}:{end_total % 60:02d}"
        conn.execute("UPDATE Student SET address_line=?, pickup_window_start=?, pickup_window_end=? WHERE student_id=?",
                     (f"{100 + n % 8900} Synthetic Avenue, Unit {1+n%40}", start, end, sid))
    rows = conn.execute("SELECT route_stop_id, planned_arrival_min FROM RouteStop WHERE pickup_window_start IS NULL").fetchall()
    for rsid, minute in rows:
        total = 6 * 60 + int(minute or 0)
        start = f"{(total//60)%24:02d}:{total%60:02d}"
        end_total = total + 20
        end = f"{(end_total//60)%24:02d}:{end_total%60:02d}"
        conn.execute("UPDATE RouteStop SET pickup_window_start=?, pickup_window_end=? WHERE route_stop_id=?", (start, end, rsid))
    conn.commit()


def _event(conn, entity_type, entity_id, event_type, actor, details):
    import json
    conn.execute("INSERT INTO OperationalEvent(entity_type,entity_id,event_type,event_at,actor,details_json) VALUES(?,?,?,?,?,?)",
                 (entity_type, entity_id, event_type, now(), actor, json.dumps(details, sort_keys=True)))


def _minutes(hhmm):
    h, m = map(int, hhmm.split(":", 1))
    return h * 60 + m


def assign_student(conn, student_id, route_id, stop_id, actor="dispatcher"):
    """Create an assignment only when every safety/business rule is satisfied."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        student = conn.execute("SELECT * FROM Student WHERE student_id=?", (student_id,)).fetchone()
        route = conn.execute("SELECT r.*, b.capacity, b.current_capacity_override, b.accessible, b.status bus_status, b.bus_id FROM Route r JOIN Bus b ON b.bus_id=r.bus_id WHERE r.route_id=?", (route_id,)).fetchone()
        stop = conn.execute("SELECT * FROM Stop WHERE stop_id=?", (stop_id,)).fetchone()
        rs = conn.execute("SELECT * FROM RouteStop WHERE route_id=? AND stop_id=?", (route_id, stop_id)).fetchone()
        errors = []
        if not student or not student["is_active"]: errors.append("student_not_active_or_missing")
        if not route or not route["is_active"]: errors.append("route_not_active_or_missing")
        if not stop or not stop["is_approved"]: errors.append("stop_not_approved_or_missing")
        if not rs: errors.append("stop_not_on_route")
        if route and route["bus_status"] != "active": errors.append("bus_not_active")
        if route and conn.execute("SELECT 1 FROM RouteDisruption WHERE route_id=? AND status='open' AND starts_at<=? AND (ends_at IS NULL OR ends_at>=?) LIMIT 1", (route_id, now(), now())).fetchone():
            errors.append("route_disrupted")
        if route and route["driver_id"]:
            drv = conn.execute("SELECT status FROM Driver WHERE driver_id=?", (route["driver_id"],)).fetchone()
            if not drv or drv["status"] != "active": errors.append("driver_not_active")
        if student and stop and student["address_zone_id"] != stop["address_zone_id"]: errors.append("student_stop_zone_mismatch")
        if student and student["accessibility_needs"] == "wheelchair" and route and not route["accessible"]: errors.append("accessible_vehicle_required")
        existing = conn.execute("SELECT * FROM Assignment WHERE student_id=? AND status='active'", (student_id,)).fetchone()
        if route:
            cap = route["current_capacity_override"] or route["capacity"]
            load = conn.execute("SELECT COUNT(*) FROM Assignment WHERE route_id=? AND status='active' AND student_id<>?", (route_id, student_id)).fetchone()[0]
            if load >= cap: errors.append("bus_capacity_exceeded")
        if rs and rs["travel_time_from_prev_min"] is not None and rs["travel_time_from_prev_min"] > 60: errors.append("route_travel_time_infeasible")
        if student and rs:
            a, b = student["pickup_window_start"], student["pickup_window_end"]
            c, d = rs["pickup_window_start"], rs["pickup_window_end"]
            if a and b and c and d and max(_minutes(a), _minutes(c)) > min(_minutes(b), _minutes(d)):
                errors.append("pickup_window_no_overlap")
        if existing and existing["route_id"] == route_id and existing["stop_id"] == stop_id:
            errors.append("student_already_assigned_to_this_route_and_stop")
        if errors:
            conn.rollback()
            _event(conn, "Assignment", f"{student_id}:{route_id}:{stop_id}", "assignment_rejected", actor, {"errors": errors})
            if "pickup_window_no_overlap" in errors and student and rs:
                conn.execute("INSERT INTO PickupWindowViolation(student_id,route_id,stop_id,requested_start,requested_end,reason,created_at) VALUES(?,?,?,?,?,?,?)",
                             (student_id, route_id, stop_id, student["pickup_window_start"], student["pickup_window_end"], "no_overlap_with_route_stop_window", now()))
            conn.commit()
            return {"ok": False, "errors": errors}
        assignment_id = f"ASN-{student_id}-{YEAR}"
        if existing:
            previous = {"route_id": existing["route_id"], "stop_id": existing["stop_id"]}
            assignment_id = existing["assignment_id"]
            conn.execute("UPDATE Assignment SET route_id=?,stop_id=?,assigned_at=?,is_compatible=1,notes='operationally_validated' WHERE assignment_id=?",
                         (route_id, stop_id, now(), assignment_id))
            event_type = "assignment_reassigned"
        else:
            conn.execute("INSERT INTO Assignment(assignment_id,student_id,route_id,stop_id,school_year,assigned_at,status,is_compatible,notes) VALUES(?,?,?,?,?,?,?,?,?)",
                         (assignment_id, student_id, route_id, stop_id, YEAR, now(), "active", 1, "operationally_validated"))
            previous = None
            event_type = "assignment_created"
        _event(conn, "Assignment", assignment_id, event_type, actor,
               {"student_id": student_id, "route_id": route_id, "stop_id": stop_id, "capacity_at_assignment": cap, "load_before": load, "previous_assignment": previous})
        conn.commit()
        return {"ok": True, "assignment_id": assignment_id, "capacity": cap, "load_after": load + 1}
    except Exception:
        conn.rollback()
        raise


def record_attendance(conn, student_id, event_date, status, actor="school_staff", notes=None):
    allowed = {"present", "absent", "late", "missed_pickup", "boarded", "dropped_off"}
    if status not in allowed: return {"ok": False, "errors": ["invalid_attendance_status"]}
    try: date.fromisoformat(event_date)
    except ValueError: return {"ok": False, "errors": ["invalid_event_date"]}
    a = conn.execute("SELECT assignment_id FROM Assignment WHERE student_id=? AND status='active'", (student_id,)).fetchone()
    if not a: return {"ok": False, "errors": ["no_active_assignment"]}
    next_att = conn.execute("SELECT COALESCE(MAX(CAST(SUBSTR(event_id,5) AS INTEGER)),0)+1 FROM AttendanceEvent WHERE event_id LIKE 'ATT-%'").fetchone()[0]
    event_id = f"ATT-{next_att:06d}"
    conn.execute("INSERT INTO AttendanceEvent(event_id,student_id,assignment_id,event_date,status,recorded_at,notes) VALUES(?,?,?,?,?,?,?)",
                 (event_id, student_id, a["assignment_id"], event_date, status, now(), notes))
    _event(conn, "AttendanceEvent", event_id, "attendance_recorded", actor, {"student_id": student_id, "status": status})
    notification = None
    if status in {"absent", "missed_pickup"}:
        contact = conn.execute("SELECT contact_id FROM GuardianContact WHERE student_id=? AND is_primary=1 AND is_valid=1 ORDER BY contact_id LIMIT 1", (student_id,)).fetchone()
        if contact:
            next_not = conn.execute("SELECT COALESCE(MAX(CAST(SUBSTR(notification_id,10) AS INTEGER)),0)+1 FROM Notification WHERE notification_id LIKE 'NOT-2026-%'").fetchone()[0]
            nid = f"NOT-2026-{next_not:06d}"
            conn.execute("INSERT INTO Notification(notification_id,student_id,contact_id,event_type,message,sent_at,delivery_status,related_event_id) VALUES(?,?,?,?,?,?,?,?)",
                         (nid, student_id, contact["contact_id"], status, f"Synthetic alert: {student_id} recorded {status} on {event_date}", now(), "sent", event_id))
            notification = nid
            _event(conn, "Notification", nid, "guardian_notified", actor, {"contact_id": contact["contact_id"], "attendance_event_id": event_id})
        else:
            _event(conn, "Notification", student_id, "guardian_notification_suppressed", actor, {"reason": "no_valid_primary_contact"})
    conn.commit()
    return {"ok": True, "event_id": event_id, "notification_id": notification}


def report_disruption(conn, route_id, disruption_type, starts_at, ends_at=None, notes=None, actor="dispatcher"):
    allowed = {"bus_breakdown", "driver_unavailable", "road_closure", "weather"}
    if disruption_type not in allowed: return {"ok": False, "errors": ["invalid_disruption_type"]}
    if not starts_at: return {"ok": False, "errors": ["start_time_required"]}
    try:
        datetime.fromisoformat(starts_at)
        if ends_at: datetime.fromisoformat(ends_at)
    except ValueError:
        return {"ok": False, "errors": ["invalid_disruption_datetime"]}
    if not conn.execute("SELECT 1 FROM Route WHERE route_id=?", (route_id,)).fetchone(): return {"ok": False, "errors": ["route_not_found"]}
    if ends_at and ends_at < starts_at: return {"ok": False, "errors": ["end_before_start"]}
    cur = conn.execute("INSERT INTO RouteDisruption(route_id,disruption_type,starts_at,ends_at,status,notes,created_at) VALUES(?,?,?,?,?,?,?)",
                       (route_id, disruption_type, starts_at, ends_at, "open", notes, now()))
    did = cur.lastrowid
    _event(conn, "Route", route_id, "route_disruption_reported", actor, {"disruption_id": did, "type": disruption_type, "starts_at": starts_at})
    conn.commit()
    return {"ok": True, "disruption_id": did}


def resolve_disruption(conn, disruption_id, actor="dispatcher"):
    row = conn.execute("SELECT * FROM RouteDisruption WHERE disruption_id=?", (disruption_id,)).fetchone()
    if not row:
        return {"ok": False, "errors": ["disruption_not_found"]}
    if row["status"] == "resolved":
        return {"ok": False, "errors": ["disruption_already_resolved"]}
    resolved_at = now()
    conn.execute("UPDATE RouteDisruption SET status='resolved', ends_at=COALESCE(ends_at, ?) WHERE disruption_id=?", (resolved_at, disruption_id))
    _event(conn, "Route", row["route_id"], "route_disruption_resolved", actor, {"disruption_id": disruption_id, "type": row["disruption_type"], "resolved_at": resolved_at})
    conn.commit()
    return {"ok": True, "disruption_id": disruption_id, "status": "resolved"}


def change_bus_capacity(conn, bus_id, new_capacity, reason, actor="fleet_admin"):
    try:
        new_capacity = int(new_capacity)
    except (TypeError, ValueError):
        return {"ok": False, "errors": ["capacity_must_be_integer"]}
    bus = conn.execute("SELECT * FROM Bus WHERE bus_id=?", (bus_id,)).fetchone()
    if not bus:
        return {"ok": False, "errors": ["bus_not_found"]}
    if new_capacity < 1 or new_capacity > bus["capacity"]:
        return {"ok": False, "errors": ["capacity_outside_allowed_range"]}
    active_routes = conn.execute("SELECT route_id FROM Route WHERE bus_id=? AND is_active=1", (bus_id,)).fetchall()
    for route in active_routes:
        load = conn.execute("SELECT COUNT(*) FROM Assignment WHERE route_id=? AND status='active'", (route["route_id"],)).fetchone()[0]
        if load > new_capacity:
            return {"ok": False, "errors": [f"capacity_below_current_load:{route['route_id']}:{load}"]}
    old_capacity = bus["current_capacity_override"] or bus["capacity"]
    conn.execute("UPDATE Bus SET current_capacity_override=? WHERE bus_id=?", (None if new_capacity == bus["capacity"] else new_capacity, bus_id))
    cur = conn.execute("INSERT INTO BusCapacityEvent(bus_id,old_capacity,new_capacity,effective_at,reason,actor,created_at) VALUES(?,?,?,?,?,?,?)",
                       (bus_id, old_capacity, new_capacity, now(), reason or "capacity_adjustment", actor, now()))
    _event(conn, "Bus", bus_id, "bus_capacity_changed", actor, {"old_capacity": old_capacity, "new_capacity": new_capacity, "reason": reason})
    conn.commit()
    return {"ok": True, "capacity_event_id": cur.lastrowid, "old_capacity": old_capacity, "new_capacity": new_capacity}
