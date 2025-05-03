import streamlit as st
import os
import sys
import importlib.util
from notion_client import Client

# Streamlit UI Konfiguration
st.set_page_config(
    page_title="F1 Journal API Updater",
    page_icon="🏎️",
    layout="wide"
)

st.title("🏎️ F1 Journal API Integration")
st.write("Nutze dieses Tool, um dein F1 Journal in Notion automatisch mit API-Daten zu aktualisieren.")

# Funktion zum Laden deines F1-Skripts
def load_script(script_path):
    """Lädt dein bestehendes F1-Skript dynamisch"""
    try:
        # Dynamisches Laden des Moduls
        module_name = os.path.basename(script_path).replace('.py', '')
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        f1_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = f1_module
        spec.loader.exec_module(f1_module)
        return f1_module
    except Exception as e:
        st.error(f"Fehler beim Laden des Skripts: {e}")
        return None

# Notion API Setup
def connect_to_notion():
    """Verbindet sich mit der Notion API"""
    # Notion API Token aus den Umgebungsvariablen laden oder aus Streamlit Secrets
    notion_token = os.environ.get("NOTION_TOKEN") or st.secrets.get("NOTION_TOKEN", "")
    
    # Falls kein Token hinterlegt ist, Eingabefeld anzeigen
    if not notion_token:
        notion_token = st.text_input("Notion API Token eingeben:", type="password")
        if not notion_token:
            st.warning("Bitte gib deinen Notion API Token ein, um fortzufahren.")
            return None
    
    try:
        client = Client(auth=notion_token)
        return client
    except Exception as e:
        st.error(f"Fehler bei der Verbindung zu Notion: {e}")
        return None

# Seitenleiste für Einstellungen
with st.sidebar:
    st.header("Einstellungen")
    
    # Eingabe für Notion Datenbank ID
    database_id = st.text_input(
        "Notion Datenbank ID:",
        placeholder="Deine Notion Datenbank ID für das F1 Journal",
        help="Die ID findest du in der URL deiner Notion-Datenbank"
    )
    
    # Pfad zu deinem F1-Skript
    script_path = st.text_input(
        "Pfad zu deinem F1-Skript:",
        value="f1_api_script.py",  # Standardwert, den du ändern kannst
        help="Relativer oder absoluter Pfad zu deinem bestehenden F1-API-Skript"
    )
    
    # Lade das Skript
    if os.path.exists(script_path):
        st.success(f"Skript '{script_path}' gefunden!")
    else:
        st.warning(f"Skript '{script_path}' nicht gefunden. Bitte stelle sicher, dass der Pfad korrekt ist.")

# Hauptbereich der App
tab1, tab2 = st.tabs(["API Daten abrufen", "Einstellungen"])

