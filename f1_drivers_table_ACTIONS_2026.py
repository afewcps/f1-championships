import requests
import os
from notion_client import Client
import httpx

# F1 Drivers Championship Notion Updater für GitHub Actions – Saison 2026

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID  = "3166839379ed81f8bc7dc0999f1f8e6d"  # Drivers Championship 2026

RACE_LOCATIONS = [
    "Australia", "China", "Japan",
    # "Bahrain", "Saudi Arabia",  # 2026: abgesagt – regionaler Konflikt; für 2027 wieder einkommentieren
    "Miami",
    "Canada", "Monaco", "Barcelona", "Austria", "Great Britain", "Belgium",
    "Hungary", "Netherlands", "Italy", "Spain", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"

# Mapping: API-Name → Notion-Anzeigename
# Die API liefert z.B. "Andrea Kimi Antonelli", in Notion heißt der Eintrag aber "Kimi Antonelli".
API_TO_NOTION_NAME = {
    "Andrea Kimi Antonelli": "Kimi Antonelli",
}

# Mapping: Notion-Anzeigename → Seiten-ID im "Drivers 2026" DB
# Wird für die "Driver"-Relation in der Drivers Championship 2026 DB benötigt.
DRIVER_PAGE_IDS = {
    "Max Verstappen":   "3166839379ed81f3b6f5cf5864abdcba",
    "Isack Hadjar":     "3166839379ed8153acedd2bed8ed3c5e",
    "George Russell":   "3166839379ed81499980c7fde7c353e9",
    "Kimi Antonelli":   "3166839379ed814695edceee97561ad0",
    "Charles Leclerc":  "3166839379ed81049f8aca1b3fbb5c2e",
    "Lewis Hamilton":   "3166839379ed81b39fbfc668967b43ca",
    "Lando Norris":     "3166839379ed8159a2dccc7dd76ba669",
    "Oscar Piastri":    "3166839379ed81a48c4bccd923a59d12",
    "Fernando Alonso":  "3166839379ed8111856dca4832af4816",
    "Lance Stroll":     "3166839379ed81f28f6be9c75c6d86b9",
    "Alexander Albon":  "3166839379ed81d78a12e2564f90c3b9",
    "Carlos Sainz":     "3166839379ed81a3a73bf3a63e6505d6",
    "Pierre Gasly":     "3166839379ed81f6be7bd54256fb4096",
    "Franco Colapinto": "3186839379ed80ebbef3ce6d9d66cf7e",
    "Liam Lawson":      "3166839379ed81179562f8bb3d7ea15a",
    "Arvid Lindblad":   "3186839379ed80d08be1c9359498ac59",
    "Esteban Ocon":     "3166839379ed81eaa7a1d971704c679a",
    "Oliver Bearman":   "3166839379ed81488937d5a06740ae28",
    "Nico Hülkenberg":  "3166839379ed81be895df1bb7cd0fa40",
    "Gabriel Bortoleto":"3166839379ed81659d63ca189da1b672",
    "Sergio Pérez":     "3186839379ed8095acdbe00d33cbfa35",
    "Valtteri Bottas":  "3186839379ed801693e1d191cca36300",
}

TEAM_COLORS = {
    "Max Verstappen":   "#0600EF",
    "Isack Hadjar":     "#0600EF",
    "George Russell":   "#00D2BE",
    "Kimi Antonelli":   "#00D2BE",
    "Charles Leclerc":  "#DC0000",
    "Lewis Hamilton":   "#DC0000",
    "Lando Norris":     "#FF8700",
    "Oscar Piastri":    "#FF8700",
    "Fernando Alonso":  "#006F62",
    "Lance Stroll":     "#006F62",
    "Alexander Albon":  "#005AFF",
    "Carlos Sainz":     "#005AFF",
    "Pierre Gasly":     "#0090FF",
    "Franco Colapinto": "#0090FF",
    "Liam Lawson":      "#0131d1",
    "Arvid Lindblad":   "#0131d1",
    "Esteban Ocon":     "#FFFFFF",
    "Oliver Bearman":   "#FFFFFF",
    "Nico Hülkenberg":  "#00e701",
    "Gabriel Bortoleto":"#00e701",
    "Sergio Pérez":     "#B0B0B0",
    "Valtteri Bottas":  "#B0B0B0",
}


def get_sprint_points(round_num):
    """Holt Sprint-Punkte und normalisiert die Fahrernamen auf Notion-Namen."""
    url = f"{BASE_URL}{round_num}/sprint.json"
    sprint_points = {}
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            races = r.json()['MRData']['RaceTable']['Races']
            if races:
                for res in races[0]['SprintResults']:
                    api_name    = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
                    notion_name = API_TO_NOTION_NAME.get(api_name, api_name)
                    sprint_points[notion_name] = int(float(res['points']))
    except Exception:
        pass
    return sprint_points


def get_weekend_points():
    """
    Berechnet die Punkte pro Rennwochenende.
    Fahrernamen werden sofort auf Notion-Namen normalisiert (kein Duplikat-Risiko).
    """
    weekend_points = {}

    for round_num in range(1, len(RACE_LOCATIONS) + 1):
        try:
            r = requests.get(f"{BASE_URL}{round_num}/results.json", timeout=10)
            if r.status_code != 200:
                continue
        except Exception:
            continue

        races         = r.json()['MRData']['RaceTable']['Races']
        sprint_points = get_sprint_points(round_num)

        if races:
            for res in races[0]['Results']:
                api_name    = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
                notion_name = API_TO_NOTION_NAME.get(api_name, api_name)
                pts         = int(float(res['points'])) + sprint_points.get(notion_name, 0)

                if notion_name not in weekend_points:
                    weekend_points[notion_name] = [0] * len(RACE_LOCATIONS)

                if weekend_points[notion_name][round_num - 1] == 0:
                    weekend_points[notion_name][round_num - 1] = pts

    return weekend_points


def calculate_total_points(weekend_points):
    return {driver: sum(pts) for driver, pts in weekend_points.items()}


def get_existing_entries(db_id):
    """Gibt Dict {Fahrername (Notion): page_id} zurück."""
    http_headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    existing = {}
    has_more, start_cursor = True, None
    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        r = httpx.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=http_headers, json=body, timeout=30.0
        )
        if r.status_code != 200:
            print(f"❌ Query fehlgeschlagen: {r.status_code} – {r.text}")
            break
        data = r.json()
        for page in data.get("results", []):
            if page.get("archived"):
                continue
            title_prop = page["properties"].get("Name") or page["properties"].get("Driver")
            if title_prop and title_prop.get("title"):
                name = title_prop["title"][0]["text"]["content"] if title_prop["title"] else None
                if name:
                    existing[name] = page["id"]
        has_more     = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return existing


