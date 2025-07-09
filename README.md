# Incident Scraper

Simple Flask application to fetch and store Rockland County FireWatch incidents.

## Setup

```bash
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

By default the app listens on port 5000. Deployment platforms like Render set a
`PORT` environment variable which the application will honor, so no code changes
are required to run in those environments.

Then open `http://localhost:5000` in your browser when running locally.

The index page now uses Bootstrap styling and paginates results 10 per page so large incident lists remain easy to navigate. New incidents appear first after each fetch.

`app.py` now fetches incidents from the JSON feed used by Rockland
FireWatch. If the endpoint changes, update the `FIREWATCH_URL` constant
in the script accordingly.

The CSV tracks these fields:

- `time_reported`
- `address`
- `incident_type`
- `name`
- `phone`
- `email`

Times shown in the web interface are converted to the US/Eastern timezone
and displayed in a 12‑hour format with AM/PM for consistency with
Rockland County's local time.

