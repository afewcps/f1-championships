import streamlit as st
import fastf1
import pandas as pd
import requests
import json
import traceback
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="F1 Results to Notion",
    page_icon="🏎️",
    layout="wide"
)

# Add header
st.title("🏎️ F1 Results to Notion")
st.markdown("Upload F1 session results directly to your Notion database.")
st.info("Important: This app will only update existing databases in Notion with the pattern '(GP Land) GP Year'. You must first duplicate the Results database template before using this app.")

# Notion API Configuration
notion_token = st.sidebar.text_input("Notion Token", value="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", type="password")
notion_f1_results_block_id = st.sidebar.text_input("Notion F1 Results Block ID", value="1e26839379ed80edbd00df2aaf120777")

# Cache configuration for FastF1
#cache_location = st.sidebar.text_input("FastF1 Cache Location", value="./fastf1_cache/")
#fastf1.Cache.enable_cache(cache_location)

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

def find_gp_database(gp_name, year, headers):
    """Find a GP database by name using the pattern '(GP Land) GP Year'."""
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
            if result.get("object") == "database":
                db_title = result.get("title", [{}])[0].get("text", {}).get("content", "")
                expected_title = f"({gp_name}) GP {year}"
                
                if expected_title in db_title:
                    st.success(f"Found existing database: {db_title}")
                    return result["id"]
    
    return None

def create_gp_database(gp_name, year, headers, block_id):
    """Function is now deprecated as we should only use existing databases."""
    st.error("Dupliziere zuerst die Results Datenbank")
    st.stop()  # This will halt the execution of the Streamlit app
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
            st.warning(f"Session {display_name} does not exist for {gp_name} GP {year}: {str(e)}")
            return None
            
        # Check if session has data before loading
        try:
            session.load()
        except Exception as e:
            st.warning(f"Could not load data for {display_name}: {str(e)}")
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
        st.error(f"Error processing {display_name}: {str(e)}")
        return None

def save_session_to_notion(database_id, session_data, is_sprint_weekend, headers):
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
        st.error(f"Failed to query database: {response.status_code}")
        st.code(response.text)
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
            st.success(f"Updated {session_name} in Notion")
        else:
            st.error(f"Failed to update {session_name}: {response.status_code}")
            st.code(response.text)
    else:
        # Create new page in the database
        create_url = "https://api.notion.com/v1/pages"
        create_data = {
            "parent": {"database_id": database_id},
            "properties": properties
        }
        
        response = requests.post(create_url, headers=headers, json=create_data)
        
        if response.status_code == 200:
            st.success(f"Created new entry for {session_name}")
        else:
            st.error(f"Failed to create entry for {session_name}: {response.status_code}")
            st.code(response.text)

def process_race_weekend(year, gp_name, is_sprint_weekend, headers, block_id):
    """Process all sessions for a race weekend."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text(f"Searching for database with pattern: ({gp_name}) GP {year}...")
    # Try to find an existing database for this GP with specific pattern
    gp_database_id = find_gp_database(gp_name, year, headers)
    
    # If not found, stop execution
    if not gp_database_id:
        status_text.text(f"No existing database found for ({gp_name}) GP {year}.")
        st.error("Dupliziere zuerst die Results Datenbank")
        st.stop()  # This will halt the execution of the Streamlit app
    
    progress_bar.progress(10)
    
    # Check if this is a future event
    current_date = datetime.now()
    if year > current_date.year:
        st.warning(f"{gp_name} GP {year} is in the future - data may be limited or unavailable")
    elif year == current_date.year:
        st.info(f"Processing current year's event: {gp_name} GP {year}. Some sessions may not have occurred yet.")
    
    # Define session types based on weekend type
    if is_sprint_weekend:
        session_types = ['FP1', 'SQ', 'S', 'FP2', 'Q', 'R']
    else:
        session_types = ['FP1', 'FP2', 'FP3', 'Q', 'R']
    
    # Calculate progress increment
    progress_increment = 90 / len(session_types)
    current_progress = 10
    
    # Process each session
    for session_type in session_types:
        try:
            status_text.text(f"Processing {gp_name} {session_type}...")
            session_data = get_results_for_session(year, gp_name, session_type)
            if session_data:
                save_session_to_notion(gp_database_id, session_data, is_sprint_weekend, headers)
            else:
                st.info(f"No data available for {gp_name} {session_type}")
        except Exception as e:
            st.error(f"Error with {session_type}: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
        
        # Update progress
        current_progress += progress_increment
        progress_bar.progress(int(current_progress))
    
    progress_bar.progress(100)
    status_text.text(f"✅ Completed processing {gp_name} GP {year}")
    st.balloons()

def get_available_events(year):
    """Get available events for the selected year."""
    try:
        # Get the schedule for the year
        schedule = fastf1.get_event_schedule(year)
        return schedule
    except Exception as e:
        st.error(f"Error retrieving schedule for {year}: {str(e)}")
        return pd.DataFrame()

def main():
    # Year selection
    current_year = datetime.now().year
    year = st.selectbox("Select Season", 
                        options=list(range(2018, 2026)),  # F1 data available from 2018
                        index=list(range(2018, 2026)).index(2025))  # Default to 2025
    
    # Get available events for the selected year
    with st.spinner(f"Loading events for {year}..."):
        events_df = get_available_events(year)
    
    if not events_df.empty:
        # Extract event names for the dropdown
        event_names = events_df['EventName'].tolist()
        
        # Create two columns
        col1, col2 = st.columns(2)
        
        with col1:
            # Grand Prix selection
            gp_name = st.selectbox("Select Grand Prix", 
                                   options=event_names,
                                   index=0)
            
        with col2:
            # Sprint weekend selection
            is_sprint = st.checkbox("Sprint Weekend Format", value=False)
        
        # Notion headers
        headers = {
            "Authorization": f"Bearer {notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # Process button
        if st.button("Process Race Weekend", type="primary"):
            with st.spinner(f"Processing {gp_name} GP {year}..."):
                process_race_weekend(year, gp_name, is_sprint, headers, notion_f1_results_block_id)
    else:
        st.warning(f"No events found for {year} or unable to fetch events.")

if __name__ == "__main__":
    main()
