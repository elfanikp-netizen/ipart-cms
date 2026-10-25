# Scraper CMS

Scraper CMS launches the existing crawler scripts as subprocesses; the crawler
projects themselves are not modified. Upload an Excel file, queue a run, follow
its progress and log, and download the result when available.

For platform-wide setup, the Portal Apps architecture, shared authentication,
database schema, and full local startup instructions, see the
[platform README](../README.md).

The Scraper UI returns to the portal using `VITE_PORTAL_BASE_URL`. By default
it uses `/`, so the Portal link and login redirect stay on the current host
(for example, `http://localhost:5174/` when mounted at `/scrapper/`). To use a
different portal origin, set `VITE_PORTAL_BASE_URL` in
`frontend/.env.local`, for example `https://portal.example.com/`, and restart
Vite.

## Crawler catalog

| Group | Crawlers | Project folder |
|---|---|---|
| CCC | Workfile (VIN; configurable description match, defaults to `A/M: CAPA`) | `C:\ELFANI\scrapper-ccc` |
| Keystone | Partslink, Find-Model | `C:\ELFANI\scrapper-keystone` |
| CARiD | Parts, Interchange | `C:\ELFANI\scrapper` |
| Brands (OEM Parts) | Acura, Audi, BMW, Chrysler, Ford, GMC, Honda, Hyundai, Infiniti, Kia, Lexus, Mazda, Nissan, Porsche, Subaru, Toyota, Volvo, VW | `C:\ELFANI\scrapper-brand\scrapper-*` |

Crawler definitions live in [backend/app/crawlers.py](backend/app/crawlers.py).
Adding a crawler script means registering it there.

## Start Scraper services

The Portal API must also be running to issue sessions; see the platform guide.
Run these Scraper services in separate PowerShell terminals:

```powershell
# Scraper API (:8000)
cd C:\ELFANI\portal-apps\scrapper-site\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Scraper UI (:5173, proxied under /scrapper/ by Portal Apps)
cd C:\ELFANI\portal-apps\scrapper-site
.\run_ui.ps1
```

Open Scraper CMS from the Portal Apps launcher at http://localhost:5174. The
Scraper API validates the shared portal session but does not manage credentials,
accounts, or profile settings.

## Run behavior

Runs execute one at a time so persistent Chrome profiles and CDP ports do not
collide. Each run has a directory under `data/runs/<id>/` containing its input,
live `run.log`, and output workbook when produced. The API resolves older
absolute artifact paths against the current configured data directory so runs
created before moving the workspace can still show logs and downloads.

CARiD and brand crawlers may open a visible Chrome window. If a Cloudflare or
human-verification check appears, the run is marked as waiting in the UI. Open
the Chrome window on the Scraper host, complete the check, and the run resumes.

Stopping a run kills the crawler process tree, including Chrome. Restarting
the Scraper API marks active or queued runs as failed; avoid restarting it while
a crawl is running.

## Development and troubleshooting

- Crawler script changes apply to the next run; an already-running subprocess
  continues with the code it started with.
- Vite hot reloads Scraper frontend source. Restart `run_ui.ps1` after changing
  `frontend/vite.config.ts` or `frontend/package.json`.
- The Scraper API has no auto-reload. Restart it after changing files in
  `backend/app/`. For active backend development, add `--reload` to its Uvicorn
  command, but do not use reload during a production crawl.
- If port 5173 is occupied, find the PID with `netstat -ano | findstr :5173`,
  stop that process, and restart `run_ui.ps1`.
- If port 8000 is occupied, find the PID with `netstat -ano | findstr :8000`,
  stop that process, and restart Uvicorn.
- If PowerShell blocks a launcher, use
  `powershell -ExecutionPolicy Bypass -File .\run_ui.ps1` or allow local scripts
  with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Remote users can queue and watch runs through the portal, but crawler browser
windows and any human-verification prompt are on the machine running Scraper.

## Scraper API

The Scraper API accepts the portal's `portal_session` cookie or a bearer JWT
issued by the Portal API. It exposes crawler and run operations only:

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Scraper API health |
| `GET /api/crawlers` | List registered crawlers, sites, and capabilities |
| `POST /api/runs` | Queue a run with multipart crawler options and an Excel file |
| `GET /api/runs` / `GET /api/runs/{id}` | List and inspect runs |
| `GET /api/runs/{id}/log?tail=300` | Read a run log tail |
| `POST /api/runs/{id}/stop` | Stop a queued or running process tree |
| `GET /api/runs/{id}/output` | Download a run output workbook |
| `GET /api/queue` | Read current queue status |
| `GET /api/network-status` | Estimate host VPN status |
