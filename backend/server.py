#!/usr/bin/env python3
"""
Lightweight HTTP API + static file server for School Bus Routing dashboard.
Uses only Python stdlib + sqlite3.
"""

import json
import sqlite3
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
try:
    from .operations import init_schema, assign_student, record_attendance, report_disruption, resolve_disruption, change_bus_capacity
except ImportError:
    from operations import init_schema, assign_student, record_attendance, report_disruption, resolve_disruption, change_bus_capacity

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "school_bus.db"
FRONTEND = ROOT / "frontend"
PORT = int(os.environ.get("PORT", "8080"))

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn

def rows_to_list(rows):
    return [dict(r) for r in rows]

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self.error(404, "Unknown endpoint")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            conn = get_db()
            if parsed.path == "/api/assign":
                result = assign_student(conn, payload.get("student_id", ""), payload.get("route_id", ""), payload.get("stop_id", ""), payload.get("actor", "dispatcher"))
            elif parsed.path == "/api/attendance":
                result = record_attendance(conn, payload.get("student_id", ""), payload.get("event_date", ""), payload.get("status", ""), payload.get("actor", "school_staff"), payload.get("notes"))
            elif parsed.path == "/api/disruptions":
                result = report_disruption(conn, payload.get("route_id", ""), payload.get("disruption_type", ""), payload.get("starts_at", ""), payload.get("ends_at"), payload.get("notes"), payload.get("actor", "dispatcher"))
            elif parsed.path == "/api/disruptions/resolve":
                result = resolve_disruption(conn, payload.get("disruption_id"), payload.get("actor", "dispatcher"))
            elif parsed.path == "/api/bus-capacity":
                result = change_bus_capacity(conn, payload.get("bus_id", ""), payload.get("new_capacity"), payload.get("reason", ""), payload.get("actor", "fleet_admin"))
            else:
                conn.close()
                return self.error(404, "Unknown API endpoint")
            conn.close()
            self.json_response(result, 200 if result.get("ok") else 422)
        except (ValueError, json.JSONDecodeError) as e:
            self.error(400, str(e))
        except Exception as e:
            self.error(500, str(e))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path.startswith("/api/"):
            self.handle_api(path, qs)
        else:
            # Static files
            if path == "/" or path == "":
                self.path = "/index.html"
            return super().do_GET()

    def handle_api(self, path, qs):
        try:
            conn = get_db()
            cur = conn.cursor()
            limit = int(qs.get("limit", [50])[0])
            offset = int(qs.get("offset", [0])[0])
            q = qs.get("q", [""])[0].strip()

            if path == "/api/stats":
                stats = {}
                for table in ["Student", "Bus", "Stop", "Route", "Assignment", "AttendanceEvent", "Notification", "ground_truth"]:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table.lower()] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM Assignment WHERE is_compatible = 0")
                stats["incompatible_assignments"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM Assignment WHERE notes = 'capacity_exceeded'")
                stats["capacity_exceeded"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM ground_truth WHERE severity = 'high'")
                stats["high_severity_issues"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM AttendanceEvent WHERE status = 'missed_pickup'")
                stats["missed_pickups"] = cur.fetchone()[0]
                self.json_response(stats)

            elif path == "/api/students":
                if q:
                    cur.execute(
                        "SELECT student_id,first_name,last_name,grade,date_of_birth,accessibility_needs,address_zone_id,is_active,effective_from,effective_to FROM Student WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? LIMIT ? OFFSET ?",
                        (f"%{q}%", f"%{q}%", f"%{q}%", limit, offset)
                    )
                else:
                    cur.execute("SELECT student_id,first_name,last_name,grade,date_of_birth,accessibility_needs,address_zone_id,is_active,effective_from,effective_to FROM Student LIMIT ? OFFSET ?", (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/routes":
                cur.execute("""
                    SELECT r.*, b.capacity, b.accessible, b.plate_number,
                           (SELECT COUNT(*) FROM Assignment a WHERE a.route_id = r.route_id) as assigned_count
                    FROM Route r
                    LEFT JOIN Bus b ON r.bus_id = b.bus_id
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/route_detail":
                rid = qs.get("id", [None])[0]
                if not rid:
                    return self.error(400, "id required")
                cur.execute("SELECT * FROM Route WHERE route_id = ?", (rid,))
                route = cur.fetchone()
                if not route:
                    return self.error(404, "not found")
                cur.execute("""
                    SELECT rs.*, s.stop_name, s.lat, s.lon
                    FROM RouteStop rs JOIN Stop s ON rs.stop_id = s.stop_id
                    WHERE rs.route_id = ? ORDER BY rs.sequence
                """, (rid,))
                stops = rows_to_list(cur.fetchall())
                cur.execute("""
                    SELECT a.*, st.first_name, st.last_name, st.grade, st.accessibility_needs
                    FROM Assignment a JOIN Student st ON a.student_id = st.student_id
                    WHERE a.route_id = ? LIMIT 200
                """, (rid,))
                assigns = rows_to_list(cur.fetchall())
                self.json_response({"route": dict(route), "stops": stops, "assignments": assigns})

            elif path == "/api/assignments":
                cur.execute("""
                    SELECT a.*, s.first_name, s.last_name, s.grade, s.accessibility_needs,
                           r.route_name, st.stop_name
                    FROM Assignment a
                    JOIN Student s ON a.student_id = s.student_id
                    JOIN Route r ON a.route_id = r.route_id
                    JOIN Stop st ON a.stop_id = st.stop_id
                    ORDER BY a.assignment_id
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/exceptions":
                cur.execute("SELECT * FROM ground_truth ORDER BY severity DESC, issue_type LIMIT ? OFFSET ?", (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/attendance":
                status = qs.get("status", [None])[0]
                if status:
                    cur.execute(
                        "SELECT * FROM AttendanceEvent WHERE status = ? ORDER BY event_date DESC LIMIT ? OFFSET ?",
                        (status, limit, offset)
                    )
                else:
                    cur.execute("SELECT * FROM AttendanceEvent ORDER BY event_date DESC LIMIT ? OFFSET ?", (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/notifications":
                cur.execute("SELECT * FROM Notification ORDER BY sent_at DESC LIMIT ? OFFSET ?", (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/operational_events":
                cur.execute("SELECT * FROM OperationalEvent ORDER BY event_at DESC LIMIT ? OFFSET ?", (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/disruptions":
                cur.execute("SELECT * FROM RouteDisruption ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/bus-capacity-events":
                cur.execute("SELECT * FROM BusCapacityEvent ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/buses":
                cur.execute("""
                    SELECT b.*,
                           (SELECT COUNT(*) FROM Route r WHERE r.bus_id = b.bus_id AND r.is_active = 1) as active_routes
                    FROM Bus b
                """)
                self.json_response(rows_to_list(cur.fetchall()))

            elif path == "/api/capacity_overview":
                cur.execute("""
                    SELECT r.route_id, r.route_name, b.bus_id, b.capacity,
                           COALESCE(b.current_capacity_override, b.capacity) as effective_cap,
                           COUNT(a.assignment_id) as load,
                           CASE WHEN COUNT(a.assignment_id) > COALESCE(b.current_capacity_override, b.capacity)
                                THEN 1 ELSE 0 END as over_capacity
                    FROM Route r
                    JOIN Bus b ON r.bus_id = b.bus_id
                    LEFT JOIN Assignment a ON a.route_id = r.route_id
                    GROUP BY r.route_id
                    ORDER BY over_capacity DESC, load DESC
                """)
                self.json_response(rows_to_list(cur.fetchall()))

            else:
                self.error(404, "Unknown API endpoint")

            conn.close()
        except Exception as e:
            self.error(500, str(e))

    def json_response(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def error(self, code, msg):
        self.json_response({"error": msg}, code)

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

def main():
    if not DB_PATH.exists():
        print("ERROR: Database not found at", DB_PATH)
        print("Run data_generator/generate_data.py and load script first.")
        return
    os.chdir(FRONTEND)
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"School Bus Routing Dashboard running at http://localhost:{PORT}")
    print("API base: /api/stats  /api/routes  /api/exceptions  /api/capacity_overview ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")

if __name__ == "__main__":
    main()
