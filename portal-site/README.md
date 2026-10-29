# Portal UI and Identity API

This site contains the Portal Apps frontend and the identity API used by
connected applications. The portal provides sign-in, the application launcher,
account administration, profile settings, and the Portal-only activity history.
The application launcher opens Scraper CMS at `/scrapper/` and Universe Master
Data at `/universe/` for superadmins.

For the full multi-service architecture, shared credential configuration, and
local startup instructions, see the [platform README](../README.md).

## Portal services

| Component | Port | Responsibility |
|---|---:|---|
| Portal frontend | 5174 | Sign-in, app launcher, accounts, profile, sign-out |
| Portal identity API | 8001 | Login/logout, user accounts, profiles, Portal activity |

The frontend proxies `/api/auth`, `/api/profile`, `/api/users`, and
`/api/activity` to the identity API. Portal login, logout, profile, and account
events are stored in PostgreSQL schema `global`; Scraper and Universe events
are stored in their own application schemas. Scraper routes are proxied to
Scraper CMS by the portal Vite configuration; the portal UI and identity API do
not run crawlers or manage run artifacts.

The portal also proxies `/universe/` to the Universe UI and `/api/universe` to
the Universe API. Universe owns its vehicle and VIN domain records; the portal
continues to own identity and sessions.

## Run the portal services

From `C:\ELFANI\portal-apps`, launch each service in its own PowerShell terminal:

```powershell
# Identity API
.\run_portal_api.ps1

# Portal frontend
.\run_portal.ps1
```

Open http://localhost:5174. On first run, `run_portal_api.ps1` creates
`portal-site/backend/.venv` and installs `backend/requirements.txt`.
`run_portal.ps1` installs frontend dependencies if `node_modules` is absent.

## Identity API configuration

The identity API reads the shared database URL, schema, signing key, and cookie
setting from `scrapper-site/backend/.env`. Portal-issued sessions are HTTP-only
cookies and are validated by connected application APIs using the same signing
key. Set `cookie_secure=true` when serving the portal over HTTPS; local HTTP
development should use `false`.

The first API startup creates `superadmin` / `12345678` only if the shared user
table is empty. Change the initial password in the Accounts page before real
use.

## Add an application

Add an application tile in `src/App.tsx` and configure any development proxy in
`vite.config.ts`. Mount the application on the portal origin where possible so
the shared session cookie is available. Application-specific crawler settings
and run handling belong in that application's own site.

## Development

Build and type-check the portal frontend:

```powershell
cd C:\ELFANI\portal-apps\portal-site
npm run build
```

Vite hot reloads frontend source edits. Restart the frontend after changing
`vite.config.ts` or `package.json`. Restart the identity API after changing
files under `backend/app/`.