def build_properties(driver, points):
    """Baut das Notion-Properties-Dict für einen Fahrereintrag auf."""
    props = {
        "Driver": {"title": [{"text": {"content": driver}}]},
        "Total":  {"number": sum(points)}
    }

    for i, location in enumerate(RACE_LOCATIONS):
        props[location] = {"number": points[i] if points[i] > 0 else None}

    return props


def upsert_driver_entries(notion, db_id, weekend_points, total_points):
    print("\n" + "="*60)
    print("🔄 UPSERT FAHRER-EINTRÄGE")
    print("="*60)

    existing = get_existing_entries(db_id)
    print(f"📋 Bestehende Einträge in DB: {len(existing)}")

    sorted_drivers = sorted(
        weekend_points.keys(),
        key=lambda d: total_points.get(d, 0),
        reverse=True
    )

    updated, created = 0, 0

    for pos, driver in enumerate(sorted_drivers, 1):
        points = weekend_points.get(driver, [0] * len(RACE_LOCATIONS))
        props  = build_properties(driver, points)

        if driver in existing:
            try:
                notion.pages.update(page_id=existing[driver], properties=props)
                updated += 1
                print(f"♻️  {pos:2d}. {driver:<30} {total_points[driver]:3d} Pts  [aktualisiert]")
            except Exception as e:
                print(f"❌ Update-Fehler {driver}: {e}")
        else:
            try:
                notion.pages.create(parent={"database_id": db_id}, properties=props)
                created += 1
                print(f"✅ {pos:2d}. {driver:<30} {total_points[driver]:3d} Pts  [neu erstellt]")
            except Exception as e:
                print(f"❌ Erstell-Fehler {driver}: {e}")

    print(f"\n✅ Aktualisiert: {updated} | Neu erstellt: {created}")
    return updated, created


def main():
    print("\n" + "="*60)
    print("🏎️  F1 DRIVERS CHAMPIONSHIP 2026 UPDATE")
    print("="*60)
    print(f"Database ID: {DATABASE_ID}")

    try:
        notion = Client(auth=NOTION_TOKEN)
        print("✅ Notion Client initialisiert")

        print("\n📡 Hole F1-Daten (Saison 2026)...")
        weekend_points = get_weekend_points()
        total_points   = calculate_total_points(weekend_points)
        print(f"✅ Daten für {len(total_points)} Fahrer geladen")

        updated, created = upsert_driver_entries(notion, DATABASE_ID, weekend_points, total_points)

        print("\n" + "="*60)
        print("✅ UPDATE ERFOLGREICH!")
        print("="*60)
        print(f"Aktualisiert: {updated} | Neu erstellt: {created}")
        print("="*60)
        return True

    except Exception as e:
        import traceback
        print(f"\n❌ FEHLER: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if not main():
        exit(1)