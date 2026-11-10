"""Acceptance tests for transactional assignment, attendance and disruption workflows."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from operations import init_schema, assign_student, record_attendance, report_disruption, resolve_disruption, change_bus_capacity


def db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE Student(student_id TEXT PRIMARY KEY, address_zone_id TEXT, is_active INTEGER, accessibility_needs TEXT);
    CREATE TABLE Route(route_id TEXT PRIMARY KEY, bus_id TEXT, driver_id TEXT, is_active INTEGER);
    CREATE TABLE Bus(bus_id TEXT PRIMARY KEY, capacity INTEGER, current_capacity_override INTEGER, accessible INTEGER, status TEXT);
    CREATE TABLE Driver(driver_id TEXT PRIMARY KEY, status TEXT);
    CREATE TABLE Stop(stop_id TEXT PRIMARY KEY, address_zone_id TEXT, is_approved INTEGER);
    CREATE TABLE RouteStop(route_stop_id TEXT PRIMARY KEY, route_id TEXT, stop_id TEXT, travel_time_from_prev_min INTEGER, planned_arrival_min INTEGER);
    CREATE TABLE Assignment(assignment_id TEXT PRIMARY KEY, student_id TEXT, route_id TEXT, stop_id TEXT, school_year TEXT, assigned_at TEXT, status TEXT, is_compatible INTEGER, notes TEXT);
    CREATE TABLE GuardianContact(contact_id TEXT PRIMARY KEY, student_id TEXT, is_primary INTEGER, is_valid INTEGER);
    CREATE TABLE AttendanceEvent(event_id TEXT PRIMARY KEY, student_id TEXT, assignment_id TEXT, event_date TEXT, status TEXT, recorded_at TEXT, notes TEXT);
    CREATE TABLE Notification(notification_id TEXT PRIMARY KEY, student_id TEXT, contact_id TEXT, event_type TEXT, message TEXT, sent_at TEXT, delivery_status TEXT, related_event_id TEXT);
    """)
    c.execute("INSERT INTO Bus VALUES('BUS-000001',2,NULL,1,'active')")
    c.execute("INSERT INTO Driver VALUES('DRV-000001','active')")
    c.execute("INSERT INTO Route VALUES('ROUTE-2026-000001','BUS-000001','DRV-000001',1)")
    c.execute("INSERT INTO Stop VALUES('STOP-000001','ZONE-1',1)")
    c.execute("INSERT INTO RouteStop(route_stop_id,route_id,stop_id,travel_time_from_prev_min,planned_arrival_min) VALUES('RS-1','ROUTE-2026-000001','STOP-000001',10,20)")
    c.execute("INSERT INTO Student(student_id,address_zone_id,is_active,accessibility_needs) VALUES('STU-000001','ZONE-1',1,'none')")
    c.execute("INSERT INTO GuardianContact VALUES('GDN-000001','STU-000001',1,1)")
    init_schema(c)
    c.commit()
    return c


def test_safe_assignment_and_audit_event():
    c = db()
    result = assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    assert result['ok'] is True
    assert result['assignment_id'] == 'ASN-STU-000001-2026'
    assert c.execute("SELECT event_type FROM OperationalEvent").fetchone()[0] == 'assignment_created'


def test_inaccessible_vehicle_rejected():
    c = db()
    c.execute("UPDATE Student SET accessibility_needs='wheelchair' WHERE student_id='STU-000001'")
    c.execute("UPDATE Bus SET accessible=0 WHERE bus_id='BUS-000001'")
    c.commit()
    result = assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    assert result['ok'] is False and 'accessible_vehicle_required' in result['errors']
    assert c.execute('SELECT COUNT(*) FROM Assignment').fetchone()[0] == 0


def test_capacity_limit_rejected():
    c = db()
    c.execute("INSERT INTO Student(student_id,address_zone_id,is_active,accessibility_needs) VALUES('STU-000002','ZONE-1',1,'none')")
    c.commit()
    assert assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')['ok']
    assert assign_student(c, 'STU-000002', 'ROUTE-2026-000001', 'STOP-000001')['ok']
    c.execute("INSERT INTO Student(student_id,address_zone_id,is_active,accessibility_needs) VALUES('STU-000003','ZONE-1',1,'none')")
    c.commit()
    result = assign_student(c, 'STU-000003', 'ROUTE-2026-000001', 'STOP-000001')
    assert result['ok'] is False and 'bus_capacity_exceeded' in result['errors']


def test_unapproved_stop_rejected():
    c = db(); c.execute("UPDATE Stop SET is_approved=0"); c.commit()
    result = assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    assert 'stop_not_approved_or_missing' in result['errors']


def test_impossible_route_time_rejected():
    c = db(); c.execute("UPDATE RouteStop SET travel_time_from_prev_min=90"); c.commit()
    result = assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    assert 'route_travel_time_infeasible' in result['errors']


