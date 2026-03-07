import requests
import os
import time
from notion_client import Client

# F1 Drivers Championship Notion Updater für GitHub Actions – Saison 2026

# Notion API Setup
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = "3166839379ed81f8bc7dc0999f1f8e6d"  # Drivers Championship 2026

# Rennkalender 2026 (24 Rennen)
# Spain (Runde 16) = Gran Premio de España → Madrid
# Barcelona (Runde 9) = Gran Premio de Barcelona-Catalunya
RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami",
    "Canada", "Monaco", "Barcelona", "Austria", "Great Britain", "Belgium",
    "Hungary", "Netherlands", "Italy", "Spain", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# Jolpica-API-Link
BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"

# Team-Farben für Visualisierungen – Saison 2026
TEAM_COLORS = {
    "Max Verstappen": "#0600EF",        # Red Bull
    "Isack Hadjar": "#0600EF",          # Red Bull
    "George Russell": "#00D2BE",        # Mercedes
    "Andrea Kimi Antonelli": "#00D2BE", # Mercedes
    "Charles Leclerc": "#DC0000",       # Ferrari
    "Lewis Hamilton": "#DC0000",        # Ferrari
    "Lando Norris": "#FF8700",          # McLaren
    "Oscar Piastri": "#FF8700",         # McLaren
    "Fernando Alonso": "#006F62",       # Aston Martin
    "Lance Stroll": "#006F62",          # Aston Martin
    "Alexander Albon": "#005AFF",       # Williams
    "Carlos Sainz": "#005AFF",          # Williams
    "Pierre Gasly": "#0090FF",          # Alpine
    "Franco Colapinto": "#0090FF",      # Alpine
    "Liam Lawson": "#0131d1",           # Racing Bulls
    "Arvid Lindblad": "#0131d1",        # Racing Bulls
    "Esteban Ocon": "#FFFFFF",          # Haas
    "Oliver Bearman": "#FFFFFF",        # Haas
    "Nico Hülkenberg": "#00e701",       # Audi (ex Sauber)
    "Gabriel Bortoleto": "#00e701",     # Audi (ex Sauber)
    "Sergio Perez": "#B0B0B0",          # Cadillac
    "Valtteri Bottas": "#B0B0B0",       # Cadillac
}


def get_sprint_points(round_num):
    """Holt die Sprint-Punkte eines Rennwochenendes."""
    url = f"{BASE_URL}{round_num}/sprint.json"
    response = requests.get(url)
    sprint_points = {}

    if response.status_code == 200:
        data = response.json()
        races = data['MRData']['RaceTable']['Races']
        if races:
            for result in races[0]['SprintResults']:
                driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
                points = float(result['points'])
                sprint_points[driver] = int(points)
    return sprint_points


def get_weekend_points():
    """Berechnet die Punkte für jedes Wochenende separat."""
    weekend_points = {}

    for round_num in range(1, len(RACE_LOCATIONS) + 1):
        url = f"{BASE_URL}{round_num}/results.json"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            races = data['MRData']['RaceTable']['Races']
            sprint_points = get_sprint_points(round_num)

            if races:
                for result in races[0]['Results']:
                    driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
                    points = float(result['points']) + sprint_points.get(driver, 0)

                    if driver not in weekend_points:
                        weekend_points[driver] = [0] * len(RACE_LOCATIONS)

                    if weekend_points[driver][round_num - 1] == 0:
                        weekend_points[driver][round_num - 1] = int(points)

    return weekend_points


def calculate_total_points(weekend_points):
    """Berechnet die Gesamtpunkte durch Aufsummieren der Wochenendpunkte."""
    return {driver: sum(points_list) for driver, points_list in weekend_points.items()}


def get_existing_entries(db_id):
    """
    Liest alle bestehenden (nicht archivierten) Einträge aus der Datenbank.
    Gibt ein Dict {Fahrername: page_id} zurück.
    """
    import httpx
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    existing = {}
    has_more = True
    start_cursor = None

    while has_more:
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        response = httpx.post(url, headers=headers, json=body, timeout=30.0)

        if response.status_code == 200:
            data = response.json()
            for page in data.get("results", []):
                if page.get("archived"):
                    continue
                # Titel-Property heißt "Name" in der Drivers Championship 2026 DB
                title_prop = page["properties"].get("Name") or page["properties"].get("Driver")
                if title_prop and title_prop.get("title"):
                    name = title_prop["title"][0]["text"]["content"] if title_prop["title"] else None
                    if name:
                        existing[name] = page["id"]
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
        else:
            print(f"❌ Query fehlgeschlagen: {response.status_code} – {response.text}")
            break

    return existing


def upsert_driver_entries(notion, db_id, weekend_points, total_points):
    """
    Upsert-Logik:
    - Bestehende Einträge → werden per PATCH aktualisiert.
    - Neue Fahrer → werden neu per POST angelegt.
    - Kein Löschen/Archivieren – konstruktiver saisonaler Aufbau.
    """
    print("\n" + "="*60)
    print("🔄 UPSERT FAHRER-EINTRÄGE")
    print("="*60)

    existing = get_existing_entries(db_id)
    print(f"📋 Bestehende Einträge in DB: {len(existing)}")

    sorted_drivers = sorted(
        [d for d in weekend_points if d in total_points],
        key=lambda x: total_points[x],
        reverse=True
    )

    updated = 0
    created = 0

    for position, driver in enumerate(sorted_drivers, 1):
        points = weekend_points.get(driver, [0] * len(RACE_LOCATIONS))

        driver_properties = {
            "Name": {"title": [{"text": {"content": driver}}]},
            "Total": {"number": total_points[driver]}
        }

        for i, location in enumerate(RACE_LOCATIONS):
            driver_properties[location] = {"number": points[i] if points[i] > 0 else None}

        if driver in existing:
            try:
                notion.pages.update(
                    page_id=existing[driver],
                    properties=driver_properties
                )
                updated += 1
                print(f"♻️  {position:2d}. {driver:<30} {total_points[driver]:3d} Punkte  [aktualisiert]")
            except Exception as e:
                print(f"❌ Fehler beim Update von {driver}: {e}")
        else:
            try:
                notion.pages.create(
                    parent={"database_id": db_id},
                    properties=driver_properties
                )
                created += 1
                print(f"✅ {position:2d}. {driver:<30} {total_points[driver]:3d} Punkte  [neu erstellt]")
            except Exception as e:
                print(f"❌ Fehler beim Erstellen von {driver}: {e}")

    print(f"\n✅ Aktualisiert: {updated} | Neu erstellt: {created}")
    return updated, created


def update_f1_data():
    """Hauptfunktion zum Aktualisieren der F1-Daten"""
    print("\n" + "="*60)
    print("🏎️  F1 DRIVERS CHAMPIONSHIP 2026 UPDATE")
    print("="*60)
    print(f"Database ID: {DATABASE_ID}")

    try:
        notion = Client(auth=NOTION_TOKEN)
        print("✅ Notion Client initialisiert")

        print("\n📡 Hole F1-Daten (Saison 2026)...")
        weekend_points = get_weekend_points()
        total_points = calculate_total_points(weekend_points)
        print(f"✅ Daten für {len(total_points)} Fahrer geladen")

        updated, created = upsert_driver_entries(notion, DATABASE_ID, weekend_points, total_points)

        print("\n" + "="*60)
        print("✅ UPDATE ERFOLGREICH!")
        print("="*60)
        print(f"Aktualisiert: {updated} | Neu erstellt: {created}")
        print("="*60)

        return True

    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ FEHLER: {str(e)}")
        print("="*60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = update_f1_data()
    if not success:
        exit(1)
