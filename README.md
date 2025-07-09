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

Then open `http://localhost:5000` in your browser.

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

