import json
import os
import uuid
import streamlit as st

CLIENTS_FILE = "clients.json"

def load_clients():
    """
    Loads clients from the JSON file.
    Returns a list of client dictionaries.
    """
    if not os.path.exists(CLIENTS_FILE):
        return []
    
    try:
        with open(CLIENTS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def save_client(client_data):
    """
    Saves a new client or updates an existing one.
    client_data: dict containing 'id', 'name', 'industry', 'status', 'google_id', 'meta_id'
    """
    clients = load_clients()
    
    if 'id' not in client_data or not client_data['id']:
        # New Client
        client_data['id'] = str(uuid.uuid4())
        clients.append(client_data)
    else:
        # Update Existing
        for i, client in enumerate(clients):
            if client['id'] == client_data['id']:
                clients[i] = client_data
                break
    
    with open(CLIENTS_FILE, 'w') as f:
        json.dump(clients, f, indent=4)
        
    return True

def delete_client(client_id):
    """
    Deletes a client by ID.
    """
    clients = load_clients()
    clients = [c for c in clients if c['id'] != client_id]
    
    with open(CLIENTS_FILE, 'w') as f:
        json.dump(clients, f, indent=4)
        
    return True

def toggle_client_status(client_id):
    """
    Toggles the status of a client (Active/Inactive).
    """
    clients = load_clients()
    for client in clients:
        if client['id'] == client_id:
            current_status = client.get('status', 'Active')
            client['status'] = 'Inactive' if current_status == 'Active' else 'Active'
            break
            
    with open(CLIENTS_FILE, 'w') as f:
        json.dump(clients, f, indent=4)
        
    return True

def get_active_clients():
    """
    Returns only active clients.
    """
    clients = load_clients()
    return [c for c in clients if c.get('status') == 'Active']

def update_client_config(client_id, config_updates):
    """
    Updates specific configuration fields for a client.
    config_updates: dict of key-value pairs to update.
    """
    clients = load_clients()
    updated = False
    
    for client in clients:
        if client['id'] == client_id:
            for key, value in config_updates.items():
                client[key] = value
            updated = True
            break
            
    if updated:
        with open(CLIENTS_FILE, 'w') as f:
            json.dump(clients, f, indent=4)
            
    return updated
