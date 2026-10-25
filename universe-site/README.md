# Universe Master Data

Universe is the portal-connected reference-data CMS for vehicles and VINs. It
uses the shared Portal session and stores domain records separately from user
identity and Scraper run data. For the full platform setup, see the
[platform README](../README.md).

## Data model

- `vehicle`: unique Year/Make/Model, normalized for case and whitespace.
- `vin`: references a vehicle through `id_vehicle`; VINs are unique per vehicle.
- PostgreSQL target: database `ipart`, schema `universe`.
- Vehicle/VIN rows include IDs, notes, creation/update timestamps, and shared
  user IDs for auditing.
- Deleting a vehicle deletes its linked VIN rows.

## Master Data

The Vehicle and VIN lists use 10 rows per page. Both support text search and
year/make filters; VIN also has a model filter.

Vehicle import/export uses exactly these Excel columns:

| Year | Make | Model |
|---:|---|---|

VIN import/export uses:

| Year | Make | Model | VIN |
|---:|---|---|---|

VIN imports resolve or create the matching vehicle first. Imports update
existing matching records, skip unchanged duplicates, and never create a second
vehicle with the same Year/Make/Model or a second VIN for the same vehicle.
Workbook extensions supported are `.xlsx` and `.xlsm`.

To seed both tables from the supplied example workbook, place it at
`universe-site/data/Example Data.xlsx`, then run the importer from the portal
root after starting PostgreSQL configuration is available:

```powershell
cd C:\ELFANI\portal-apps\universe-site\backend
.\.venv\Scripts\python.exe -m app.seed_example_data
```

The importer requires `Year`, `Make`, `Model`, and `VIN` columns. It creates
missing vehicles/VINs and skips existing normalized duplicate keys, so it can
be safely run again after new example rows are added.

## Run locally

Start the Universe API and UI in separate PowerShell terminals from
`C:\ELFANI\portal-apps`:

```powershell
# Universe API (:8002)
.\run_universe_api.ps1

# Universe UI (:5175, mounted through the portal at /universe/)
.\run_universe_ui.ps1
```

Open Universe from the Portal Apps launcher at http://localhost:5174. The
portal proxies `/universe/` and `/api/universe`, keeping the shared HTTP-only
session cookie on the portal origin.

The API launcher creates `universe-site/backend/.venv` and installs the
Universe backend requirements the first time it runs. The UI launcher installs
frontend packages when `node_modules` is absent.

## API reference

All routes are under `/api/universe` and require a valid Portal session:

| Route | Purpose |
|---|---|
| `GET /vehicles` | Search/filter/paginate vehicles (`page_size` defaults to 10) |
| `POST /vehicles` | Create a vehicle |
| `PUT /vehicles/{id}` | Update a vehicle |
| `DELETE /vehicles/{id}` | Delete a vehicle and its VINs |
| `GET /vehicles/export` | Export filtered vehicles as Excel |
| `POST /vehicles/import` | Import or update vehicles from Excel |
| `GET /vins` | Search/filter/paginate VINs with vehicle details |
| `POST /vins` | Create a VIN for a vehicle |
| `PUT /vins/{id}` | Update a VIN |
| `DELETE /vins/{id}` | Delete a VIN |
| `GET /vins/export` | Export filtered VINs as Excel |
| `POST /vins/import` | Import vehicles and VINs from Excel |

## Development

Build the frontend from `universe-site/frontend` with `npm run build`. Restart
the API after changes under `backend/app/`; restart Vite after changing its
config or package file.