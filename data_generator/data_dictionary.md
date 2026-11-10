# Data Dictionary — School Bus Routing & Assignment System

Fixed seed: 20261022  
ID Conventions: STU-000001, STOP-000001, BUS-000001, ROUTE-2026-000001, ASN-<student-id>-2026, NOT-2026-000001, DRV-000001, ZONE-000001

## 1. Student
| Field | Type | Required | Allowed Values / Units | Uniqueness | Validation |
|-------|------|----------|------------------------|------------|------------|
| student_id | TEXT | Y | STU-XXXXXX | PK | Pattern ^STU-\d{6}$ |
| first_name | TEXT | Y | synthetic name | - | non-empty |
| last_name | TEXT | Y | synthetic name | - | non-empty |
| grade | INTEGER | Y | 1-12 | - | 1 ≤ grade ≤ 12 |
| date_of_birth | DATE | Y | YYYY-MM-DD | - | age 5-18 consistent with grade |
| accessibility_needs | TEXT | N | none, wheelchair, visual, hearing, other | - | enum |
| address_zone_id | TEXT | Y | ZONE-XXXXXX | FK → AddressZone | must exist |
| is_active | BOOLEAN | Y | true/false | - | default true |
| created_at | TIMESTAMP | Y | ISO8601 | - | ≤ now |
| effective_from | DATE | Y | YYYY-MM-DD | - | - |
| effective_to | DATE | N | YYYY-MM-DD | - | ≥ effective_from or null |

**Cardinality**: Student 1:N GuardianContact; Student N:1 AddressZone; Student 1:N Assignment; Student 1:N AttendanceEvent

## 2. GuardianContact
| Field | Type | Required | Allowed Values | Uniqueness | Validation |
|-------|------|----------|----------------|------------|------------|
| contact_id | TEXT | Y | GDN-XXXXXX | PK | Pattern ^GDN-\d{6}$ |
| student_id | TEXT | Y | STU-XXXXXX | FK | must exist |
| name | TEXT | Y | - | - | non-empty |
| relationship | TEXT | Y | parent, guardian, other | - | enum |
| phone | TEXT | Y | synthetic E.164-like | - | format +1XXXXXXXXXX |
| email | TEXT | N | synthetic | - | valid email format |
| is_primary | BOOLEAN | Y | true/false | - | at least one primary per student preferred |
| is_valid | BOOLEAN | Y | true/false | - | for edge cases set false |
| created_at | TIMESTAMP | Y | ISO8601 | - | - |

**Cardinality**: GuardianContact N:1 Student

## 3. AddressZone
| Field | Type | Required | Allowed Values | Uniqueness | Validation |
|-------|------|----------|----------------|------------|------------|
| zone_id | TEXT | Y | ZONE-XXXXXX | PK | Pattern ^ZONE-\d{6}$ |
| zone_name | TEXT | Y | - | unique | non-empty |
| centroid_lat | REAL | Y | -90..90 | - | decimal degrees |
| centroid_lon | REAL | Y | -180..180 | - | decimal degrees |
| is_approved | BOOLEAN | Y | true/false | - | false for unapproved edge case |
| school_district | TEXT | Y | - | - | - |
| created_at | TIMESTAMP | Y | ISO8601 | - | - |

**Cardinality**: AddressZone 1:N Student; AddressZone N:M Stop (via approved mapping logic)

## 4. Stop
| Field | Type | Required | Allowed Values / Units | Uniqueness | Validation |
|-------|------|----------|------------------------|------------|------------|
| stop_id | TEXT | Y | STOP-XXXXXX | PK | Pattern ^STOP-\d{6}$ |
| stop_name | TEXT | Y | - | - | non-empty |
| lat | REAL | Y | -90..90 | - | - |
| lon | REAL | Y | -180..180 | - | - |
| address_zone_id | TEXT | Y | ZONE-XXXXXX | FK | must exist |
| is_approved | BOOLEAN | Y | true/false | - | - |
| capacity_hint | INTEGER | N | ≥0 | - | soft limit |
| created_at | TIMESTAMP | Y | ISO8601 | - | - |

**Cardinality**: Stop N:1 AddressZone; Stop 1:N RouteStop; Stop 1:N Assignment

## 5. Bus
| Field | Type | Required | Allowed Values / Units | Uniqueness | Validation |
|-------|------|----------|------------------------|------------|------------|
| bus_id | TEXT | Y | BUS-XXXXXX | PK | Pattern ^BUS-\d{6}$ |
| plate_number | TEXT | Y | synthetic | unique | - |
| capacity | INTEGER | Y | 20-72 | - | seats |
| accessible | BOOLEAN | Y | true/false | - | wheelchair capable |
| status | TEXT | Y | active, maintenance, retired | - | enum |
| current_capacity_override | INTEGER | N | ≥0 | - | for capacity change events |
| created_at | TIMESTAMP | Y | ISO8601 | - | - |

