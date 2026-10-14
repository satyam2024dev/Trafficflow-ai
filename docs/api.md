# REST API (prefix `/api`) – full interactive docs at `/docs`
Filters used by most traffic endpoints: `start_date`, `end_date` (YYYY-MM-DD, app timezone), `area_id`, `camera_id`, `vehicle_type`, `direction`.

| Method | Path | Purpose |
|---|---|---|
| GET | /health | DB, model, processing status |
| GET/POST | /cameras | list / create (a default counting line is added) |
| GET/PUT/DELETE | /cameras/{id} | DELETE deactivates; `?permanent=true` removes camera + events |
| GET | /cameras/{id}/snapshot | one frame for the line editor |
| GET/POST | /cameras/{id}/lines, /cameras/{id}/zones | counting lines / zones (normalised 0..1) |
| PUT/DELETE | /lines/{id} · DELETE /zones/{id} | |
| GET/POST/PUT/DELETE | /areas | |
| GET | /traffic/today · hourly · daily · weekly · monthly | headline and time series |
| GET | /traffic/by-area · by-camera · by-type · by-direction | breakdowns |
| GET | /traffic/peak-hours · trends · map | peak hours, week-over-week, per-camera live level |
| GET | /events | paginated; `page, page_size, sort_by, order, search` + filters |
| GET | /events/export | CSV of the filtered events |
| GET | /reports | `format=json|csv` |
| GET | /predictions | `area_id`, `hours` (1–24); `is_prediction: true` |
| GET | /video/files | videos in the server folder (names only) |
| POST | /video/start · /video/stop | `{ "camera_id": n }` |
| GET | /video/status · /video/stream/{camera_id} | processor state · MJPEG annotated stream |
| POST | /demo/start · /demo/reset | one-click demo |

WebSocket `/ws/traffic` messages: `hello`, `vehicle_event`, `zone_event`, `processor_state`, `error`; send `ping` → `pong`.
