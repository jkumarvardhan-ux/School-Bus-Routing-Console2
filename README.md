# School Bus Routing & Student Assignment System

**Full working solution** for assigning students to routes and stops while respecting bus capacity, pickup windows, safety (accessibility), and attendance updates.

Fixed seed: **20261022** · Full volume: **5,000 students · 100 buses · 300 stops · 200 school days**

---

## 1. Business Context

District transportation teams must:

- Assign every active student to a stop and a route.
- Never silently exceed bus capacity (overflows are labelled).
- Match accessibility needs (wheelchair → accessible vehicle).
- Keep route stop sequences travel-time feasible.
- Reflect daily attendance and missed pickups across 200 school days.
- Notify guardians via synthetic contact records.
- Expose every exception with a ground-truth label for audit and evaluation.

The system preserves history (no destructive overwrites), uses deterministic IDs, and separates ground-truth labels from operational data.

---

## 2. Project Structure

```
school_bus_routing/
├── backend/
│   └── server.py              # Stdlib HTTP API + static server (port 8080)
├── frontend/
│   ├── index.html             # Dashboard UI
│   ├── app.js
│   └── styles.css
├── data_generator/
│   ├── generate_data.py       # Single-source generator (seed 20261022)
│   └── data_dictionary.md     # Full field-level data dictionary
├── data/                      # Generated artifacts (CSV + JSON + SQLite)
│   ├── *.csv / *.json
│   ├── ground_truth.csv/json
│   ├── manifest.json
│   ├── validation_summary.json
│   └── checksums.json
├── scripts/
│   ├── load_db.py
│   └── check_reproducibility.py
├── tests/
│   ├── test_generator.py
│   └── test_api.py
├── requirements.txt
└── README.md
```

---

## 3. Entities & Relationships

| Entity            | PK              | Cardinality / Notes                                      |
|-------------------|-----------------|----------------------------------------------------------|
| Student           | student_id      | 1:N GuardianContact, 1:N Assignment                      |
| GuardianContact   | contact_id      | N:1 Student                                              |
| AddressZone       | zone_id         | 1:N Stop, 1:N Student                                    |
| Stop              | stop_id         | N:M Route via RouteStop; 1:N Assignment                  |
| Bus               | bus_id          | 1:N Route                                                |
| Driver            | driver_id       | 1:N Route (optional)                                     |
| Route             | route_id        | 1:N RouteStop, 1:N Assignment                            |
| RouteStop         | route_stop_id   | N:1 Route, N:1 Stop                                      |
| Assignment        | assignment_id   | N:1 Student, N:1 Route, N:1 Stop                         |
| AttendanceEvent   | event_id        | N:1 Student, N:1 Assignment                              |
| Notification      | notification_id | N:1 Student, N:1 GuardianContact                         |

All relationships use foreign keys. Event history is retained. Bridge table RouteStop models the N:M between Route and Stop.

---

## 4. ID Conventions (immutable)

- `STU-000001` … `STU-005000`
- `STOP-000001` … `STOP-000300`
- `BUS-000001` … `BUS-000100`
- `DRV-000001` …
- `ZONE-000001` …
- `ROUTE-2026-000001` …
- `ASN-<student_id>-2026`
- `NOT-2026-000001` …
- `ATT-000001` …, `RS-000001` …, `GDN-000001` …

---

## 5. Required Edge Cases (all labelled in ground_truth)

| issue_type                              | Present | Count (approx) |
|-----------------------------------------|---------|----------------|
| bus_capacity_exceeded                   | Yes     | 235            |
| student_assigned_to_incompatible_route  | Yes     | 1              |
| impossible_travel_time                  | Yes     | 1              |
| notification_sent_to_invalid_contact    | Yes     | 1              |
| unapproved_address_exposed              | Yes     | 4              |

---

## 6. How to Generate / Validate

```bash
# Generate (deterministic)
cd data_generator
python3 generate_data.py

# Reproducibility (run twice, compare checksums)
python3 ../scripts/check_reproducibility.py

# Unit tests
cd ..
python3 -m pytest tests/ -v

# Load SQLite (optional)
python3 scripts/load_db.py
```

Fixed seed = **20261022**. Starter scale: set `SCALE = 0.1` inside the generator.

---

## 7. Validation & Acceptance

Automatic checks (see `data/validation_summary.json`):

- Primary-key uniqueness for every table
- Foreign-key integrity
- Allowed enums / grade ranges / attendance statuses
- Capacity reconciliation (routes over capacity + overflow seat count)
- Date coverage (200 unique school days in AttendanceEvent)
- All five required ground-truth issue types present

Current run: **zero unlabelled anomalies**, `fk_ok: true`; all deliberate negative examples are accounted for in the separate ground-truth file.

---

## 8. Quick Metrics (Full Scale)