**Cardinality**: Bus 1:N Route (over time); Bus N:1 Driver (optional)

## 6. Driver
| Field | Type | Required | Allowed Values | Uniqueness | Validation |
|-------|------|----------|----------------|------------|------------|
| driver_id | TEXT | Y | DRV-XXXXXX | PK | Pattern ^DRV-\d{6}$ |
| name | TEXT | Y | - | - | non-empty |
| license_number | TEXT | Y | synthetic | unique | - |
| phone | TEXT | Y | - | - | - |
| status | TEXT | Y | active, leave, terminated | - | enum |
| hired_date | DATE | Y | YYYY-MM-DD | - | - |
| created_at | TIMESTAMP | Y | ISO8601 | - | - |

**Cardinality**: Driver 1:N Route (assignment over time)

## 7. Route
| Field | Type | Required | Allowed Values | Uniqueness | Validation |
|-------|------|----------|----------------|------------|------------|
| route_id | TEXT | Y | ROUTE-2026-XXXXXX | PK | Pattern ^ROUTE-2026-\d{6}$ |
| route_name | TEXT | Y | - | - | non-empty |
| bus_id | TEXT | Y | BUS-XXXXXX | FK | must exist |
| driver_id | TEXT | N | DRV-XXXXXX | FK | optional |
| school_id | TEXT | Y | SCH-001 | - | fixed for simplicity |
| direction | TEXT | Y | morning, afternoon | - | enum |
| is_active | BOOLEAN | Y | true/false | - | - |
| effective_from | DATE | Y | YYYY-MM-DD | - | - |
| effective_to | DATE | N | YYYY-MM-DD | - | - |
| created_at | TIMESTAMP | Y | ISO8601 | - | - |

**Cardinality**: Route N:1 Bus; Route N:1 Driver; Route 1:N RouteStop; Route 1:N Assignment

## 8. RouteStop (bridge + sequence)
| Field | Type | Required | Allowed Values / Units | Uniqueness | Validation |
|-------|------|----------|------------------------|------------|------------|
| route_stop_id | TEXT | Y | RS-XXXXXX | PK | - |
| route_id | TEXT | Y | ROUTE-... | FK | - |
| stop_id | TEXT | Y | STOP-... | FK | - |
| sequence | INTEGER | Y | ≥1 | unique per route | ordered |
| planned_arrival_min | INTEGER | Y | minutes from start | - | increasing with sequence (except edge cases) |
| travel_time_from_prev_min | INTEGER | Y | ≥0 | - | realistic or labelled anomaly |
| created_at | TIMESTAMP | Y | ISO8601 | - | - |

**Cardinality**: RouteStop N:1 Route; RouteStop N:1 Stop  (M:N via this bridge)

## 9. Assignment
| Field | Type | Required | Allowed Values | Uniqueness | Validation |
|-------|------|----------|----------------|------------|------------|
| assignment_id | TEXT | Y | ASN-STU-XXXXXX-2026 | PK | Pattern ASN-STU-\d{6}-2026 |
| student_id | TEXT | Y | STU-... | FK | - |
| route_id | TEXT | Y | ROUTE-... | FK | - |
| stop_id | TEXT | Y | STOP-... | FK | must be on route |
| school_year | TEXT | Y | 2026 | - | - |
| assigned_at | TIMESTAMP | Y | ISO8601 | - | - |
| status | TEXT | Y | active, pending, cancelled | - | enum |
| is_compatible | BOOLEAN | Y | true/false | - | false for edge case |
| notes | TEXT | N | - | - | - |

**Cardinality**: Assignment N:1 Student; Assignment N:1 Route; Assignment N:1 Stop

## 10. AttendanceEvent
| Field | Type | Required | Allowed Values | Uniqueness | Validation |
|-------|------|----------|----------------|------------|------------|
| event_id | TEXT | Y | ATT-XXXXXX | PK | - |
| student_id | TEXT | Y | STU-... | FK | - |
| assignment_id | TEXT | Y | ASN-... | FK | - |
| event_date | DATE | Y | YYYY-MM-DD | - | within school days |
| status | TEXT | Y | present, absent, missed_pickup, late | - | enum |
| recorded_at | TIMESTAMP | Y | ISO8601 | - | - |
| notes | TEXT | N | - | - | - |

**Cardinality**: AttendanceEvent N:1 Student; AttendanceEvent N:1 Assignment  
History retained; no overwrite.

