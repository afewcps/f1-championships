import requests
import datetime
import os

# F1 Constructors Championship Notion Updater für GitHub Actions – Saison 2026

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("❌ Fehler: NOTION_TOKEN environment variable ist nicht gesetzt!")
    exit(1)

NOTION_PARENT_PAGE_ID = "3166839379ed809aa3caf99622a2cb68"
CONSTRUCTORS_DB_ID    = "3166839379ed81a18ff9c93850213783"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

RACE_LOCATIONS = [
    "Australia", "China", "Japan",
    # "Bahrain", "Saudi Arabia",  # 2026: abgesagt – regionaler Konflikt; für 2027 wieder einkommentieren
    "Miami",
    "Canada", "Monaco", "Barcelona", "Austria", "Great Britain", "Belgium",
    "Hungary", "Netherlands", "Italy", "Spain", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# Mapping: API-Name → Notion-Anzeigename
# Jolpica liefert z.B. "Alpine F1 Team", in Notion heißt der Eintrag aber "Alpine".
API_TO_NOTION_NAME = {
    "Alpine F1 Team": "Alpine",
    "RB F1 Team":     "Racing Bulls",
    "Haas F1 Team":   "Haas",
}

# Notion-Namen (so wie sie in der DB stehen / stehen sollen)
TEAMS_NOTION = [
    "McLaren", "Red Bull", "Mercedes", "Williams", "Aston Martin",
    "Audi", "Ferrari", "Alpine", "Racing Bulls", "Haas", "Cadillac"
]

# Reverse-Mapping für API-Abfragen: Notion-Name → API-Name
NOTION_TO_API_NAME = {v: k for k, v in API_TO_NOTION_NAME.items()}

BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"


def check_if_race_happened(round_num):
    url = f"{BASE_URL}{round_num}/results.json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return bool(r.json()['MRData']['RaceTable'].get('Races'))
    except Exception:
        pass
    return False


def get_sprint_points(round_num):
    url = f"{BASE_URL}{round_num}/sprint.json"
    points = {}
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            races = r.json()['MRData']['RaceTable']['Races']
            if races:
                for res in races[0]['SprintResults']:
                    api_team = res['Constructor']['name']
                    # Auf Notion-Namen normalisieren
                    notion_team = API_TO_NOTION_NAME.get(api_team, api_team)
                    points[notion_team] = points.get(notion_team, 0) + int(float(res['points']))
    except Exception:
        pass
    return points


def get_weekend_points():
    weekend_points = {team: [0] * len(RACE_LOCATIONS) for team in TEAMS_NOTION}
    race_happened  = [False] * len(RACE_LOCATIONS)

    for round_num in range(1, len(RACE_LOCATIONS) + 1):
        race_has_results = check_if_race_happened(round_num)
        sprint_points    = get_sprint_points(round_num)

        # Runde komplett überspringen wenn weder Rennen noch Sprint stattgefunden hat
        if not race_has_results and not sprint_points:
            continue

        race_happened[round_num - 1] = True
        current_points = {team: 0 for team in TEAMS_NOTION}

        if race_has_results:
            url = f"{BASE_URL}{round_num}/results.json"
            try:
                r = requests.get(url, timeout=10)
                if r.status_code != 200:
                    pass  # Sprint-Punkte werden trotzdem unten eingetragen
                else:
                    races = r.json()['MRData']['RaceTable']['Races']
                    if races:
                        for res in races[0]['Results']:
                            api_team    = res['Constructor']['name']
                            notion_team = API_TO_NOTION_NAME.get(api_team, api_team)
                            if notion_team in current_points:
                                current_points[notion_team] += int(float(res['points']))
            except Exception:
                pass  # Sprint-Punkte werden trotzdem unten eingetragen

        for notion_team, pts in sprint_points.items():
            if notion_team in current_points:
                current_points[notion_team] += pts

        for team in weekend_points:
            weekend_points[team][round_num - 1] = current_points.get(team, 0)

    return weekend_points, race_happened


def get_total_points(weekend_points, race_happened):
    total = {team: 0 for team in weekend_points}
    for i in range(len(RACE_LOCATIONS)):
        if race_happened[i]:
            for team in weekend_points:
                total[team] += weekend_points[team][i]
    return total


def get_existing_entries(database_id):
    existing = {}
    has_more, start_cursor = True, None
    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers=headers, json=body
        )
        if r.status_code != 200:
            print(f"❌ Fehler beim Abfragen der DB: {r.status_code}")
            break
        data = r.json()
        for page in data.get("results", []):
            if page.get("archived"):
                continue
            title_prop = page["properties"].get("Constructor")
            if title_prop and title_prop.get("title"):
                name = title_prop["title"][0]["text"]["content"]
                if name:
                    existing[name] = page["id"]
        has_more     = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return existing


