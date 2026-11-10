# Acceptance Test Matrix

Last verified: 2026-11-10. Fixed seed: `20261022`.

| Requirement | Implementation / evidence | Status |
|---|---|---|
| Master data before dependent records | Generator creates zones, stops, buses, drivers, students and guardian contacts before routes/assignments/events | Pass |
| Required core entities and IDs | 11 core entities, deterministic zero-padded IDs and consistent FK references | Pass |
| Full-scale synthetic volume | 5,000 students, 100 buses, 300 stops, 150 routes, 2,264 route stops, 200 school days | Pass |
| Pickup windows | Synthetic student and route-stop windows; assignment overlap is enforced | Pass |
| Safe baseline assignments | Greedy capacity/accessibility/driver/approved-stop/zone/travel-time/window checks; 4,928 baseline assignments | Pass |
| Capacity changes | Validated capacity API, active-load guard, `BusCapacityEvent`, audit events | Pass |
| Accessibility | Wheelchair need requires accessible bus in operational assignment API | Pass |
| Route feasibility | Operational API rejects travel legs over 60 minutes; one labelled impossible-time example is injected | Pass |
| Route disruptions | Breakdown/driver/road/weather records, active disruption blocks assignment, resolution event retained | Pass |
| Attendance and missed pickup | Append-only daily attendance events; absent/missed-pickup workflow | Pass |
| Guardian notifications | Only valid primary/alternate synthetic contact receives operational notifications; invalid contact attempts are suppressed and audited | Pass |
| Address privacy | Synthetic addresses only; student API deliberately omits address-line field | Pass |
| Historical traceability | Assignment create/reassign, capacity, attendance, notification and disruption transitions append audit events | Pass |
| Labelled anomaly cases | Five required issue types are injected after baseline and stored separately in `ground_truth` | Pass |
| Ground-truth separation | Operational API and assignment decisions do not use ground-truth labels | Pass |
| PK/FK, enums, pickup windows and anomaly-label reconciliation | `validation_summary.json`; zero unlabelled anomalies | Pass |
| CSV/JSON/SQLite/README/schema | Included in project; `scripts/load_db.py` rebuilds SQLite and applies operational schema | Pass |
| Fixed-seed reproducibility | `scripts/check_reproducibility.py` runs twice and compares row counts/checksums | Pass |
| Automated acceptance tests | `python -m pytest tests/ -q` → **29 passed** | Pass |
| React UI build | React/Vite source and proxy configuration included; `npm install`/`npm run build` not run in this offline build environment | Not verified |
| Role-based authentication | Actor labels are recorded for audit, but login, authorization and separate role permissions are not implemented | Partial |
| Automatic disruption rerouting / live GPS | Dispatcher can report/resolve disruptions and manually reassign; no live GPS, traffic API or automatic route optimizer | Partial |

## Ground-truth distribution

- `bus_capacity_exceeded`: 235 assignment records
- `student_assigned_to_incompatible_route`: 1 assignment
- `impossible_travel_time`: 1 route-stop record
- `notification_sent_to_invalid_contact`: 1 notification
- `unapproved_address_exposed`: 4 records across zone/stop/student entities

The full synthetic dataset intentionally contains these labelled negative examples. They are not accepted by the operational assignment workflow. The operational API validates new decisions; the anomaly records remain available for evaluation.

## Reproduction commands

```bash
python data_generator/generate_data.py
python scripts/check_reproducibility.py
python scripts/load_db.py
python -m pytest tests/ -q
```
