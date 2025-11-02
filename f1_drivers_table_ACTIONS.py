import requests
import json
import os
import time
from notion_client import Client

# F1 Drivers Championship Notion Updater für GitHub Actions

# Notion API Setup
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = "29f6839379ed8141977dc42824014a75"  # Direkte Database ID

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

def setup_database_structure(notion, database_id):
    """Stellt sicher, dass die Database die richtige Struktur hat."""
    print(f"🔧 Richte Database-Struktur ein für ID: {database_id}")
    
    try:
        # Hole aktuelle Database-Info
        db_info = notion.databases.retrieve(database_id=database_id)
        existing_props = db_info.get("properties", {})
        print(f"Existierende Properties: {list(existing_props.keys())}")
        
        # Definiere gewünschte Properties
        required_properties = {}
        
        # Driver als Title
        if "Driver" not in existing_props:
            required_properties["Driver"] = {"title": {}}
        
        # Alle Race Locations als Number
        for i, location in enumerate(RACE_LOCATIONS, 1):
            prop_name = f"{i:02d}. {location}"  # z.B. "01. Australia"
            if prop_name not in existing_props:
                required_properties[prop_name] = {
                    "number": {"format": "number"}
                }
        
        # Total am Ende
        if "Total" not in existing_props:
            required_properties["Total"] = {
                "number": {"format": "number"}
            }
        
        # Füge fehlende Properties hinzu
        if required_properties:
            print(f"➕ Füge {len(required_properties)} neue Properties hinzu...")
            for prop_name in required_properties.keys():
                print(f"   - {prop_name}")
            
            notion.databases.update(
                database_id=database_id,
                properties=required_properties
            )
            print("✅ Database-Struktur aktualisiert")
            time.sleep(2)  # Warte kurz nach Update
        else:
            print("✅ Alle Properties existieren bereits")
        
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Setup der Database-Struktur: {repr(e)}")
        import traceback
        traceback.print_exc()
        return False

def clear_database_entries(notion, database_id):
    """Löscht alle bestehenden Einträge aus der Database."""
    print("🗑️  Lösche bestehende Einträge...")
    
    try:
        # Hole alle Einträge
        has_more = True
        start_cursor = None
        deleted_count = 0
        
        while has_more:
            query_params = {"database_id": database_id, "page_size": 100}
            if start_cursor:
                query_params["start_cursor"] = start_cursor
            
            response = notion.databases.query(**query_params)
            entries = response.get("results", [])
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")
            
            for entry in entries:
                notion.pages.update(page_id=entry["id"], archived=True)
                deleted_count += 1
        
        print(f"✅ {deleted_count} Einträge archiviert")
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Löschen der Einträge: {repr(e)}")
        import traceback
        traceback.print_exc()
        return False

def populate_database(notion, database_id, weekend_points, total_points):
    """Füllt die Database mit Fahrerdaten."""
    print("📝 Erstelle neue Einträge...")
    
    # Sortiere Fahrer nach Gesamtpunkten
    sorted_drivers = sorted(
        [driver for driver in weekend_points.keys() if driver in total_points],
        key=lambda x: total_points[x],
        reverse=True
    )
    
    created_count = 0
    
    for driver in sorted_drivers:
        try:
            # Baue Properties für diesen Fahrer
            properties = {
                "Driver": {
                    "title": [{"type": "text", "text": {"content": driver}}]
                }
            }
            
            # Füge Punkte für jedes Rennen hinzu
            points = weekend_points.get(driver, [0] * len(RACE_LOCATIONS))
            for i, location in enumerate(RACE_LOCATIONS):
                prop_name = f"{i+1:02d}. {location}"
                
                # Nur Werte > 0 eintragen
                if points[i] > 0:
                    properties[prop_name] = {"number": points[i]}
            
            # Füge Total hinzu
            properties["Total"] = {"number": total_points[driver]}
            
            # Erstelle Page
            response = notion.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
            
            created_count += 1
            print(f"✅ {created_count:2d}. {driver:<25} - {total_points[driver]:3d} Punkte")
            
        except Exception as e:
            print(f"❌ Fehler bei {driver}: {repr(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n✅ {created_count} Fahrer erfolgreich eingetragen")
    return created_count > 0

def update_f1_data():
    """Hauptfunktion zum Aktualisieren der F1-Daten"""
    print("=" * 60)
    print("🏎️  F1 DRIVERS CHAMPIONSHIP UPDATE")
    print("=" * 60)
    
    try:
        # Initialisiere Notion Client
        notion = Client(auth=NOTION_TOKEN)
        print(f"✅ Notion Client initialisiert")
        print(f"📊 Database ID: {DATABASE_ID}")
        
        # Hole Daten von der API
        print("\n📡 Hole Daten von Jolpica API...")
        weekend_points = get_weekend_points()
        total_points = calculate_total_points(weekend_points)
        
        driver_count = len([d for d in weekend_points.keys() if d in total_points])
        print(f"✅ Daten für {driver_count} Fahrer geladen")
        
        # Zeige Top 3
        sorted_drivers = sorted(
            [driver for driver in weekend_points.keys() if driver in total_points],
            key=lambda x: total_points[x],
            reverse=True
        )
        print("\n🏆 Aktuelle Top 3:")
        for i, driver in enumerate(sorted_drivers[:3], 1):
            print(f"   {i}. {driver:<25} {total_points[driver]:3d} Punkte")
        
        # Setup Database-Struktur
        print("\n" + "=" * 60)
        if not setup_database_structure(notion, DATABASE_ID):
            raise Exception("Database-Setup fehlgeschlagen")
        
        # Lösche alte Einträge
        print("\n" + "=" * 60)
        if not clear_database_entries(notion, DATABASE_ID):
            raise Exception("Löschen der Einträge fehlgeschlagen")
        
        # Fülle Database neu
        print("\n" + "=" * 60)
        if not populate_database(notion, DATABASE_ID, weekend_points, total_points):
            raise Exception("Erstellen der Einträge fehlgeschlagen")
        
        # Abschluss
        print("\n" + "=" * 60)
        print("✅ UPDATE ERFOLGREICH ABGESCHLOSSEN!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ FEHLER: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = update_f1_data()
    if not success:
        exit(1)