def test_attendance_creates_safe_guardian_notification():
    c = db(); assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    result = record_attendance(c, 'STU-000001', '2026-11-10', 'missed_pickup')
    assert result['ok'] and result['notification_id']
    assert c.execute("SELECT delivery_status FROM Notification").fetchone()[0] == 'sent'


def test_invalid_contact_suppresses_notification():
    c = db(); assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    c.execute("UPDATE GuardianContact SET is_valid=0"); c.commit()
    result = record_attendance(c, 'STU-000001', '2026-11-10', 'absent')
    assert result['ok'] and result['notification_id'] is None
    assert c.execute("SELECT COUNT(*) FROM Notification").fetchone()[0] == 0


def test_disruption_is_persisted_and_audited():
    c = db(); result = report_disruption(c, 'ROUTE-2026-000001', 'road_closure', '2026-11-10T07:00:00')
    assert result['ok']
    assert c.execute("SELECT status FROM RouteDisruption").fetchone()[0] == 'open'
    assert c.execute("SELECT event_type FROM OperationalEvent").fetchone()[0] == 'route_disruption_reported'


def test_pickup_window_mismatch_is_rejected_and_logged():
    c = db()
    c.execute("UPDATE Student SET pickup_window_start='09:00', pickup_window_end='09:45'")
    c.execute("UPDATE RouteStop SET pickup_window_start='06:00', pickup_window_end='06:20'")
    c.commit()
    result = assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    assert 'pickup_window_no_overlap' in result['errors']
    assert c.execute('SELECT COUNT(*) FROM PickupWindowViolation').fetchone()[0] == 1
    assert c.execute("SELECT event_type FROM OperationalEvent").fetchone()[0] == 'assignment_rejected'


def test_reassignment_retains_assignment_id_and_audits_previous_route():
    c = db()
    assert assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')['ok']
    c.execute("INSERT INTO Bus VALUES('BUS-000002',3,NULL,1,'active')")
    c.execute("INSERT INTO Driver VALUES('DRV-000002','active')")
    c.execute("INSERT INTO Route VALUES('ROUTE-2026-000002','BUS-000002','DRV-000002',1)")
    c.execute("INSERT INTO Stop VALUES('STOP-000002','ZONE-1',1)")
    c.execute("INSERT INTO RouteStop(route_stop_id,route_id,stop_id,travel_time_from_prev_min,planned_arrival_min) VALUES('RS-2','ROUTE-2026-000002','STOP-000002',10,20)")
    c.commit()
    result = assign_student(c, 'STU-000001', 'ROUTE-2026-000002', 'STOP-000002')
    assert result['ok'] and result['assignment_id'] == 'ASN-STU-000001-2026'
    assert c.execute("SELECT COUNT(*) FROM Assignment WHERE student_id='STU-000001'").fetchone()[0] == 1
    assert c.execute("SELECT event_type FROM OperationalEvent ORDER BY event_id DESC LIMIT 1").fetchone()[0] == 'assignment_reassigned'


def test_open_disruption_blocks_route_and_can_be_resolved():
    c = db()
    disruption = report_disruption(c, 'ROUTE-2026-000001', 'bus_breakdown', '2020-01-01T07:00:00')
    assert disruption['ok']
    blocked = assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')
    assert 'route_disrupted' in blocked['errors']
    resolved = resolve_disruption(c, disruption['disruption_id'])
    assert resolved['ok'] and resolved['status'] == 'resolved'
    assert assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')['ok']


def test_bus_capacity_change_is_validated_and_audited():
    c = db()
    changed = change_bus_capacity(c, 'BUS-000001', 1, 'temporary seat restriction')
    assert changed['ok'] and changed['old_capacity'] == 2 and changed['new_capacity'] == 1
    assert c.execute('SELECT new_capacity FROM BusCapacityEvent').fetchone()[0] == 1
    assert c.execute("SELECT event_type FROM OperationalEvent ORDER BY event_id DESC LIMIT 1").fetchone()[0] == 'bus_capacity_changed'
    rejected = change_bus_capacity(c, 'BUS-000001', 3, 'invalid increase')
    assert 'capacity_outside_allowed_range' in rejected['errors']


def test_capacity_cannot_be_reduced_below_active_load():
    c = db()
    c.execute("INSERT INTO Student(student_id,address_zone_id,is_active,accessibility_needs) VALUES('STU-000002','ZONE-1',1,'none')")
    c.commit()
    assert assign_student(c, 'STU-000001', 'ROUTE-2026-000001', 'STOP-000001')['ok']
    assert assign_student(c, 'STU-000002', 'ROUTE-2026-000001', 'STOP-000001')['ok']
    rejected = change_bus_capacity(c, 'BUS-000001', 1, 'unsafe reduction')
    assert any(e.startswith('capacity_below_current_load:') for e in rejected['errors'])
