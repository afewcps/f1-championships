import requests
import datetime
import os

# F1 Constructors Championship Notion Updater für GitHub Actions – Saison 2026

# Notion API Konfiguration
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("❌ Fehler: NOTION_TOKEN environment variable ist nicht gesetzt!")
    exit(1)

# Paddock (1) – Parent Page für neue Datenbanken (falls create_database nötig)
NOTION_PARENT_PAGE_ID = "3166839379ed809aa3caf99622a2cb68"

# Direkte DB-ID für Constructors Championship 2026
CONSTRUCTORS_DB_ID = "3166839379ed81a18ff9c93850213783"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Rennkalender 2026 (24 Rennen)
# Spain (Runde 16) = Gran Premio de España → Madrid
# Barcelona (Runde 9) = Gran Premio de Barcelona-Catalunya
RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami",
    "Canada", "Monaco", "Barcelona", "Austria", "Great Britain", "Belgium",
    "Hungary", "Netherlands", "Italy", "Spain", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# Konstrukteure 2026
# Änderungen zu 2025: Sauber → Audi, Cadillac neu als 11. Team
# Hinweis: API-Namen müssen mit den von Jolpica zurückgegebenen Namen übereinstimmen.
# Nach dem ersten Rennen ggf. "Audi" / "Cadillac" anpassen, falls die API andere Namen liefert.
TEAMS = [
    "McLaren", "Red Bull", "Mercedes", "Williams", "Aston Martin",
    "Audi", "Ferrari", "Alpine F1 Team", "RB F1 Team", "Haas F1 Team", "Cadillac"
]

BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"


def check_if_race_happened(round_num):
    """Überprüft, ob ein Rennen bereits stattgefunden hat."""
    url = f"{BASE_URL}{round_num}/results.json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        races = data['MRData']['RaceTable'].get('Races', [])
        if races:
            return True

    return False


def get_sprint_points(round_num):
    url = f"{BASE_URL}{round_num}/sprint.json"
    response = requests.get(url)
    points = {}
    if response.status_code == 200:
        data = response.json()
        races = data['MRData']['RaceTable']['Races']
        if races:
            for result in races[0]['SprintResults']:
                team = result['Constructor']['name']
                team_points = float(result['points'])
                points[team] = points.get(team, 0) + int(team_points)
    return points


def get_weekend_points():
    weekend_points = {team: [0] * len(RACE_LOCATIONS) for team in TEAMS}
    race_happened = [False] * len(RACE_LOCATIONS)

    for round_num in range(1, len(RACE_LOCATIONS) + 1):
        if check_if_race_happened(round_num):
            race_happened[round_num - 1] = True
            url = f"{BASE_URL}{round_num}/results.json"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                races = data['MRData']['RaceTable']['Races']
                current_points = {team: 0 for team in TEAMS}
                sprint_points = get_sprint_points(round_num)

                if races:
                    for result in races[0]['Results']:
                        team = result['Constructor']['name']
                        if team in current_points:
                            current_points[team] += int(float(result['points']))

                    for team in sprint_points:
                        if team in current_points:
                            current_points[team] += sprint_points[team]

                    for team in weekend_points:
                        weekend_points[team][round_num - 1] = current_points.get(team, 0)

    return weekend_points, race_happened


def get_cumulative_standings(weekend_points, race_happened):
    total_points = {team: 0 for team in weekend_points}

    for race_index in range(len(RACE_LOCATIONS)):
        if race_happened[race_index]:
            for team in weekend_points:
                total_points[team] += weekend_points[team][race_index]

    return total_points


def get_existing_entries(database_id):
    """
    Liest alle bestehenden (nicht archivierten) Einträge aus der Datenbank.
    Gibt ein Dict {Teamname: page_id} zurück.
    """
    existing = {}
    has_more = True
    start_cursor = None

    while has_more:
        query_url = f"https://api.notion.com/v1/databases/{database_id}/query"
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        response = requests.post(query_url, headers=headers, json=body)

        if response.status_code == 200:
            data = response.json()
            for page in data.get("results", []):
                if page.get("archived"):
                    continue
                title_prop = page["properties"].get("Constructor")
                if title_prop and title_prop.get("title"):
                    name = title_prop["title"][0]["text"]["content"] if title_prop["title"] else None
                    if name:
                        existing[name] = page["id"]
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
        else:
            print(f"❌ Fehler beim Abfragen der Datenbank: {response.status_code}")
            break

    return existing


