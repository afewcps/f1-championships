import requests
import json
import os
import time
from notion_client import Client

# F1 Drivers Championship Notion Updater für GitHub Actions

# Notion API Setup
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = "29f6839379ed8141977dc42824014a75"  # Database ID (Container)

# Liste der Rennorte für die Saison 2025
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

def get_data_source_id(database_id):
    """Findet die Data Source ID innerhalb der Database."""
    print("\n🔍 Suche Data Source in Database...")
    
    try:
        # Direkte API-Anfrage um Data Sources zu finden
        import httpx
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",  # Verwende alte API-Version für Kompatibilität
            "Content-Type": "application/json"
        }
        
        # Versuche als Database zu querien (alte Methode funktioniert noch)
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = httpx.post(url, headers=headers, json={}, timeout=30.0)
        
        if response.status_code == 200:
            print(f"✅ Database erreichbar (nutze Database ID direkt)")
            return database_id
        else:
            print(f"⚠️ Status: {response.status_code}")
            print(f"Response: {response.text}")
            return database_id
            
    except Exception as e:
        print(f"⚠️ Fehler: {e}")
        return database_id

def clear_all_entries(notion, db_id):
    """Löscht ALLE Einträge aus der Database/Data Source."""
    print("\n" + "="*60)
    print("🗑️  LÖSCHE ALLE BESTEHENDEN EINTRÄGE")
    print("="*60)
    
    deleted_count = 0
    
    try:
        # Verwende direkte HTTP-Anfrage für bessere Kontrolle
        import httpx
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # Sammle alle Pages
        all_pages = []
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
                pages = data.get("results", [])
                all_pages.extend(pages)
                has_more = data.get("has_more", False)
                start_cursor = data.get("next_cursor")
                print(f"   Batch: {len(pages)} Einträge gefunden")
            else:
                print(f"❌ Query fehlgeschlagen: {response.status_code}")
                print(f"Response: {response.text}")
                break
        
        print(f"📌 Insgesamt: {len(all_pages)} Einträge gefunden")
        
        # Lösche alle Pages
        if all_pages:
            print("🔥 Beginne mit Archivieren...")
            for i, page in enumerate(all_pages, 1):
                page_id = page["id"]
                
                # Archiviere via API
                update_url = f"https://api.notion.com/v1/pages/{page_id}"
                update_body = {"archived": True}
                
                response = httpx.patch(update_url, headers=headers, json=update_body, timeout=30.0)
                
                if response.status_code == 200:
                    deleted_count += 1
                    if i % 5 == 0 or i == len(all_pages):
                        print(f"   ✅ Archiviert: {i}/{len(all_pages)}")
                else:
                    print(f"   ⚠️ Fehler bei {page_id[:8]}: {response.status_code}")
            
            print(f"\n✅ {deleted_count} Einträge archiviert")
            print("⏳ Warte 5 Sekunden...")
            time.sleep(5)
        else:
            print("✅ Keine Einträge zum Löschen")
        
        return deleted_count
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return deleted_count

def update_database_properties(notion, db_id):
    """Aktualisiert die Properties der Database."""
    print("\n" + "="*60)
    print("🔧 AKTUALISIERE DATABASE PROPERTIES")
    print("="*60)
    
    properties = {
        "Driver": {"title": {}},
        "Total": {"number": {}}
    }
    
    for location in RACE_LOCATIONS:
        properties[location] = {"number": {}}
    
    try:
        notion.databases.update(database_id=db_id, properties=properties)
        print("✅ Properties aktualisiert")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"⚠️ Properties-Update: {e}")
        return False

def create_driver_entries(notion, db_id, weekend_points, total_points):
    """Erstellt alle Fahrer-Einträge neu."""
    print("\n" + "="*60)
    print("📝 ERSTELLE NEUE FAHRER-EINTRÄGE")
    print("="*60)
    
    sorted_drivers = sorted(
        [driver for driver in weekend_points.keys() if driver in total_points], 
        key=lambda x: total_points[x], 
        reverse=True
    )
    
    created_count = 0
    
    for position, driver in enumerate(sorted_drivers, 1):
        driver_properties = {
            "Driver": {"title": [{"text": {"content": driver}}]},
            "Total": {"number": total_points[driver]}
        }
        
        points = weekend_points.get(driver, [0] * len(RACE_LOCATIONS))
        for i, location in enumerate(RACE_LOCATIONS):
            driver_properties[location] = {"number": points[i] if points[i] > 0 else None}
        
        try:
            notion.pages.create(
                parent={"database_id": db_id},
                properties=driver_properties
            )
            created_count += 1
            print(f"✅ {position:2d}. {driver:<25} {total_points[driver]:3d} Punkte")
        except Exception as e:
            print(f"❌ Fehler bei {driver}: {e}")
    
    print(f"\n✅ {created_count} Fahrer eingetragen")
    return created_count

def update_f1_data():
    """Hauptfunktion zum Aktualisieren der F1-Daten"""
    print("\n" + "="*60)
    print("🏎️  F1 DRIVERS CHAMPIONSHIP UPDATE")
    print("="*60)
    print(f"Database ID: {DATABASE_ID}")
    
    try:
        # Initialisiere Notion Client
        notion = Client(auth=NOTION_TOKEN)
        print("✅ Notion Client initialisiert")
        
        # Hole F1-Daten
        print("\n📡 Hole F1-Daten...")
        weekend_points = get_weekend_points()
        total_points = calculate_total_points(weekend_points)
        print(f"✅ Daten für {len(total_points)} Fahrer geladen")
        
        # Finde Data Source
        data_source_id = get_data_source_id(DATABASE_ID)
        
        # Lösche alte Einträge
        deleted = clear_all_entries(notion, data_source_id)
        
        # Aktualisiere Properties
        update_database_properties(notion, data_source_id)
        
        # Erstelle neue Einträge
        created = create_driver_entries(notion, data_source_id, weekend_points, total_points)
        
        # Zusammenfassung
        print("\n" + "="*60)
        print("✅ UPDATE ERFOLGREICH!")
        print("="*60)
        print(f"Gelöscht: {deleted} | Erstellt: {created}")
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
