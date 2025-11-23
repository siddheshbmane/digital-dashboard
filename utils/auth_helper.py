import streamlit as st
from utils.config_manager import load_credentials
from utils.client_manager import get_active_clients

def _on_client_change(key):
    """Callback to update client ID when selection changes"""
    active_clients = get_active_clients()
    selected_name = st.session_state[key]
    
    if selected_name == "All Clients":
        st.session_state.selected_client_id = "ALL"
    else:
        selected_client = next((c for c in active_clients if c['name'] == selected_name), None)
        if selected_client:
            st.session_state.selected_client_id = selected_client['id']

def render_client_selector(key_suffix=""):
    """
    Renders the client selector in the sidebar and updates session state.
    Should be called at the top of the sidebar in every page.
    key_suffix: Optional suffix for the widget key to allow multiple selectors.
    """
    active_clients = get_active_clients()
    
    if active_clients:
        client_names = ["All Clients"] + [c['name'] for c in active_clients]
        
        # Initialize selected_client_id if not present
        if 'selected_client_id' not in st.session_state:
            st.session_state.selected_client_id = "ALL"
        
        # Find current selection index
        index = 0
        if st.session_state.selected_client_id == "ALL":
            index = 0
        else:
            for i, c in enumerate(active_clients):
                if c['id'] == st.session_state.selected_client_id:
                    index = i + 1  # +1 because of "All Clients"
                    break
        
        # Render selectbox with on_change callback
        widget_key = f"client_selector{key_suffix}"
        st.selectbox(
            "Select Client", 
            client_names, 
            index=index,
            key=widget_key,
            on_change=_on_client_change,
            args=(widget_key,)
        )
        
        # Show industry caption if specific client selected
        if st.session_state.selected_client_id != "ALL":
            selected_client = next((c for c in active_clients if c['id'] == st.session_state.selected_client_id), None)
            if selected_client:
                st.sidebar.caption(f"Industry: {selected_client.get('industry', 'N/A')}")
    else:
        st.sidebar.info("No active clients. Using default credentials.")

def get_context_credentials():
    """
    Loads credentials and applies the selected client context from session state.
    Returns:
        google_creds (dict): Google Ads credentials.
        fb_creds (dict): Facebook Ads credentials.
        is_all_clients (bool): True if "All Clients" is selected.
    """
    saved_creds = load_credentials()
    google_creds = saved_creds.get("google", {})
    fb_creds = saved_creds.get("facebook", {})
    is_all_clients = False
    
    # Check Session State for Client Selection
    if 'selected_client_id' in st.session_state:
        client_id = st.session_state.selected_client_id
        
        if client_id == "ALL":
            is_all_clients = True
        else:
            # Find the client details
            active_clients = get_active_clients()
            selected_client = next((c for c in active_clients if c['id'] == client_id), None)
            
            if selected_client:
                # Override IDs
                if selected_client.get('google_id'):
                    google_creds['customer_id'] = selected_client['google_id']
                if selected_client.get('meta_id'):
                    fb_creds['ad_account_id'] = selected_client['meta_id']
                    
    return google_creds, fb_creds, is_all_clients
