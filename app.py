from flask import Flask, render_template, redirect, url_for, send_file, request, session
import os
import pandas as pd
import requests
from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo
import logging

EST = ZoneInfo("US/Eastern")

# Mapping for common Eastern time abbreviations. This avoids warnings from
# pandas/dateutil when parsing strings like "EDT" or "EST".
TZINFOS = {"EDT": EST, "EST": EST}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
PASSWORD = os.environ.get("PASSWORD", "")

DATA_FILE = 'rockland_incidents.csv'
JSON_FILE = 'incidents.json'
FIREWATCH_URL = 'https://firewatch.44-control.net/status.json'

# Configure basic logging so information is printed to the console. This helps
# debug deployments where standard output is captured by the hosting platform.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

def to_est(timestr: str) -> str:
    """Convert a time string to Eastern time and format consistently."""
    try:
        dt = parser.parse(timestr, tzinfos=TZINFOS)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=EST)
        # Display times in 12 hour format with AM/PM for easier reading.
        # Always label the timezone as EST to keep the strings consistent.
        return dt.astimezone(EST).strftime('%Y-%m-%d %I:%M:%S %p EST')
    except Exception as exc:
        logger.error("Error parsing '%s': %s", timestr, exc)
        return timestr


def parse_time_est(timestr: str) -> datetime:
    """Parse a time string that may contain EDT/EST and return an aware datetime."""
    try:
        dt = parser.parse(timestr, tzinfos=TZINFOS)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=EST)
        return dt.astimezone(EST)
    except Exception as exc:
        logger.error("Error parsing time '%s': %s", timestr, exc)
        return datetime.min.replace(tzinfo=EST)


def fetch_firewatch():
    """Fetch incidents from Rockland FireWatch feed."""
    logger.info("Fetching incidents from %s", FIREWATCH_URL)
    try:
        resp = requests.get(FIREWATCH_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Received %d bytes", len(resp.content))
    except Exception as exc:
        logger.error("Error fetching FireWatch feed: %s", exc)
        return []

    # The JSON schema contains a `Fire` key with the incident list.
    records = []
    if isinstance(data, dict):
        records = data.get('Fire') or data.get('fire') or []
    elif isinstance(data, list):
        records = data

    incidents = []
    for item in records:
        # Prefer the reported time for display
        time_reported = (
            item.get('Time Reported')
            or item.get('Time Opened')
            or item.get('Time Closed')
            or datetime.utcnow().isoformat()
        )
        # Combine address fields if provided
        addr1 = item.get('Address')
        addr2 = item.get('Address2')
        address = " ".join(part for part in [addr1, addr2] if part)
        incident_type = item.get('Incident Type', '')
        if time_reported and address:
            incidents.append({
                'time_reported': to_est(time_reported),
                'address': address,
                'incident_type': incident_type,
                'name': '',
                'phone': '',
                'email': ''

            })

    logger.info("Parsed %d incidents from feed", len(incidents))
    return incidents

def deduplicate_and_save(new_incidents):
    """Merge new incidents into the CSV, avoiding duplicates."""
    columns = ['time_reported', 'address', 'incident_type', 'name', 'phone', 'email']
    if os.path.exists(DATA_FILE):
        df_old = pd.read_csv(DATA_FILE)
        for col in columns:
            if col not in df_old.columns:
                df_old[col] = ''
    else:
        df_old = pd.DataFrame(columns=columns)

    df_new = pd.DataFrame(new_incidents)
    df_all = pd.concat([df_old, df_new], ignore_index=True)
    df_all.drop_duplicates(subset=['time_reported', 'address', 'incident_type'], inplace=True)

    # Sort by time reported so the newest incidents are first
    df_all['sort_time'] = df_all['time_reported'].apply(parse_time_est)
    df_all.sort_values('sort_time', ascending=False, inplace=True)
    df_all.drop(columns=['sort_time'], inplace=True)

    df_all.to_csv(DATA_FILE, index=False)
    logger.info("Saved %d total incidents to %s", len(df_all), DATA_FILE)

def csv_to_json():
    """Convert the CSV data file to a JSON file."""
    if not os.path.exists(DATA_FILE):
        logger.warning("CSV file %s does not exist", DATA_FILE)
        return
    try:
        df = pd.read_csv(DATA_FILE)
        df.to_json(JSON_FILE, orient="records", indent=2)
        logger.info("Wrote %d records to %s", len(df), JSON_FILE)
    except Exception as exc:
        logger.error("Error converting CSV to JSON: %s", exc)

@app.route('/')
def index():
    if PASSWORD and not session.get('logged_in'):
        return redirect(url_for('login'))
    csv_exists = os.path.exists(JSON_FILE)
    incidents = []
    logger.info("Rendering index page")
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    # Allow selecting multiple incident types via ?incident_type=A&incident_type=B
    selected_types = [t for t in request.args.getlist('incident_type') if t]
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = parser.parse(start_date_str).date()
        except Exception as exc:
            logger.error("Invalid start_date '%s': %s", start_date_str, exc)
    if end_date_str:
        try:
            end_date = parser.parse(end_date_str).date()
        except Exception as exc:
            logger.error("Invalid end_date '%s': %s", end_date_str, exc)
    incident_types = []
    if csv_exists:
        try:
            df = pd.read_json(JSON_FILE)
            for col in ['time_reported', 'address', 'incident_type', 'name', 'phone', 'email']:
                if col not in df.columns:
                    df[col] = ''

            df['sort_time'] = df['time_reported'].apply(parse_time_est)
            if start_date is not None:
                df = df[df['sort_time'].dt.date >= start_date]
            if end_date is not None:
                df = df[df['sort_time'].dt.date <= end_date]

            incident_types = sorted(df['incident_type'].dropna().unique().tolist())
            if selected_types:
                df = df[df['incident_type'].isin(selected_types)]

            df.sort_values('sort_time', ascending=False, inplace=True)
            df.drop(columns=['sort_time'], inplace=True)
            incidents = df.to_dict('records')
        except Exception as exc:
            logger.error("Error reading %s: %s", JSON_FILE, exc)
    return render_template(
        'index.html',
        csv_exists=csv_exists,
        incidents=incidents,
        start_date=start_date_str,
        end_date=end_date_str,
        incident_types=incident_types,
        selected_types=selected_types,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple password-based login."""
    if not PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        error = 'Invalid password'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """Clear the login session."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/download')
def download_csv():
    if PASSWORD and not session.get('logged_in'):
        return redirect(url_for('login'))
    logger.info("/download endpoint called")
    if os.path.exists(DATA_FILE):
        logger.info("Sending CSV file %s", DATA_FILE)
        return send_file(DATA_FILE, as_attachment=True)
    logger.info("CSV file not found")
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Render sets the PORT environment variable to tell the application which
    # port to listen on. Default to 5000 for local development.
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    logger.info("Starting server on port %d (debug=%s)", port, debug)
    # Listen on all interfaces so Render can route traffic to the container.
    app.run(host="0.0.0.0", port=port, debug=debug)
