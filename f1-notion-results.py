import fastf1
import pandas as pd
import requests
import json
from datetime import datetime

# Notion API Configuration
NOTION_TOKEN = "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"
NOTION_F1_RESULTS_BLOCK_ID = "1e26839379ed80edbd00df2aaf120777"  # ID of the "F1 Session Results" toggle block

# Headers for Notion API requests
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Cache configuration for FastF1
fastf1.Cache.enable_cache("C:\\Users\\simon\\Downloads\\fast f1 cache\\")

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

def find_gp_database(gp_name, year):
    """Find a GP database by name."""
    # Search for existing database with this GP name
    search_url = "https://api.notion.com/v1/search"
    search_payload = {
        "query": f"{gp_name} GP {year}",
        "filter": {
            "property": "object",
            "value": "database"
        }
    }
    
    response = requests.post(search_url, headers=headers, json=search_payload)
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        for result in results:
            if result.get("object") == "database" and f"{gp_name} GP {year}" in result.get("title", [{}])[0].get("text", {}).get("content", ""):
                print(f"Found existing database for {gp_name} GP {year}")
                return result["id"]
    
    return None

def create_gp_database(gp_name, year):
    """Create a new database in Notion for a specific Grand Prix under the F1 Session Results toggle block."""
    url = "https://api.notion.com/v1/databases"
    
    # Prepare properties for the database - ensure P1 to P20 are in order by using an ordered dict
    properties = {
        "Session": {"title": {}},  # Title property will be the session name
        "Session Order": {"number": {}}  # For ordering the sessions correctly
    }
    
    # Add positions from P1 to P20 as properties in ascending order
    for i in range(1, 21):
        properties[f"P{i}"] = {"rich_text": {}}
    
    # Fix: Correct parent format for block_id
    payload = {
        "parent": {
            "type": "page_id",  # Changed from block_id to page_id
            "page_id": NOTION_F1_RESULTS_BLOCK_ID
        },
        "title": [{"type": "text", "text": {"content": f"{gp_name} GP {year}"}}],
        "properties": properties,
        "is_inline": False  # Make it a full-page database, not inline
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        database_id = response.json()["id"]
        print(f"Created new database for {gp_name} GP {year} with ID: {database_id}")
        
        # Set the title only (removed sorts and properties_config as they're not supported in this API)
        view_url = f"https://api.notion.com/v1/databases/{database_id}"
        view_payload = {
            "title": [{"type": "text", "text": {"content": f"{gp_name} GP {year}"}}]
        }
        
        view_response = requests.patch(view_url, headers=headers, json=view_payload)
        if view_response.status_code == 200:
            print(f"Updated database title for {gp_name} GP {year}")
        else:
            print(f"Failed to update database title: {view_response.status_code}")
            print(view_response.text)
        
        return database_id
    else:
        print(f"Failed to create database: {response.status_code}")
        print(response.text)
        return None

def get_results_for_session(year, gp_name, session_type):
    """Get the results for a specific session."""
    # Map session type codes to display names
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
    
    try:
        # Load session
        try:
            session = fastf1.get_session(year, gp_name, session_type)
        except ValueError as e:
            print(f"Session {display_name} does not exist for {gp_name} GP {year}: {str(e)}")
            return None
            
        # Check if session has data before loading
        try:
            session.load()
        except Exception as e:
            print(f"Could not load data for {display_name}: {str(e)}")
            return None
        
        # Different handling based on session type
        if session_type in ['R', 'S']:  # Race or Sprint
            # Use the actual race results
            results = session.results.copy()
            
            # Handle DNF, DSQ, etc.
            positions_dict = {}
            for i, row in results.iterrows():
                try:
                    pos = int(row["Position"])
                    positions_dict[pos] = row["Abbreviation"]
                except (ValueError, TypeError):
                    # Skip non-numeric positions
                    pass
        else:  # Qualifying, Practice, etc.
            # Extract all lap times
            laps = session.laps
            
            # Calculate the fastest lap for each driver
            fastest_laps = laps.groupby("DriverNumber")["LapTime"].min().reset_index()
            
            # Merge with session results to get driver info
            merged_results = pd.merge(session.results, fastest_laps, on="DriverNumber")
            
            # Sort by fastest lap time
            sorted_results = merged_results.sort_values(by="LapTime")
            
            # Create positions dictionary
            positions_dict = {}
            for i, row in enumerate(sorted_results.itertuples(), 1):
                positions_dict[i] = row.Abbreviation
        
        return {
            "session_name": display_name,
            "session_date": session.date,
            "positions": positions_dict
        }
    except Exception as e:
        print(f"Error processing {display_name}: {str(e)}")
        return None

def save_session_to_notion(database_id, session_data, is_sprint_weekend):
    """Save a session's results to the GP database."""
    if not session_data:
        return
        
    session_name = session_data["session_name"]
    positions_dict = session_data["positions"]
    session_date = session_data["session_date"]
    
    # Determine session order
    order_mapping = SPRINT_WEEKEND_ORDER if is_sprint_weekend else NORMAL_WEEKEND_ORDER
    session_order = order_mapping.get(session_name, 99)  # Default to high number if not found
    
    # First, check if this session already exists in the database
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
        print(f"Failed to query database: {response.status_code}")
        print(response.text)
        return
    
    # Check if we found existing results
    results = response.json().get("results", [])
    
    # Prepare the properties to update or create
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
            print(f"Updated {session_name} in Notion")
        else:
            print(f"Failed to update {session_name}: {response.status_code}")
            print(response.text)
    else:
        # Create new page in the database
        create_url = "https://api.notion.com/v1/pages"
        create_data = {
            "parent": {"database_id": database_id},
            "properties": properties
        }
        
        response = requests.post(create_url, headers=headers, json=create_data)
        
        if response.status_code == 200:
            print(f"Created new entry for {session_name}")
        else:
            print(f"Failed to create entry for {session_name}: {response.status_code}")
            print(response.text)

def process_race_weekend(year, gp_name, is_sprint_weekend):
    """Process all sessions for a race weekend."""
    # First, try to find an existing database for this GP
    gp_database_id = find_gp_database(gp_name, year)
    
    # If not found, create a new one
    if not gp_database_id:
        print(f"No existing database found for {gp_name} GP {year}. Creating new one...")
        gp_database_id = create_gp_database(gp_name, year)
    
    if not gp_database_id:
        print("Failed to create or find GP database.")
        return
    
    # Check if this is a future event
    current_date = datetime.now()
    if year > current_date.year:
        print(f"Warning: {gp_name} GP {year} is in the future - data may be limited or unavailable")
    elif year == current_date.year:
        print(f"Processing current year's event: {gp_name} GP {year}")
        print("Note: Some sessions may not have occurred yet")
    
    # Define session types based on weekend type
    if is_sprint_weekend:
        session_types = ['FP1', 'SQ', 'S', 'FP2', 'Q', 'R']
    else:
        session_types = ['FP1', 'FP2', 'FP3', 'Q', 'R']
    
    # Process each session
    for session_type in session_types:
        try:
            print(f"Processing {gp_name} {session_type}...")
            session_data = get_results_for_session(year, gp_name, session_type)
            if session_data:
                save_session_to_notion(gp_database_id, session_data, is_sprint_weekend)
            else:
                print(f"No data available for {gp_name} {session_type}")
        except Exception as e:
            print(f"Error with {session_type}: {str(e)}")
            import traceback
            traceback.print_exc()

def check_fastf1_available_events(year):
    """Check which events are available in FastF1 for the given year."""
    try:
        # Get the schedule for the year
        schedule = fastf1.get_event_schedule(year)
        print(f"\nAvailable events for {year}:")
        for idx, event in schedule.iterrows():
            print(f" - {event['EventName']} ({event['EventDate'].strftime('%Y-%m-%d')})")
        print("")  # Empty line for better readability
        return True
    except Exception as e:
        print(f"Error retrieving schedule for {year}: {str(e)}")
        return False

def main():
    # Use current year as default
    year = datetime.now().year
    
    # Ask for the year (with current year as default)
    year_input = input(f"Enter the year (default: {year}): ").strip()
    if year_input:
        year = int(year_input)
    
    # Show available events for the selected year
    check_fastf1_available_events(year)
    
    # Ask the user for Grand Prix name
    gp_name = input("Which Grand Prix do you want to process? (e.g. Australia, Japan): ")
    
    # Ask if it's a sprint weekend
    is_sprint = input("Is it a sprint weekend? (y/n): ").lower() == 'y'
    
    # Process the entire race weekend
    process_race_weekend(year, gp_name, is_sprint)
    
    print(f"✅ Completed processing {gp_name} GP {year}")

if __name__ == "__main__":
    main()
