# Universe Master Data

Universe is the portal-connected reference-data CMS for vehicles and VINs. It
uses the shared Portal session and stores domain records separately from user
identity and Scraper run data. For the full platform setup, see the
[platform README](../README.md).

## Data model

- `vehicle`: unique Year/Make/Model, normalized for case and whitespace.
- `vin`: references a vehicle through `id_vehicle`; VINs are unique per vehicle.
- `oem`: references a VIN through `id_vin`; OEM numbers are unique per VIN.
- `universe.ccc_market_data`: CCC crawl summaries and decoded market results,
  unique by OEM, VIN, and crawl date.
- PostgreSQL target: database `ipart`, schema `universe`.
- Vehicle/VIN rows include IDs, notes, creation/update timestamps, and shared
  user IDs for auditing.
- Deleting a vehicle deletes its linked VIN rows.

## Master Data

The Vehicle, VIN, and OEM lists use 10 rows per page. They support text search
across their displayed fields and related vehicle data.

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

OEM import/export uses these columns:

| OEM | VIN | Year | Make | Model | Description | Notes |
|---|---|---:|---|---|---|---|

OEM and VIN are required for import. Year, Make, and Model are optional as a
group: when present, import resolves or creates the vehicle and its VIN; when
omitted, the VIN must already identify exactly one vehicle. An OEM/VIN match
updates the existing record. OEM export can use the current search or an
uploaded list workbook containing an `OEM` column and optional `VIN` column;
OEM-only rows export all related VIN records, while OEM plus VIN narrows the
match to that specific vehicle.

## Market Data: CCC

The Market menu contains the CCC list. It can filter by OEM, VIN, description,
and vendor, and sorts records by newest crawl date first. The list groups offer
rows by OEM, VIN, and crawl date and displays only those three fields; the
decoded offers remain stored as separate database rows for each crawl.

The CCC **Lowest Price** view compares numeric `ext-price` values within each
crawl and description, then groups winning OEM part numbers by vendor and
description. It reports distinct OEM counts and crawl-win counts separately,
as well as OEMs/crawls where a vendor did not have the lowest offer. Equal
lowest-price ties count for each winning vendor. The date range defaults to
today and the preceding calendar month; both endpoints are included. Click a
description count to inspect its related OEM/VIN/crawl records and export them
to Excel.

CCC Excel imports require `VIN`, `OEM`, `date_time`, and `market_data` columns.
`date_time` is stored as `crawl_date`; `market_data` contains a JSON array of
market offers. Each JSON object is decoded and stored as its own row in
`universe.ccc_market_data`, with `market_index` preserving its array position.
Offer descriptions and vendors are exposed for filtering. Reimporting the same
OEM, VIN, and crawl date replaces that crawl's complete set of offer rows.

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
Universe backend requirements the first time it runs. Universe requires the
PostgreSQL `ipart` database URL from `scrapper-site/backend/.env` and creates
tables in schema `universe`. The UI launcher installs frontend packages when
`node_modules` is absent.

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
| `GET /oems` | Search and page OEMs with related VIN and vehicle fields |
| `GET /oems/export` | Export all OEMs or those matching a search |
| `POST /oems/export-by-list` | Export OEMs matching an uploaded OEM/VIN workbook |
| `POST /oems/import` | Import OEMs and resolve related vehicles and VINs |
| `GET /market/ccc` | Filter and page CCC market data, newest crawl first |
| `GET /market/ccc/filters` | List distinct CCC OEM, VIN, description, and vendor filters |
| `POST /market/ccc/import` | Import or replace CCC market data from Excel |
| `GET /activity` | Search and paginate Universe-only activity |

Universe activity is stored in PostgreSQL schema `universe` and records vehicle,
VIN, CCC import, and export actions. Portal account activity remains in `global`;
Scraper run activity is stored in `scrapping`.

## Development

Build the frontend from `universe-site/frontend` with `npm run build`. Restart
the API after changes under `backend/app/`; restart Vite after changing its
config or package file.