## 11. Notification
| Field | Type | Required | Allowed Values | Uniqueness | Validation |
|-------|------|----------|----------------|------------|------------|
| notification_id | TEXT | Y | NOT-2026-XXXXXX | PK | Pattern ^NOT-2026-\d{6}$ |
| student_id | TEXT | Y | STU-... | FK | - |
| contact_id | TEXT | Y | GDN-... | FK | may be invalid for edge |
| event_type | TEXT | Y | missed_pickup, capacity_alert, route_change, attendance | - | enum |
| message | TEXT | Y | - | - | - |
| sent_at | TIMESTAMP | Y | ISO8601 | - | - |
| delivery_status | TEXT | Y | sent, failed, pending | - | enum |
| related_event_id | TEXT | N | ATT-... or other | - | - |

**Cardinality**: Notification N:1 Student; Notification N:1 GuardianContact

## Ground Truth
Separate file `ground_truth.csv` containing:
- entity_type, entity_id, issue_type, description, expected_decision, severity
Never mixed into operational tables as features.

## Operational workflow extension (added)

| Entity / field | Type | Required | Allowed / units | Uniqueness | Validation |
|---|---|---:|---|---|---|
| Student.address_line | TEXT | Yes | Synthetic street/unit text; no real address | No | Must be synthetic; never use real learner addresses |
| Student.pickup_window_start | TEXT | Yes | Local `HH:MM` | No | Valid 24-hour time; earlier than end |
| Student.pickup_window_end | TEXT | Yes | Local `HH:MM` | No | Valid 24-hour time; later than start |
| RouteStop.pickup_window_start | TEXT | Yes | Local `HH:MM` | No | Valid 24-hour time; overlaps assigned student's window |
| RouteStop.pickup_window_end | TEXT | Yes | Local `HH:MM` | No | Valid 24-hour time; later than start |
| OperationalEvent.event_id | INTEGER | Yes | Auto-increment | PK | Append-only audit record |
| OperationalEvent.entity_type | TEXT | Yes | Student, Assignment, Route, AttendanceEvent, Notification | No | Identifies affected entity |
| OperationalEvent.entity_id | TEXT | Yes | Existing entity ID | No | Must refer to the recorded entity |
| OperationalEvent.event_type | TEXT | Yes | Workflow event name | No | Never overwrite prior event |
| OperationalEvent.event_at | TEXT | Yes | ISO-8601 UTC | No | Timestamp of state transition |
| OperationalEvent.actor | TEXT | Yes | Synthetic role/system label | No | No real staff PII |
| OperationalEvent.details_json | TEXT | Yes | JSON | No | Captures before/after and decision facts |
| RouteDisruption.disruption_id | INTEGER | Yes | Auto-increment | PK | Append-only disruption record |
| RouteDisruption.route_id | TEXT | Yes | Route ID | No | FK to Route; start <= end |
| RouteDisruption.disruption_type | TEXT | Yes | bus_breakdown, driver_unavailable, road_closure, weather | No | Controlled enum |
| RouteDisruption.status | TEXT | Yes | open, resolved | No | Lifecycle state |
| PickupWindowViolation.violation_id | INTEGER | Yes | Auto-increment | PK | Stores rejected pickup-window requests |

Operational cardinalities: Student 1:N GuardianContact; Student 1:N Assignment over history (one active assignment per school year in this implementation); Route 1:N RouteStop; Stop 1:N RouteStop; Bus 1:N Route; Driver 1:N Route; Assignment 1:N AttendanceEvent; AttendanceEvent 1:N Notification; all operational state transitions 1:N OperationalEvent. `OperationalEvent` and `RouteDisruption` are append-only history. Assignment's current route/stop may change, but every create/reassignment is retained in the audit event log.

| Entity / field | Type | Required | Allowed / units | Uniqueness | Validation |
|---|---|---:|---|---|---|
| BusCapacityEvent.capacity_event_id | INTEGER | Yes | Auto-increment | PK | Append-only capacity change record |
| BusCapacityEvent.bus_id | TEXT | Yes | Bus ID | No | FK to Bus |
| BusCapacityEvent.old_capacity | INTEGER | Yes | Seats | No | Prior effective capacity |
| BusCapacityEvent.new_capacity | INTEGER | Yes | Seats | No | 1..nominal Bus.capacity; cannot be below active load |
| BusCapacityEvent.effective_at | TEXT | Yes | ISO-8601 UTC | No | Change timestamp |
| BusCapacityEvent.reason | TEXT | Yes | Short reason | No | Required explanation |
| BusCapacityEvent.actor | TEXT | Yes | Synthetic role/system label | No | No real staff PII |