with tab1:
    st.header("F1 API-Daten abrufen")
    
    # Parameter für die API-Abfrage
    col1, col2 = st.columns(2)
    
    with col1:
        saison = st.number_input("Saison:", min_value=2018, max_value=2030, value=2025)
        
    with col2:
        rennen_auswahl = st.selectbox(
            "Rennen auswählen:",
            options=["1 - Bahrain GP", "2 - Saudi Arabian GP", "3 - Australian GP", "4 - Japanese GP", "5 - Chinese GP", 
                    "6 - Miami GP", "7 - Emilia Romagna GP", "8 - Monaco GP", "9 - Canadian GP", "10 - Spanish GP"],
            index=0
        )
        rennen_nummer = int(rennen_auswahl.split(" - ")[0])
    
    # API-Aufruf und Notion-Update
    if st.button("Daten abrufen und Notion aktualisieren", type="primary"):
        # Nur ausführen, wenn Datenbankzugriff verfügbar ist
        notion = connect_to_notion()
        
        if notion and database_id:
            try:
                with st.spinner("Lade F1-Skript..."):
                    # Dein Skript dynamisch laden
                    f1_module = load_script(script_path)
                    
                    if f1_module:
                        # Parameter für dein Skript vorbereiten
                        params = {
                            "saison": saison,
                            "rennen": rennen_nummer,
                            "notion_client": notion,
                            "database_id": database_id
                        }
                        
                        # Hier wird angenommen, dass dein Skript eine Hauptfunktion hat
                        # Du musst diese Zeile entsprechend deinem Skriptaufbau anpassen
                        with st.spinner("API-Daten abrufen und Notion aktualisieren..."):
                            # Überprüfen, welche Funktionen im Modul verfügbar sind
                            available_functions = dir(f1_module)
                            st.write("Verfügbare Funktionen im Skript:", [f for f in available_functions if not f.startswith('_')])
                            
                            # Hier solltest du die passende Hauptfunktion deines Skripts aufrufen
                            # Beispiel (anzupassen!):
                            if hasattr(f1_module, 'update_notion_with_f1_data'):
                                result = f1_module.update_notion_with_f1_data(saison, rennen_nummer, notion, database_id)
                                st.success("Notion Journal erfolgreich aktualisiert!")
                                
                                # Ergebnisse anzeigen
                                st.subheader("Aktualisierte Daten")
                                st.json(result)
                            else:
                                st.error("Hauptfunktion konnte im Skript nicht gefunden werden.")
                                st.info("""
                                Bitte stelle sicher, dass dein Skript eine Hauptfunktion wie 'update_notion_with_f1_data(saison, rennen, notion_client, database_id)' 
                                enthält oder passe diesen Code entsprechend an.
                                """)
            except Exception as e:
                st.error(f"Fehler bei der Ausführung: {e}")
        else:
            st.warning("Bitte gib eine gültige Notion Datenbank ID ein und stelle eine Verbindung her.")

with tab2:
    st.header("Anpassung deines F1-Skripts")
    
    st.markdown("""
    ### So passt du dein bestehendes Skript an
    
    Damit dein F1-API-Skript mit dieser Streamlit-App funktioniert, stelle sicher, dass es:
    
    1. Eine Hauptfunktion hat, die folgende Parameter akzeptiert:
       - `saison`: Die Formel-1-Saison (z.B. 2025)
       - `rennen`: Die Rennnummer (z.B. 1 für den ersten Grand Prix)
       - `notion_client`: Eine Instanz des Notion-Clients
       - `database_id`: Die ID deiner Notion-Datenbank
    
    2. Keine hartcodierten Pfade oder Abhängigkeiten enthält, die auf deinem lokalen System spezifisch sind
    
    3. Alle notwendigen Abhängigkeiten importiert
    
    **Beispiel für die Anpassung deines Skripts:**
    """)
    
    st.code('''
    # Ursprünglicher Code:
    def update_f1_journal():
        # Hartcodierte Werte
        saison = 2025
        rennen = 1
        notion_token = "secret_..."
        database_id = "..."
        
        # API-Aufruf und Notion-Update
        ...
    
    # Angepasster Code:
    def update_notion_with_f1_data(saison, rennen, notion_client, database_id):
        # API-Aufruf
        race_data = get_race_data(saison, rennen)
        
        # Notion-Update
        result = update_notion(notion_client, database_id, race_data)
        
        return result
    
    def get_race_data(saison, rennen):
        # Deine API-Logik hier
        ...
        
    def update_notion(notion_client, database_id, race_data):
        # Deine Notion-Update-Logik hier
        ...
    ''', language="python")
    
    st.markdown("""
    ### Deployment-Hinweise
    
    Um deine App für den Zugriff von überall zu deployen:

    1. Lade den Code und dein F1-Skript auf GitHub hoch
    2. Erstelle ein kostenloses Konto auf [Streamlit Cloud](https://streamlit.io/cloud)
    3. Verbinde dein GitHub-Repository mit Streamlit Cloud
    4. Füge deinen Notion API Token als Geheimnis in Streamlit Cloud hinzu
    """)

# Footer
st.divider()
st.caption("F1 Journal API Updater • Erstellt mit Streamlit")
