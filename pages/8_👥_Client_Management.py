import streamlit as st
import pandas as pd
from utils.client_manager import load_clients, save_client, delete_client, toggle_client_status

st.set_page_config(page_title="Client Management", page_icon="👥", layout="wide")

st.title("👥 Client Management")
st.markdown("Manage your clients and their ad account configurations.")

# --- Session State for Edit Mode ---
if 'edit_client_id' not in st.session_state:
    st.session_state.edit_client_id = None

# --- Action Handler ---
def handle_save():
    name = st.session_state.form_name
    industry = st.session_state.form_industry
    google_id = st.session_state.form_google_id
    meta_id = st.session_state.form_meta_id
    status = st.session_state.form_status
    
    if not name:
        st.error("Client Name is required.")
        return

    client_data = {
        'id': st.session_state.edit_client_id,
        'name': name,
        'industry': industry,
        'google_id': google_id,
        'meta_id': meta_id,
        'status': status
    }
    
    save_client(client_data)
    st.success("Client saved successfully!")
    st.session_state.edit_client_id = None # Exit edit mode
    st.rerun()

def handle_edit(client):
    st.session_state.edit_client_id = client['id']
    st.rerun()

def handle_delete(client_id):
    delete_client(client_id)
    st.success("Client deleted.")
    st.rerun()

def handle_toggle(client_id):
    toggle_client_status(client_id)
    st.rerun()

def handle_cancel():
    st.session_state.edit_client_id = None
    st.rerun()

# --- List View ---
clients = load_clients()

if st.session_state.edit_client_id is None:
    # Show List
    st.subheader("Client List")
    
    if not clients:
        st.info("No clients found. Add one below.")
    else:
        # Create a dataframe for display
        display_data = []
        for c in clients:
            display_data.append({
                'Name': c['name'],
                'Industry': c.get('industry', ''),
                'Status': c.get('status', 'Active'),
                'Google ID': c.get('google_id', ''),
                'Meta ID': c.get('meta_id', ''),
                'ID': c['id']
            })
        
        df = pd.DataFrame(display_data)
        
        # Custom Table with Actions (Streamlit doesn't support buttons in dataframe easily, so we iterate)
        # Using columns for layout
        
        # Header
        h1, h2, h3, h4, h5, h6 = st.columns([2, 2, 1, 2, 2, 3])
        h1.markdown("**Name**")
        h2.markdown("**Industry**")
        h3.markdown("**Status**")
        h4.markdown("**Google ID**")
        h5.markdown("**Meta ID**")
        h6.markdown("**Actions**")
        st.markdown("---")
        
        for client in clients:
            c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 1, 2, 2, 3])
            c1.write(client['name'])
            c2.write(client.get('industry', ''))
            
            status = client.get('status', 'Active')
            status_color = "green" if status == "Active" else "red"
            c3.markdown(f":{status_color}[{status}]")
            
            c4.write(client.get('google_id', ''))
            c5.write(client.get('meta_id', ''))
            
            with c6:
                b1, b2, b3 = st.columns(3)
                if b1.button("Edit", key=f"edit_{client['id']}"):
                    handle_edit(client)
                
                btn_label = "Deactivate" if status == "Active" else "Activate"
                if b2.button(btn_label, key=f"toggle_{client['id']}"):
                    handle_toggle(client['id'])
                    
                if b3.button("Delete", key=f"del_{client['id']}"):
                    handle_delete(client['id'])
            st.markdown("---")

    if st.button("➕ Add New Client"):
        st.session_state.edit_client_id = "" # Empty string signals new client
        st.rerun()

# --- Add/Edit Form ---
else:
    # Determine if adding or editing
    is_new = st.session_state.edit_client_id == ""
    client_to_edit = {}
    if not is_new:
        client_to_edit = next((c for c in clients if c['id'] == st.session_state.edit_client_id), {})
    
    st.subheader("Add New Client" if is_new else "Edit Client")
    
    with st.form("client_form"):
        st.text_input("Client Name", value=client_to_edit.get('name', ''), key="form_name")
        st.text_input("Industry", value=client_to_edit.get('industry', ''), key="form_industry")
        
        c1, c2 = st.columns(2)
        c1.text_input("Google Ads Customer ID", value=client_to_edit.get('google_id', ''), key="form_google_id", help="The 10-digit Customer ID (e.g., 123-456-7890)")
        c2.text_input("Meta Ad Account ID", value=client_to_edit.get('meta_id', ''), key="form_meta_id", help="The Ad Account ID (e.g., act_123456789)")
        
        st.selectbox("Status", ["Active", "Inactive"], index=0 if client_to_edit.get('status', 'Active') == 'Active' else 1, key="form_status")
        
        b1, b2 = st.columns([1, 10])
        submitted = b1.form_submit_button("Save", on_click=handle_save)
        cancelled = b2.form_submit_button("Cancel", on_click=handle_cancel)
