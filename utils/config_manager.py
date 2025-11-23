import json
import os
import streamlit as st

CREDENTIALS_FILE = "credentials.json"

def load_credentials():
    """
    Loads credentials from the local JSON file.
    Returns a dictionary of credentials or an empty dict if file doesn't exist.
    """
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Failed to load credentials: {e}")
            return {}
    return {}

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