def upsert_entries_championship(database_id, weekend_points, total_points, race_happened):
    """
    Upsert-Logik:
    - Bestehende Einträge → werden per PATCH aktualisiert.
    - Neue Teams → werden neu per POST angelegt.
    - Kein Löschen/Archivieren – konstruktiver saisonaler Aufbau.
    """
    existing = get_existing_entries(database_id)
    print(f"📋 Bestehende Einträge in DB: {len(existing)}")

    updated = 0
    created = 0

    for team in TEAMS:
        properties = {
            "Constructor": {"title": [{"text": {"content": team}}]},
            "Total": {"number": total_points[team]}
        }

        for i, race in enumerate(RACE_LOCATIONS):
            if race_happened[i]:
                properties[race] = {"number": weekend_points[team][i]}
            # Rennen noch nicht gefahren → Feld unverändert lassen (kein Key → bleibt wie es ist)

        if team in existing:
            # Bestehenden Eintrag aktualisieren
            update_url = f"https://api.notion.com/v1/pages/{existing[team]}"
            payload = {"properties": properties}
            response = requests.patch(update_url, headers=headers, json=payload)

            if response.status_code == 200:
                updated += 1
                print(f"♻️  {team:<25} {total_points[team]:3d} Punkte  [aktualisiert]")
            else:
                print(f"❌ Fehler beim Update von {team}: {response.status_code}")
                print(response.text)
        else:
            # Neuen Eintrag anlegen
            payload = {
                "parent": {"database_id": database_id},
                "properties": properties
            }
            response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)

            if response.status_code == 200:
                created += 1
                print(f"✅ {team:<25} {total_points[team]:3d} Punkte  [neu erstellt]")
            else:
                print(f"❌ Fehler beim Erstellen von {team}: {response.status_code}")
                print(response.text)

    print(f"\n✅ Aktualisiert: {updated} | Neu erstellt: {created}")
    return updated, created


def find_or_create_database():
    """
    Nutzt primär die hart kodierte DB-ID. Nur als Fallback: Suche/Erstellung.
    """
    # Prüfe ob die direkte DB-ID erreichbar ist
    url = f"https://api.notion.com/v1/databases/{CONSTRUCTORS_DB_ID}/query"
    response = requests.post(url, headers=headers, json={})
    if response.status_code == 200:
        print(f"🔎 Constructors Championship 2026 DB gefunden (direkte ID)")
        return CONSTRUCTORS_DB_ID

    # Fallback: Suche
    print("⚠️ Direkte DB-ID nicht erreichbar, suche per API...")
    search_url = "https://api.notion.com/v1/search"
    payload = {"query": "Constructors Championship 2026", "filter": {"value": "database", "property": "object"}}
    response = requests.post(search_url, headers=headers, json=payload)

    if response.status_code == 200:
        for db in response.json().get("results", []):
            if db["object"] == "database":
                title_blocks = db.get("title", [])
                full_title = "".join(b.get("text", {}).get("content", "") for b in title_blocks)
                if "Constructors Championship 2026" in full_title:
                    print(f"🔎 Gefunden per Suche: {full_title}")
                    return db["id"]

    print("⚠️ Datenbank nicht gefunden – wird neu erstellt")
    return create_database("Constructors Championship 2026")


def create_database(title):
    url = "https://api.notion.com/v1/databases"

    properties = {"Constructor": {"title": {}}, "Total": {"number": {}}}
    for race in RACE_LOCATIONS:
        properties[race] = {"number": {}}

    payload = {
        "parent": {"type": "page_id", "page_id": NOTION_PARENT_PAGE_ID},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": properties,
        "is_inline": False
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        db_id = response.json()["id"]
        print(f"✅ Neue Datenbank erstellt: {title}")
        return db_id
    else:
        print(f"❌ Fehler beim Erstellen der Datenbank '{title}': {response.status_code}")
        print(response.text)
        return None


def update_constructors_championship():
    """Hauptfunktion zum Aktualisieren der Konstrukteurswertung"""
    print("🔄 Lade aktuelle Punkte (Saison 2026)...")

    try:
        weekend_points, race_happened = get_weekend_points()
        total_points = get_cumulative_standings(weekend_points, race_happened)

        db_championship = find_or_create_database()

        if db_championship:
            print("🔄 Starte Upsert (Championship)...")
            upsert_entries_championship(db_championship, weekend_points, total_points, race_happened)

        print("\n✅ Fertig! Konstrukteurswertung wurde in Notion aktualisiert.")

        print("\nAktuelle Konstrukteurswertung 2026:")
        print("-" * 60)

        sorted_teams = sorted(TEAMS, key=lambda x: total_points[x], reverse=True)
        for i, team in enumerate(sorted_teams, 1):
            print(f"{i:2d}. {team:<25} {total_points[team]:3d} Punkte")

        return True

    except Exception as e:
        print(f"❌ Fehler beim Aktualisieren der Konstrukteurswertung: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Hauptfunktion für GitHub Actions"""
    print("🚀 Starte F1 Konstrukteurswertung 2026 Update...")

    success = update_constructors_championship()

    if success:
        print(f"✅ Prozess erfolgreich abgeschlossen um {datetime.datetime.now()}")
        return True
    else:
        print(f"❌ Prozess fehlgeschlagen um {datetime.datetime.now()}")
        return False


if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
