import requests
import json
import os
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
    # Red Bull Racing
    "Max Verstappen": "#0600EF",  # Deep Blue
    "Yuki Tsunoda": "#0600EF",    # Deep Blue
    
    # Mercedes
    "George Russell": "#00D2BE",  # Turquoise
    "Andrea Kimi Antonelli": "#00D2BE",  # Turquoise
    
    # Ferrari
    "Charles Leclerc": "#DC0000",  # Ferrari Red
    "Lewis Hamilton": "#DC0000",     # Ferrari Red
    
    # McLaren
    "Lando Norris": "#FF8700",    # Orange
    "Oscar Piastri": "#FF8700",   # Orange
    
    # Aston Martin
    "Fernando Alonso": "#006F62",  # Racing Green
    "Lance Stroll": "#006F62",     # Racing Green
    
    # Williams
    "Alexander Albon": "#005AFF",  # Williams Blue
    "Carlos Sainz": "#005AFF",   # Williams Blue
    
    # Alpine
    "Pierre Gasly": "#0090FF",    # Alpine Blue
    "Jack Doohan": "#0090FF",    # Alpine Blue
    
    # AlphaTauri
    "Liam Lawson": "#0131d1",  # Blue
    "Isack Hadjar": "#0131d1",      # Blue
    
    # Haas
    "Esteban Ocon": "#FFFFFF",  # White
    "Oliver Bearman": "#FFFFFF",  # White
    
    # Kick Sauber
    "Nico Hülkenberg": "#00e701",  #Green
    "Gabriel Bortoletto": "#00e701", #Green
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
            
            # Sprint-Punkte abrufen
            sprint_points = get_sprint_points(round_num)

            # Hole Punkte aus dem aktuellen Rennen, falls Daten vorhanden
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

def get_cumulative_points():
    """Lädt die Fahrerwertung aus der API mit kumulativen Punkten."""
    # Initialize standings with all known drivers
    standings = {team: [0] * len(RACE_LOCATIONS) for team in TEAM_COLORS.keys()}
    
    # Holen wir die Wochenendpunkte und summieren sie korrekt
    weekend_points = get_weekend_points()
    
    # Aktualisiere für jeden Fahrer die kumulativen Punktestände
    for driver, points_list in weekend_points.items():
        if driver not in standings:
            standings[driver] = [0] * len(RACE_LOCATIONS)
        
        # Berechne den kumulativen Punktestand für jeden GP
        cumulative = 0
        for i, points in enumerate(points_list):
            cumulative += points
            standings[driver][i] = cumulative
    
    # Berechne die korrekten Gesamtpunkte
    total_points = calculate_total_points(weekend_points)
    
    return standings, total_points
