from app import fetch_firewatch, deduplicate_and_save, csv_to_json


def main():
    incidents = fetch_firewatch()
    if incidents:
        deduplicate_and_save(incidents)
        csv_to_json()


if __name__ == "__main__":
    main()
