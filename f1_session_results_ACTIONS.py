import fastf1
import pandas as pd
import requests
import json
import traceback
import os
from datetime import datetime, timedelta

# F1 Results to Notion für GitHub Actions

# Notion API Konfiguration
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("❌ Fehler: NOTION_TOKEN environment variable ist nicht gesetzt!")
    exit(1)

NOTION_F1_RESULTS_BLOCK_ID = "1e26839379ed80edbd00df2aaf120777"

# FastF1 Cache konfigurieren
fastf1.Cache.enable_cache("./fastf1_cache/")

# Session order for standard and sprint weekends
NORMAL_WEEKEND_ORDER = {
    "Practice 1": 1,
    "Practice 2": 2,
    "Practice 3": 3,
    "Qualifying": 4,
    "Race": 5
}

SPRINT_WEEKEND_ORDER = {
    "Practice 1": 1,
    "Sprint Qualifying": 2,
    "Sprint": 3,
    "Practice 2": 4,
    "Qualifying": 5,
    "Race": 6
}

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def get_current_race_weekend():
    """
    Automatische Erkennung des aktuellen/letzten Rennwochenendes
    Nutzt hardcodierten 2025 F1-Kalender da FastF1 API Probleme hat
    """
    print("🔍 Suche aktuelles Rennwochenende...")
    
    current_date = datetime.now().date()
    
    # F1 2025 Kalender mit Sprint-Wochenenden
    # Sprint-Wochenenden: China, Miami, Belgien, USA (Austin), Brasilien, Qatar
    f1_2025_calendar = [
        {"name": "Australian Grand Prix", "date": "2025-03-16", "sprint": False},
        {"name": "Chinese Grand Prix", "date": "2025-03-23", "sprint": True},
        {"name": "Japanese Grand Prix", "date": "2025-04-06", "sprint": False},
        {"name": "Bahrain Grand Prix", "date": "2025-04-13", "sprint": False},
        {"name": "Saudi Arabian Grand Prix", "date": "2025-04-20", "sprint": False},
        {"name": "Miami Grand Prix", "date": "2025-05-04", "sprint": True},
        {"name": "Emilia Romagna Grand Prix", "date": "2025-05-18", "sprint": False},
        {"name": "Monaco Grand Prix", "date": "2025-05-25", "sprint": False},
        {"name": "Spanish Grand Prix", "date": "2025-06-01", "sprint": False},
        {"name": "Canadian Grand Prix", "date": "2025-06-15", "sprint": False},
        {"name": "Austrian Grand Prix", "date": "2025-06-29", "sprint": False},
        {"name": "British Grand Prix", "date": "2025-07-06", "sprint": False},
        {"name": "Belgian Grand Prix", "date": "2025-07-27", "sprint": True},
        {"name": "Hungarian Grand Prix", "date": "2025-08-08", "sprint": False},
        {"name": "Dutch Grand Prix", "date": "2025-08-31", "sprint": False},
        {"name": "Italian Grand Prix", "date": "2025-09-07", "sprint": False},
        {"name": "Azerbaijan Grand Prix", "date": "2025-09-21", "sprint": False},
        {"name": "Singapore Grand Prix", "date": "2025-10-05", "sprint": False},
        {"name": "United States Grand Prix", "date": "2025-10-19", "sprint": True},
        {"name": "Mexican Grand Prix", "date": "2025-10-26", "sprint": False},
        {"name": "Brazilian Grand Prix", "date": "2025-11-09", "sprint": True},
        {"name": "Las Vegas Grand Prix", "date": "2025-11-22", "sprint": False},
        {"name": "Qatar Grand Prix", "date": "2025-11-30", "sprint": True},
        {"name": "Abu Dhabi Grand Prix", "date": "2025-12-07", "sprint": False}
    ]
    
    print(f"📅 Lade F1 2025 Kalender ({len(f1_2025_calendar)} Rennen)")
    
    # Suche das passende Event
    best_event = None
    best_date_diff = float('inf')
    
    for event in f1_2025_calendar:
        race_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
        date_diff = (current_date - race_date).days
        
        print(f"📊 {event['name']}: {event['date']} (Diff: {date_diff} Tage) - Sprint: {event['sprint']}")
        
        # Suche das Rennen im Zeitraum von -7 bis +3 Tagen
        if -7 <= date_diff <= 3:
            if abs(date_diff) < abs(best_date_diff):
                best_event = event
                best_date_diff = date_diff
    
    if best_event is not None:
        print(f"🏁 Gefunden: {best_event['name']}")
        print(f"🏃 Sprint-Wochenende: {'Ja' if best_event['sprint'] else 'Nein'}")
        print(f"📅 Renndatum: {best_event['date']}")
        
        return 2025, best_event['name'], best_event['sprint']
    else:
        print("❌ Kein passendes Rennwochenende gefunden")
        return None, None, False