| Metric                        | Value    |
|-------------------------------|----------|
| Students                      | 5 000    |
| Assignments                   | 4 928    |
| Guardian contacts             | 7 764    |
| Buses                         | 100      |
| Stops                         | 300      |
| Routes                        | 150      |
| Route stops                   | 2 264    |
| School days                   | 200      |
| Attendance events             | 275 800  |
| Notifications                 | 35 453   |
| Ground-truth labelled issues  | 242      |
| Capacity overflows (labelled) | 235      |
| Incompatible assignments      | 1        |

---

## 9. Data Dictionary

See `data_generator/data_dictionary.md` for complete field-level specifications (type, required, allowed values, units, uniqueness, validation rules, cardinalities).

---

## 10. Provenance & Licensing

- **100 % synthetic**. No real student, guardian or vehicle data.
- Fixed seed guarantees reproducible CSVs (checksums provided).
- External public reference data used only for schema inspiration; none redistributed.
- Suitable for academic, research and systems evaluation under typical synthetic-data terms.

---

The generator first builds capacity-, accessibility-, driver-, stop-, travel-time- and pickup-window-compatible baseline assignments, then deliberately injects a small set of negative examples and labels every resulting anomaly in `ground_truth`. The baseline data package covers the requested synthetic entities, scale, labelled anomaly categories, separate ground truth, validation and reproducibility. The operational workflow extension adds enforceable assignment, attendance, disruption and audit behavior; see the evaluation boundary above for remaining production-grade controls.

---

## 11. Operational workflow upgrade (November 2026)

The project now includes transactional API workflows in `backend/operations.py` and an Operations & Audit screen in the dashboard.

### Start the application

```bash
python scripts/load_db.py   # optional; rebuilds DB from CSV and applies additive operational schema
python backend/server.py    # http://localhost:8080
```

### Operational API

- `POST /api/assign` — create or reassign a student. Enforces active student/route/bus/driver, capacity (effective override), accessible vehicle for wheelchair need, approved stop, stop-on-route, zone match, route travel-time threshold, pickup-window overlap and no duplicate assignment to the same stop. Reassignments retain the immutable assignment ID and append a before/after `OperationalEvent`.
- `POST /api/attendance` — append attendance event for a currently assigned student. Absent/missed-pickup notifications are sent only to a valid primary synthetic guardian contact; otherwise notification is suppressed and audited.
- `POST /api/disruptions` — append route disruption (breakdown, driver unavailable, road closure, weather) and audit the event. Active disruptions block new assignments on that route.
- `POST /api/disruptions/resolve` — resolve a disruption and append a resolution audit event; dispatchers can then assign/reassign students onto the available route.
- `POST /api/bus-capacity` — record a bus capacity change, reject reductions below current active route load, update the effective override and append a `BusCapacityEvent` plus audit event.
- `GET /api/bus-capacity-events` — inspect the capacity-change history.
- `GET /api/operational_events` — read append-only audit history.
- `GET /api/disruptions` — read disruption history.

The database migration adds synthetic-only `Student.address_line`, student pickup windows and route-stop pickup windows. The data generator now emits these fields for future full regenerations. Existing supplied CSV/JSON snapshots remain the original baseline snapshot; run the generator and then `scripts/load_db.py` to regenerate a complete fresh snapshot with the new fields.

### Operational test coverage

Run:

```bash
python -m pytest tests/ -q
```

Current suite: **29 tests passing**, including 13 operational workflow tests plus data integrity and reproducibility coverage for safe assignment, accessibility rejection, capacity boundary, unapproved stops, impossible route travel time, attendance-triggered safe notification, invalid-contact suppression and disruption audit history.

### Important evaluation boundary

The generator creates a valid baseline first, then injects a small, explicit set of labelled negative examples. The resulting full-scale synthetic snapshot intentionally contains labelled negative examples (capacity overflow, accessibility incompatibility, long travel legs, invalid notification targets and unapproved address/stop references) for anomaly-detection evaluation. Those rows are not safe operational assignments. The new operational API rejects unsafe new assignment decisions; the ground-truth table remains separate. The supplied historical snapshot is not silently rewritten by the workflow upgrade. This is a synthetic academic prototype, not a production student-transport dispatch system; real deployment would additionally require authenticated role-based access, encryption, consent/retention controls, geospatial travel-time services, live vehicle telemetry and jurisdiction-specific safeguarding review.

### React dashboard (Vite)

A React 18 + Vite dashboard is included in `frontend/react/` alongside the lightweight legacy dashboard.

```bash
# Terminal 1
python backend/server.py

# Terminal 2
cd frontend/react
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` calls to the Python service on port 8080. The React app includes assignment/reassignment, attendance, disruption reporting/resolution, capacity changes, operational metrics and audit/disruption tables. The React app source is included; dependency installation/build must be performed in an environment with npm registry access.
