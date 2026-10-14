# TrafficFlow AI
**AI-powered vehicle flow monitoring and urban traffic analytics**

TrafficFlow AI turns ordinary traffic video into structured, privacy-friendly traffic data: it detects vehicles with YOLO, tracks each one with ByteTrack, counts them when they cross a virtual line or enter a zone, stores anonymous events in PostgreSQL and shows live and historical analytics in a React dashboard.

## Problem
Cities already have cameras, but raw video is not data. Nobody can query "how many trucks used this road between 5 and 7 pm last Tuesday?" from hours of footage.

## Solution
```
video file / webcam / RTSP
        │
   YOLO detection ──► ByteTrack tracking ──► line + zone counting     (ai/)
        │                                          │
        └──────────── annotated MJPEG ◄────────────┤
                                                   ▼
                          queue ─► PostgreSQL (events + hourly roll-up)   (backend/)
                                                   │
                              WebSocket + REST ────┴──► React dashboard    (frontend/)
```
AI inference runs in a background thread per camera, never on the web server's event loop. The `ai/` package has no web or database dependencies, so it can later run on an edge device and publish events to the API.

## Features
- Real YOLO detection (car, motorcycle, bus, truck; class mapping configurable), ByteTrack/BoT-SORT tracking
- Counting lines with direction (each vehicle counted once per line) and polygon zones (enter / exit / currently inside)
- Multi-camera data model: areas, cameras, per-camera lines and zones
- PostgreSQL storage with indexes; hourly roll-up table kept in the same transaction as each event
- Analytics: today, by type / area / camera / direction, hourly, daily, weekly, monthly, peak hours, trends
- Prediction: transparent same-weekday/hour averages with LOW/MODERATE/HIGH/CRITICAL status (clearly labelled as a prediction)
- Dashboard: live counters, charts (Recharts), Leaflet/OpenStreetMap map coloured by traffic level, live feed, dark/light theme
- Historical data: filter, search, sort, paginate, export CSV; reports as CSV or print-to-PDF
- Camera management, line/zone editor drawn on a video snapshot
- One-click demo mode

## Privacy
Only anonymous events are stored: vehicle type, tracker ID, camera, area, direction, confidence, timestamp. **No license plates, no faces, no video frames, no appearance embeddings** (BoT-SORT ReID is disabled). Tracker IDs are temporary numbers that restart with each run and cannot identify a vehicle or person. Video is processed in memory and only a live annotated preview is streamed to your dashboard.

## Technology
Python · OpenCV · Ultralytics YOLO · FastAPI · SQLAlchemy · PostgreSQL · React · Vite · Tailwind CSS · Recharts · Leaflet + OpenStreetMap

## Installation (Windows, VS Code)
Prerequisites: Python 3.10–3.12, Node.js 20+, PostgreSQL 14+ (or Docker Desktop), Git.

### 1. Python
```powershell
cd trafficflow-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r backend\requirements.txt
```
On Windows, `pip` installs a CPU build of PyTorch automatically. A GPU is optional (`YOLO_DEVICE=0`).

### 2. PostgreSQL
Option A – Docker (simplest): put `POSTGRES_PASSWORD` in `.env` (step 3), then
```powershell
docker compose up -d db
```
Option B – installed PostgreSQL (use *SQL Shell (psql)* as the `postgres` user):
```sql
CREATE USER trafficflow WITH PASSWORD 'choose_a_password';
CREATE DATABASE trafficflow OWNER trafficflow;
CREATE DATABASE trafficflow_test OWNER trafficflow;   -- only needed to run the tests
```
Tables are created automatically on first start. `database/schema.sql` and `seed.sql` are the same schema/seed for manual use (`psql -U trafficflow -d trafficflow -f database\schema.sql`).

### 3. Environment variables
```powershell
copy .env.example .env
notepad .env        # set POSTGRES_PASSWORD (and APP_TIMEZONE, e.g. Asia/Kolkata)
```
`.env` is git-ignored. See `.env.example` for every option (confidence threshold, tracker, frame skip, resolution, device…).

### 4. YOLO model
```powershell
python scripts\download_model.py            # downloads yolo11n.pt (5.6 MB) into ai\models\
```
Any Ultralytics model works: set `YOLO_MODEL` in `.env`. For a custom model set `YOLO_VEHICLE_CLASSES` (e.g. `0:car,1:rickshaw`).

