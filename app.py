from flask import Flask, render_template, redirect, url_for, send_file
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)

DATA_FILE = 'rockland_incidents.csv'
FIREWATCH_URL = 'https://firewatch.44-control.net/history.html'  # placeholder URL

def fetch_firewatch():
    """Fetch incidents from Rockland FireWatch feed."""
    try:
        resp = requests.get(FIREWATCH_URL, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        print(f"Error fetching FireWatch feed: {exc}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table')
    if not table:
        return []

    incidents = []
    for row in table.find_all('tr')[1:]:  # skip header
        cols = [c.get_text(strip=True) for c in row.find_all('td')]
        if len(cols) < 4:
            continue
        timestamp, incident_type, location, units = cols[:4]
        incidents.append({
            'timestamp': timestamp or datetime.utcnow().isoformat(),
            'incident_type': incident_type,
            'location': location,
            'units': units,
        })
    return incidents

def deduplicate_and_save(new_incidents):
    if os.path.exists(DATA_FILE):
        df_old = pd.read_csv(DATA_FILE)
    else:
        df_old = pd.DataFrame(columns=['timestamp', 'incident_type', 'location', 'units'])

    df_new = pd.DataFrame(new_incidents)
    df_all = pd.concat([df_old, df_new], ignore_index=True)
    df_all.drop_duplicates(subset=['timestamp', 'incident_type', 'location'], inplace=True)
    df_all.to_csv(DATA_FILE, index=False)

@app.route('/')
def index():
    csv_exists = os.path.exists(DATA_FILE)
    return render_template('index.html', csv_exists=csv_exists)

@app.route('/fetch')
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
