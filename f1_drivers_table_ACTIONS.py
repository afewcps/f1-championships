import requests
import json
import os
import time
from notion_client import Client

# F1 Drivers Championship Notion Updater für GitHub Actions

# Notion API Setup
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_NAME = "Drivers Championship"

# Liste der Rennorte für die Saison 2025 in englischer Sprache und korrekter Reihenfolge
RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami", "Emilia-Romagna", "Monaco",
    "Spain", "Canada", "Austria", "Great Britain", "Belgium", "Hungary", "Netherlands",
    "Italy", "Azerbaijan", "Singapore", "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# Jolpica-API-Link
BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"

# Team Colors Dictionary
TEAM_COLORS = {
    "Max Verstappen": "#0600EF",
    "Yuki Tsunoda": "#0600EF",
    "George Russell": "#00D2BE",
    "Andrea Kimi Antonelli": "#00D2BE",
    "Charles Leclerc": "#DC0000",
    "Lewis Hamilton": "#DC0000",
    "Lando Norris": "#FF8700",
    "Oscar Piastri": "#FF8700",
    "Fernando Alonso": "#006F62",
    "Lance Stroll": "#006F62",
    "Alexander Albon": "#005AFF",
    "Carlos Sainz": "#005AFF",
    "Pierre Gasly": "#0090FF",
    "Jack Doohan": "#0090FF",
    "Liam Lawson": "#0131d1",
    "Isack Hadjar": "#0131d1",
    "Esteban Ocon": "#FFFFFF",
    "Oliver Bearman": "#FFFFFF",
    "Nico Hülkenberg": "#00e701",
    "Gabriel Bortoletto": "#00e701",
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
            race = races[0]
            for result in race['SprintResults']:
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
    """Berechnet die echten Gesamtpunkte durch Aufsummieren der Wochenendpunkte."""
    total_points = {}
    
    for driver, points_list in weekend_points.items():
        total_points[driver] = sum(points_list)
    
    return total_points

def get_or_create_parent_page(notion):
    """Gibt die fest definierte Parent-Page-ID zurück"""
    return "1e26839379ed80edbd00df2aaf120777"

def create_notion_database(weekend_points, total_points):
    """Erstellt oder aktualisiert die Notion-Datenbank mit den F1-Fahrerwertungen."""
    notion = Client(auth=NOTION_TOKEN)

    sorted_drivers = sorted(
        [driver for driver in weekend_points.keys() if driver in total_points],
        key=lambda x: total_points[x],
        reverse=True
    )

    parent_page_id = get_or_create_parent_page(notion)
    print(f"Parent page id: {parent_page_id}")

    # Suche nach bestehender Datenbank - OHNE Filter
    database_id = None
    try:
        # Notion API v2023-06-01+ erlaubt nur "page" oder "data_source" als Filter
        # Wir suchen ohne Filter und filtern manuell
        results = notion.search(query=DATABASE_NAME).get("results", [])
        print(f"Notion search returned {len(results)} results for query '{DATABASE_NAME}'")
        
        for result in results:
            if result.get("object") == "database":
                title_text = "".join([t.get("plain_text", "") for t in result.get("title", [])])
                print(f"Found database candidate: id={result.get('id')}, title='{title_text}'")
                if title_text == DATABASE_NAME:
                    database_id = result["id"]
                    print(f"✅ Matched database: {database_id}")
                    break
    except Exception as e:
        print("❌ Fehler bei Notion search():", repr(e))
        import traceback
        traceback.print_exc()
        raise

    # Properties-Definition mit explizitem Format
    properties = {
        "Driver": {
            "title": {}
        },
        "Total": {
            "number": {
                "format": "number"
            }
        }
    }
    
    for location in RACE_LOCATIONS:
        properties[location] = {
            "number": {
                "format": "number"
            }
        }

    # Database erstellen wenn nicht vorhanden
    if not database_id:
        print("Keine existierende Datenbank gefunden – erstelle neue Datenbank...")
        try:
            response = notion.databases.create(
                parent={"type": "page_id", "page_id": parent_page_id},
                title=[{"type": "text", "text": {"content": DATABASE_NAME}}],
                properties=properties
            )
            database_id = response.get("id")
            print(f"✅ Erstellt neue Database: {database_id}")
        except Exception as e:
            print("❌ Fehler beim Erstellen der Datenbank:", repr(e))
            import traceback
            traceback.print_exc()
            raise
    else:
        print(f"Verwende existierende Database: {database_id}")
        
        # Properties prüfen und ergänzen
        try:
            db_info = notion.databases.retrieve(database_id=database_id)
            existing_props = db_info.get("properties", {})
            print(f"Existierende Properties: {list(existing_props.keys())}")
            
            props_to_add = {}
            for prop_name, prop_config in properties.items():
                if prop_name not in existing_props:
                    props_to_add[prop_name] = prop_config
                    print(f"Property '{prop_name}' fehlt - wird hinzugefügt")
            
            if props_to_add:
                print(f"Füge {len(props_to_add)} neue Properties hinzu...")
                notion.databases.update(database_id=database_id, properties=props_to_add)
                print("✅ Datenbank-Eigenschaften aktualisiert.")
            else:
                print("✅ Alle Properties existieren bereits.")
                
        except Exception as e:
            print("⚠️ Warnung: properties update fehlgeschlagen:", repr(e))
            import traceback
            traceback.print_exc()
    
        # Alte Einträge archivieren
        try:
            existing_entries = notion.databases.query(database_id=database_id, page_size=100).get("results", [])
            print(f"Anzahl existierender Einträge: {len(existing_entries)}")
            for entry in existing_entries:
                eid = entry.get("id")
                notion.pages.update(page_id=eid, archived=True)
                print(f"Archiviert entry id={eid}")
        except Exception as e:
            print("❌ Fehler beim Archivieren vorhandener Einträge:", repr(e))
            import traceback
            traceback.print_exc()
            raise

    if not database_id:
        raise RuntimeError("Database ID konnte nicht ermittelt werden – Abbruch.")

    # Kurze Pause für Notion
    time.sleep(2)

    # Pages erstellen
    created_count = 0
    for driver in sorted_drivers:
        driver_properties = {
            "Driver": {
                "title": [{"type": "text", "text": {"content": driver}}]
            },
            "Total": {
                "number": total_points[driver]
            }
        }
        
        points = weekend_points.get(driver, [0] * len(RACE_LOCATIONS))
        for i, location in enumerate(RACE_LOCATIONS):
            if points[i] > 0:
                driver_properties[location] = {"number": points[i]}

        try:
            resp = notion.pages.create(
                parent={"database_id": database_id},
                properties=driver_properties
            )
            created_count += 1
            created_id = resp.get("id")
            print(f"✅ Erstellt Page für {driver}: id={created_id}")
        except Exception as e:
            print(f"❌ Fehler beim Erstellen der Page für {driver}:", repr(e))
            import traceback
            traceback.print_exc()
            continue

    print(f"✅ Erstellt {created_count} Fahrer-Einträge in der Datenbank {database_id}")
    return database_id

def update_f1_data():
    """Hauptfunktion zum Aktualisieren der F1-Daten"""
    print("🔄 Aktualisiere die Fahrer-Meisterschaft in Notion...")
    
    try:
        weekend_points = get_weekend_points()
        total_points = calculate_total_points(weekend_points)
        database_id = create_notion_database(weekend_points, total_points)
        
        print(f"✅ Fertig! Die Fahrer-Meisterschaft wurde in Notion aktualisiert (Database ID: {database_id})")
        
        print("\nAktualisierte Fahrerwertung:")
        print("-" * 50)
        
        sorted_drivers = sorted(
            [driver for driver in weekend_points.keys() if driver in total_points], 
            key=lambda x: total_points[x], 
            reverse=True
        )
        
        for i, driver in enumerate(sorted_drivers, 1):
            print(f"{i:2d}. {driver:<25} {total_points[driver]:3d} Punkte")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Aktualisieren der Daten: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = update_f1_data()
    if not success:
        exit(1)