def upsert_entries(database_id, weekend_points, total_points, race_happened):
    existing = get_existing_entries(database_id)
    print(f"📋 Bestehende Einträge in DB: {len(existing)}")

    updated, created = 0, 0

    for team in TEAMS_NOTION:
        properties = {
            "Constructor": {"title": [{"text": {"content": team}}]},
            "Total":       {"number": total_points[team]}
        }
        for i, race in enumerate(RACE_LOCATIONS):
            if race_happened[i]:
                properties[race] = {"number": weekend_points[team][i]}

        if team in existing:
            r = requests.patch(
                f"https://api.notion.com/v1/pages/{existing[team]}",
                headers=headers, json={"properties": properties}
            )
            if r.status_code == 200:
                updated += 1
                print(f"♻️  {team:<25} {total_points[team]:3d} Pts  [aktualisiert]")
            else:
                print(f"❌ Update-Fehler {team}: {r.status_code} – {r.text}")
        else:
            r = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json={"parent": {"database_id": database_id}, "properties": properties}
            )
            if r.status_code == 200:
                created += 1
                print(f"✅ {team:<25} {total_points[team]:3d} Pts  [neu erstellt]")
            else:
                print(f"❌ Erstell-Fehler {team}: {r.status_code} – {r.text}")

    print(f"\n✅ Aktualisiert: {updated} | Neu erstellt: {created}")
    return updated, created


def find_or_create_database():
    r = requests.post(
        f"https://api.notion.com/v1/databases/{CONSTRUCTORS_DB_ID}/query",
        headers=headers, json={}
    )
    if r.status_code == 200:
        print("🔎 Constructors Championship 2026 DB gefunden (direkte ID)")
        return CONSTRUCTORS_DB_ID

    print("⚠️ Direkte DB-ID nicht erreichbar, suche per API...")
    r = requests.post(
        "https://api.notion.com/v1/search", headers=headers,
        json={"query": "Constructors Championship 2026",
              "filter": {"value": "database", "property": "object"}}
    )
    if r.status_code == 200:
        for db in r.json().get("results", []):
            if db["object"] == "database":
                full_title = "".join(
                    b.get("text", {}).get("content", "") for b in db.get("title", [])
                )
                if "Constructors Championship 2026" in full_title:
                    print(f"🔎 Gefunden per Suche: {full_title}")
                    return db["id"]

    print("⚠️ DB nicht gefunden – wird neu erstellt")
    return create_database("Constructors Championship 2026")


def create_database(title):
    properties = {"Constructor": {"title": {}}, "Total": {"number": {}}}
    for race in RACE_LOCATIONS:
        properties[race] = {"number": {}}
    r = requests.post(
        "https://api.notion.com/v1/databases", headers=headers,
        json={
            "parent": {"type": "page_id", "page_id": NOTION_PARENT_PAGE_ID},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties, "is_inline": False
        }
    )
    if r.status_code == 200:
        db_id = r.json()["id"]
        print(f"✅ Neue DB erstellt: {title}")
        return db_id
    print(f"❌ DB-Erstellung fehlgeschlagen: {r.status_code} – {r.text}")
    return None


def main():
    print("🚀 Starte F1 Konstrukteurswertung 2026 Update...")
    try:
        weekend_points, race_happened = get_weekend_points()
        total_points = get_total_points(weekend_points, race_happened)

        db_id = find_or_create_database()
        if not db_id:
            return False

        print("🔄 Starte Upsert...")
        upsert_entries(db_id, weekend_points, total_points, race_happened)

        print("\nAktuelle Konstrukteurswertung 2026:")
        print("-" * 60)
        for i, team in enumerate(
            sorted(TEAMS_NOTION, key=lambda t: total_points[t], reverse=True), 1
        ):
            print(f"{i:2d}. {team:<25} {total_points[team]:3d} Punkte")

        print(f"\n✅ Fertig um {datetime.datetime.now()}")
        return True

    except Exception as e:
        import traceback
        print(f"❌ Fehler: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if not main():
        exit(1)