def find_gp_database(gp_name, year):
    """Find a GP database by name using the pattern 'Name Year'."""
    print(f"🔍 Suche Datenbank: {gp_name} {year}")
    
    search_url = "https://api.notion.com/v1/search"
    search_query = f"{gp_name} {year}"
    
    search_payload = {
        "query": search_query,
        "filter": {
            "property": "object",
            "value": "database"
        }
    }
    
    response = requests.post(search_url, headers=headers, json=search_payload)
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        for result in results:
            if result.get("object") == "database":
                db_title = result.get("title", [{}])[0].get("text", {}).get("content", "")
                expected_title = f"{gp_name} {year}"
                
                if expected_title in db_title:
                    print(f"✅ Gefundene Datenbank: {db_title}")
                    return result["id"]
    
    print(f"❌ Keine Datenbank gefunden für: {gp_name} {year}")
    return None

def get_results_for_session(year, gp_name, session_type):
    """Get the results for a specific session."""
    session_display_names = {
        'FP1': 'Practice 1',
        'FP2': 'Practice 2',
        'FP3': 'Practice 3',
        'Q': 'Qualifying',
        'SQ': 'Sprint Qualifying',
        'S': 'Sprint',
        'R': 'Race'
    }
    
    display_name = session_display_names.get(session_type, session_type)
    print(f"📊 Verarbeite {display_name}...")
    
    try:
        # Load session
        try:
            session = fastf1.get_session(year, gp_name, session_type)
        except ValueError as e:
            print(f"⚠️ Session {display_name} existiert nicht für {gp_name} {year}: {str(e)}")
            return None
            
        # Check if session has data before loading
        try:
            session.load()
        except Exception as e:
            print(f"⚠️ Konnte keine Daten für {display_name} laden: {str(e)}")
            return None
        
        # Different handling based on session type
        if session_type in ['R', 'S']:  # Race or Sprint
            results = session.results.copy()
            
            positions_dict = {}
            for i, row in results.iterrows():
                try:
                    pos = int(row["Position"])
                    positions_dict[pos] = row["Abbreviation"]
                except (ValueError, TypeError):
                    pass
        else:  # Qualifying, Practice, etc.
            laps = session.laps
            fastest_laps = laps.groupby("DriverNumber")["LapTime"].min().reset_index()
            merged_results = pd.merge(session.results, fastest_laps, on="DriverNumber")
            sorted_results = merged_results.sort_values(by="LapTime")
            
            positions_dict = {}
            for i, row in enumerate(sorted_results.itertuples(), 1):
                positions_dict[i] = row.Abbreviation
        
        print(f"✅ {display_name}: {len(positions_dict)} Positionen geladen")
        
        return {
            "session_name": display_name,
            "session_date": session.date,
            "positions": positions_dict
        }
    except Exception as e:
        print(f"❌ Fehler bei {display_name}: {str(e)}")
        return None

