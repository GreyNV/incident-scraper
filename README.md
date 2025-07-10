# Incident Scraper

Simple Flask application to display incidents stored in `incidents.json`. A
separate script handles fetching data from the Rockland County FireWatch feed
and updating the CSV/JSON files.

## Setup

```bash
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

### Updating data

Run `fetch_incidents.py` to pull the latest incidents and update the CSV/JSON
files:

```bash
python fetch_incidents.py
```

You can also convert an existing CSV to JSON directly:

```bash
python csv_to_json.py
```

By default the app listens on port 5000. Deployment platforms like Render set a
`PORT` environment variable which the application will honor, so no code changes
are required to run in those environments.

Then open `http://localhost:5000` in your browser when running locally.

The index page uses Bootstrap for styling and displays all incidents in a single
table. New incidents appear first once the JSON file has been updated by the
`fetch_incidents.py` script.

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

