# Architecture
- **ai/** – `detector.py` (YOLO → `Detections`), `tracker.py` (ByteTrack/BoT-SORT via Ultralytics, plus a dependency-free `CentroidTracker`), `counter.py` (line crossing, direction, once-per-line), `zones.py` (polygon enter/exit/occupancy), `video_processor.py` (thread: read → detect → track → count → annotate → callbacks). No DB/web imports.
- **backend/app/services/processing_manager.py** – owns processors; callbacks enqueue events; one writer thread persists to PostgreSQL then broadcasts over WebSocket (`asyncio.run_coroutine_threadsafe`). Inference never blocks the event loop.
- **Roll-up**: each event insert upserts `traffic_summaries` (hourly bucket in `APP_TIMEZONE`) in the same transaction. Analytics read the roll-up; history/export read `vehicle_events`.
- **Counting geometry**: normalised line coordinates; side = cross product; a track counts when its motion segment intersects the finite line segment; `(line, track)` pairs are remembered so a vehicle counts once per line.
- **Security**: file sources are bare file names resolved inside `VIDEO_DIR` only; inputs validated by Pydantic; CORS restricted to configured origins; secrets via `.env`.
- **Replaceable parts**: detector and tracker are injected into `VideoProcessor` (`detector=`, `tracker_factory=`), which is also how the tests substitute a synthetic detector.
