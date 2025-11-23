import json
import os
import streamlit as st

CREDENTIALS_FILE = "credentials.json"

def load_credentials():
    """
    Loads credentials from st.secrets (priority) and local JSON file.
    Returns a dictionary of credentials.
    """
    creds = {}
    
    # 1. Load from Streamlit Secrets (Cloud/Production)
    # We convert to dict to ensure it's mutable and standard
    if "google" in st.secrets:
        creds["google"] = dict(st.secrets["google"])
    if "facebook" in st.secrets:
        creds["facebook"] = dict(st.secrets["facebook"])
        
    # 2. Load from local file (Local Dev) and merge
    # Local file values will override secrets if they exist (useful for local dev iterations)
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                file_creds = json.load(f)
                for key, val in file_creds.items():
                    if key not in creds:
                        creds[key] = val
                    else:
                        # Update existing keys (e.g. merge google settings)
                        if isinstance(val, dict) and isinstance(creds[key], dict):
                            creds[key].update(val)
                        else:
                            creds[key] = val
        except Exception as e:
            st.error(f"Failed to load local credentials: {e}")
            
    return creds

def save_credentials(credentials):
    """
    Saves the provided credentials dictionary to a local JSON file.
    """
    try:
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(credentials, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Failed to save credentials: {e}")
        return False
