import streamlit as st
import pandas as pd
from datetime import datetime
from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.config_manager import load_credentials

@st.cache_data(ttl=300)
def load_data(start_date, end_date, use_mock_data=False, google_creds=None, fb_creds=None):
    """
    Loads data from Google and Facebook connectors.
    """
    # Load credentials if not provided
    if google_creds is None or fb_creds is None:
        saved_creds = load_credentials()
        if google_creds is None:
            google_creds = saved_creds.get("google", {})
        if fb_creds is None:
            fb_creds = saved_creds.get("facebook", {})

    g_conn = GoogleAdsConnector(credentials=google_creds, use_mock=use_mock_data)
    fb_conn = FacebookAdsConnector(credentials=fb_creds, use_mock=use_mock_data)
    
    g_data = g_conn.get_data(start_date, end_date)
    fb_data = fb_conn.get_data(start_date, end_date)
    
    return g_data, fb_data

def filter_data(df, start_date, end_date):
    """
    Filters a DataFrame by a date range.
    Assumes 'Date' column exists.
    """
    if df.empty or 'Date' not in df.columns:
        return df
    
    # Ensure Date column is datetime
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Ensure start_date and end_date are datetime (or convert them)
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    mask = (df['Date'] >= start_date) & (df['Date'] <= end_date)
    return df.loc[mask]

def load_client_data(client_id, start_date, end_date):
    """
    Helper to load data for a specific client by ID.
    Fetches client details and overrides credentials.
    """
    from utils.client_manager import get_active_clients
    from utils.config_manager import load_credentials
    
    active_clients = get_active_clients()
    client = next((c for c in active_clients if c['id'] == client_id), None)
    
    if not client:
        return pd.DataFrame(), pd.DataFrame()
        
    # Load default credentials
    saved_creds = load_credentials()
    g_creds = saved_creds.get("google", {}).copy()
    f_creds = saved_creds.get("facebook", {}).copy()
    
    # Override with client specific IDs
    if client.get('google_id'):
        g_creds['customer_id'] = client['google_id']
    if client.get('meta_id'):
        f_creds['ad_account_id'] = client['meta_id']
        
    return load_data(start_date, end_date, use_mock_data=False, google_creds=g_creds, fb_creds=f_creds)
