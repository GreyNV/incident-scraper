from flask import Flask, render_template, redirect, url_for, send_file
import os
import pandas as pd
import requests
from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo

app = Flask(__name__)

DATA_FILE = 'rockland_incidents.csv'
FIREWATCH_URL = 'https://firewatch.44-control.net/status.json'
EST = ZoneInfo('America/New_York')

def to_est(timestr: str) -> str:
    """Convert a time string to Eastern time and format consistently."""
    try:
        dt = parser.parse(timestr)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=EST)
        # Display times in 12 hour format with AM/PM for easier reading
        return dt.astimezone(EST).strftime('%Y-%m-%d %I:%M:%S %p %Z')
    except Exception as exc:
        print(f"Error parsing '{timestr}': {exc}")
        return timestr

def fetch_firewatch():
    """Fetch incidents from Rockland FireWatch feed."""
    try:
        resp = requests.get(FIREWATCH_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"Error fetching FireWatch feed: {exc}")
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
        if time_reported and address:
            incidents.append({
                'time_reported': to_est(time_reported),
                'address': address,
            })

    return incidents

def deduplicate_and_save(new_incidents):
    """Merge new incidents into the CSV, avoiding duplicates."""
    if os.path.exists(DATA_FILE):
        df_old = pd.read_csv(DATA_FILE)
    else:
        df_old = pd.DataFrame(columns=['time_reported', 'address'])

    df_new = pd.DataFrame(new_incidents)
    df_all = pd.concat([df_old, df_new], ignore_index=True)
    df_all.drop_duplicates(subset=['time_reported', 'address'], inplace=True)
    df_all.to_csv(DATA_FILE, index=False)

@app.route('/')
def index():
    csv_exists = os.path.exists(DATA_FILE)
    incidents = []
    if csv_exists:
        try:
            df = pd.read_csv(DATA_FILE)
            incidents = df.to_dict('records')
        except Exception as exc:
            print(f"Error reading {DATA_FILE}: {exc}")
    return render_template('index.html', csv_exists=csv_exists, incidents=incidents)

@app.route('/fetch', methods=['GET', 'POST'])
def fetch_route():
    incidents = fetch_firewatch()
    if incidents:
        deduplicate_and_save(incidents)
    return redirect(url_for('index'))

@app.route('/download')
def download_csv():
    if os.path.exists(DATA_FILE):
        return send_file(DATA_FILE, as_attachment=True)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
