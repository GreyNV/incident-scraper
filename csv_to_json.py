import os
import pandas as pd

CSV_FILE = "rockland_incidents.csv"
JSON_FILE = "incidents.json"


def main():
    if not os.path.exists(CSV_FILE):
        print(f"{CSV_FILE} not found")
        return
    df = pd.read_csv(CSV_FILE)
    df.to_json(JSON_FILE, orient="records", indent=2)
    print(f"Wrote {len(df)} records to {JSON_FILE}")


if __name__ == "__main__":
    main()