### 5. A traffic video
Copy a clip of a road filmed from above or at an angle into `videos\` and name it **`demo.mp4`** (or any name; `.mp4 .avi .mov .mkv .webm`). Free sources: Pexels, Pixabay, or your own phone footage of a road. *No sample video is bundled* – use footage you have the right to use. Best results: cars clearly visible, camera fixed.

### 6. Run
Terminal 1 – backend:
```powershell
cd backend
uvicorn app.main:app --port 8000
```
Terminal 2 – frontend:
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. API docs: http://localhost:8000/docs.

## Demo mode
1. Open the dashboard and press **Start demo** (or Settings → Demo tools). It processes `videos/demo.mp4` on "Demo Camera 1" and jumps to Live Monitoring.
2. You will see boxes, `#ID type confidence` labels, the red counting line and the blue zone. Each crossing increments the count, is written to PostgreSQL and appears in the live feed; charts refresh within a second.
3. Check Historical Data (events) and Analytics. **Reset demo data** clears only the demo camera's rows so you can start from zero.

Tip for CPU-only laptops: if processing lags, raise `FRAME_SKIP` (e.g. 3) or lower `PROCESS_WIDTH` (e.g. 640) in `.env` and restart the backend. With `REALTIME_PLAYBACK=true` the processor drops frames to stay in sync with video time; set it to `false` to process as fast as possible.

## Adjusting the counting line
Live Monitoring → **Lines & zones**. Click two points on the snapshot. The green arrow shows which direction "Label A" refers to (vehicles crossing towards the arrow); rename the labels (e.g. northbound/southbound, inbound/outbound). Changes apply the next time processing starts.

## Running the tests
```powershell
pytest tests            # 60 tests; needs the trafficflow_test database from step 2
cd frontend; npx vitest run     # page smoke tests; needs the backend running (BACKEND_URL defaults to http://127.0.0.1:8000)
```
The tests refuse to run against any database not ending in `_test`. The AI pipeline tests use a **synthetic video with a simple colour-blob detector standing in for YOLO** (test code only, `tests/ai/synthetic.py`), so the plumbing is testable without a model.

## API
Interactive docs at `/docs`. Summary in [docs/api.md](docs/api.md). WebSocket: `/ws/traffic` (`vehicle_event`, `processor_state`, `zone_event`, `error`).

## Database
`areas`, `cameras`, `counting_lines`, `zones`, `vehicle_events`, `zone_events`, `traffic_summaries` – see `database/schema.sql`. Indexes on timestamp, camera, area and vehicle type.

## Known limitations (honest list)
- **Webcam and RTSP** sources are implemented (open, read, reconnect) but not production-tested. Video files are the verified path.
- **Speed** column exists but is NULL: no calibrated speed estimation.
- **Prediction** is a historical-average estimate; it needs real days of data to be meaningful and says so when data is thin.
- Event timestamps are the wall-clock time of the crossing, not the video's recording time.
- Counting accuracy depends on video quality, camera angle and the YOLO model (nano model by default for CPU speed). Occlusions can cause ID switches; a vehicle is counted once per line per track ID.
- Up to 2 cameras are processed at once (CPU-friendly default). For more, run additional processors on edge devices.
- Reports: CSV and browser print-to-PDF; no server-side PDF generator.
- Authentication is not implemented (single-user prototype). Do not expose it to the internet as is.
- Line/zone changes apply on the next start of processing.

## Troubleshooting
| Symptom | Fix |
|---|---|
| Header shows "Attention needed" | Hover it; usually PostgreSQL is not running or `.env` password is wrong |
| `YOLO model not found` | `python scripts\download_model.py` |
| `Video 'x' was not found` | Copy the file into `videos\` (file name only, no path) |
| 503 "database is unavailable" | Start PostgreSQL / `docker compose up -d db`; check `.env` |
| Live view blank | Press Start processing; check the red banner for the error message |
| Nothing counted | Move the counting line across where vehicles actually travel; lower `CONFIDENCE_THRESHOLD` |
| Slow / laggy | Increase `FRAME_SKIP`, reduce `PROCESS_WIDTH`, or use a GPU (`YOLO_DEVICE=0`) |
| Map is grey | Needs internet for OpenStreetMap tiles |
| `Activate.ps1` blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

## GitHub
```powershell
git init; git add .; git commit -m "TrafficFlow AI prototype"
git branch -M main
git remote add origin https://github.com/<you>/trafficflow-ai.git
git push -u origin main
```
`.env`, videos, model weights and `node_modules` are git-ignored.

## Future improvements
Calibrated speed estimation, PDF reports, authentication and roles, edge agent that posts events over HTTPS/MQTT, ONNX/TensorRT export, incident detection (stopped vehicles, wrong-way), signal-timing recommendations, Docker images for backend/frontend, ML-based forecasting once months of data exist.