def save_session_to_notion(database_id, session_data, is_sprint_weekend):
    """Save a session's results to the GP database."""
    if not session_data:
        return False
        
    session_name = session_data["session_name"]
    positions_dict = session_data["positions"]
    
    print(f"💾 Speichere {session_name} in Notion...")
    
    # Determine session order
    order_mapping = SPRINT_WEEKEND_ORDER if is_sprint_weekend else NORMAL_WEEKEND_ORDER
    session_order = order_mapping.get(session_name, 99)
    
    # Check if this session already exists
    query_url = f"https://api.notion.com/v1/databases/{database_id}/query"
    query_data = {
        "filter": {
            "property": "Session",
            "title": {
                "equals": session_name
            }
        }
    }
    
    response = requests.post(query_url, headers=headers, json=query_data)
    
    if response.status_code != 200:
        print(f"❌ Fehler beim Abfragen der Datenbank: {response.status_code}")
        return False
    
    results = response.json().get("results", [])
    
    # Prepare the properties
    properties = {
        "Session": {"title": [{"text": {"content": session_name}}]},
        "Session Order": {"number": session_order}
    }
    
    # Add driver abbreviations for each position
    for pos in range(1, 21):
        driver_abbreviation = positions_dict.get(pos, "")
        properties[f"P{pos}"] = {"rich_text": [{"text": {"content": driver_abbreviation}}]}
    
    if results:
        # Update existing page
        page_id = results[0]["id"]
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        update_data = {"properties": properties}
        
        response = requests.patch(update_url, headers=headers, json=update_data)
        
        if response.status_code == 200:
            print(f"✅ {session_name} aktualisiert")
            return True
        else:
            print(f"❌ Fehler beim Aktualisieren von {session_name}: {response.status_code}")
            return False
    else:
        # Create new page
        create_url = "https://api.notion.com/v1/pages"
        create_data = {
            "parent": {"database_id": database_id},
            "properties": properties
        }
        
        response = requests.post(create_url, headers=headers, json=create_data)
        
        if response.status_code == 200:
            print(f"✅ {session_name} erstellt")
            return True
        else:
            print(f"❌ Fehler beim Erstellen von {session_name}: {response.status_code}")
            return False

def process_race_weekend(year, gp_name, is_sprint_weekend):
    """Process all sessions for a race weekend."""
    print(f"🏁 Verarbeite {gp_name} GP {year}")
    print(f"🏃 Sprint-Format: {'Ja' if is_sprint_weekend else 'Nein'}")
    
    # Find database
    gp_database_id = find_gp_database(gp_name, year)
    if not gp_database_id:
        print(f"❌ Keine Datenbank gefunden für {gp_name} {year}")
        return False
    
    # Define session types
    if is_sprint_weekend:
        session_types = ['FP1', 'SQ', 'S', 'FP2', 'Q', 'R']
    else:
        session_types = ['FP1', 'FP2', 'FP3', 'Q', 'R']
    
    success_count = 0
    
    # Process each session
    for session_type in session_types:
        try:
            session_data = get_results_for_session(year, gp_name, session_type)
            if session_data:
                if save_session_to_notion(gp_database_id, session_data, is_sprint_weekend):
                    success_count += 1
            else:
                print(f"ℹ️ Keine Daten für {session_type}")
        except Exception as e:
            print(f"❌ Fehler bei {session_type}: {str(e)}")
    
    print(f"📊 Abgeschlossen: {success_count}/{len(session_types)} Sessions verarbeitet")
    return success_count > 0

def main():
    """Hauptfunktion für GitHub Actions"""
    print("🚀 Starte F1 Results Auto-Update...")
    
    # Automatische Erkennung des Rennwochenendes
    year, gp_name, is_sprint_weekend = get_current_race_weekend()
    
    if not year or not gp_name:
        print("❌ Konnte kein aktuelles Rennwochenende ermitteln")
        return False
    
    # Verarbeite das Rennwochenende
    success = process_race_weekend(year, gp_name, is_sprint_weekend)
    
    if success:
        print("✅ F1 Results Update erfolgreich abgeschlossen!")
        return True
    else:
        print("❌ F1 Results Update fehlgeschlagen!")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
