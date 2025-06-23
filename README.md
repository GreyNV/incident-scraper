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

The feed URL used in `app.py` is a placeholder. Update `FIREWATCH_URL`
with the correct Rockland FireWatch link before running in production.