def create_notion_database(weekend_points, total_points):
    """Erstellt oder aktualisiert die Notion-Datenbank mit den F1-Fahrerwertungen (robuste Version)."""
    notion = Client(auth=NOTION_TOKEN)

    # Sortiere Fahrer nach Gesamtpunkten (absteigend)
    sorted_drivers = sorted(
        [driver for driver in weekend_points.keys() if driver in total_points],
        key=lambda x: total_points[x],
        reverse=True
    )

    # Parent page holen
    parent_page_id = get_or_create_parent_page(notion)
    print(f"Parent page id: {parent_page_id}")

    # Suche nach bestehender Datenbank mit exakt diesem Titel
    database_id = None
    try:
        results = notion.search(query=DATABASE_NAME).get("results", [])
        print(f"Notion search returned {len(results)} results for query '{DATABASE_NAME}'")
        for result in results:
            if result.get("object") == "database":
                # title kann mehrere Blöcke enthalten -> compare plain_text join
                title_text = "".join([t.get("plain_text", "") for t in result.get("title", [])])
                print(f"Found database candidate: id={result.get('id')}, title='{title_text}'")
                if title_text == DATABASE_NAME:
                    database_id = result["id"]
                    break
    except Exception as e:
        print("❌ Fehler bei Notion search():", repr(e))
        raise

    # Erstelle die Properties-Definition
    properties = {
        "Driver": {"title": {}},
        "Total": {"number": {}}
    }
    for location in RACE_LOCATIONS:
        properties[location] = {"number": {}}

    # Wenn keine DB existiert: erstellen
    if not database_id:
        print("Keine existierende Datenbank gefunden — erstelle neue Datenbank...")
        try:
            response = notion.databases.create(
                parent={"type": "page_id", "page_id": parent_page_id},
                title=[{"type": "text", "text": {"content": DATABASE_NAME}}],
                properties=properties
            )
            database_id = response.get("id")
            print(f"Erstellt neue Database: {database_id}")
        except Exception as e:
            print("❌ Fehler beim Erstellen der Datenbank:", repr(e))
            # wenn Notion eine detailliertere Response hat, geben wir sie aus (falls verfügbar)
            try:
                import traceback; traceback.print_exc()
            except:
                pass
            raise

    else:
        print(f"Verwende existierende Database: {database_id}")
        # Versuche die Properties zu aktualisieren (falls notwendig)
        try:
            notion.databases.update(database_id=database_id, properties=properties)
            print("Datenbank-Eigenschaften (properties) aktualisiert.")
        except Exception as e:
            print("⚠️ Warnung: properties update fehlgeschlagen:", repr(e))
            # Nicht fatal: wir fahren trotzdem fort, denn evtl. sind Eigenschaften bereits korrekt.
    
        # Lösche / archive alle aktiven Einträge in dieser DB (clean slate)
        try:
            existing_entries = notion.databases.query(database_id=database_id, page_size=100).get("results", [])
            print(f"Anzahl existierender Einträge: {len(existing_entries)}")
            for entry in existing_entries:
                eid = entry.get("id")
                print(f"Archiviere entry id={eid}")
                notion.pages.update(page_id=eid, archived=True)
        except Exception as e:
            print("❌ Fehler beim Archivieren vorhandener Einträge:", repr(e))
            raise

    # Safety check: database_id muss jetzt vorhanden sein
    if not database_id:
        raise RuntimeError("Database ID konnte nicht ermittelt werden — Abbruch.")

    # Erstelle für jeden Fahrer eine neue Page (mit Logging)
    created_count = 0
    for driver in sorted_drivers:
        driver_properties = {
            "Driver": {"title": [{"text": {"content": driver}}]},
            "Total": {"number": total_points[driver]}
        }
        points = weekend_points.get(driver, [0] * len(RACE_LOCATIONS))
        for i, location in enumerate(RACE_LOCATIONS):
            driver_properties[location] = {"number": points[i] if points[i] > 0 else None}

        try:
            resp = notion.pages.create(
                parent={"database_id": database_id},
                properties=driver_properties
            )
            created_count += 1
            created_id = resp.get("id")
            print(f"Erstellt Page für {driver}: id={created_id}")
        except Exception as e:
            print(f"❌ Fehler beim Erstellen der Page für {driver}:", repr(e))
            # Drucke Stacktrace wenn möglich
            try:
                import traceback; traceback.print_exc()
            except:
                pass
            # Continue / skip diese Person, damit der ganze Run nicht sofort abbricht
            continue

    print(f"Erstellt {created_count} Fahrer-Einträge in der Datenbank {database_id}")
    return database_id


def get_or_create_parent_page(notion):
    """Gibt die fest definierte Parent-Page-ID zurück"""
    return "1e26839379ed80edbd00df2aaf120777"

def update_f1_data():
    """Hauptfunktion zum Aktualisieren der F1-Daten"""
    print("🔄 Aktualisiere die Fahrer-Meisterschaft in Notion...")
    
    try:
        weekend_points = get_weekend_points()
        total_points = calculate_total_points(weekend_points)
        database_id = create_notion_database(weekend_points, total_points)
        
        print(f"✅ Fertig! Die Fahrer-Meisterschaft wurde in Notion aktualisiert (Database ID: {database_id})")
        
        # Zeige die aktualisierten Daten in der Konsole
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
        return False

if __name__ == "__main__":
    success = update_f1_data()
    if not success:
        exit(1)
