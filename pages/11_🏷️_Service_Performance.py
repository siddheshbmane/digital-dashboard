import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.auth_helper import render_client_selector, get_context_credentials

# Page Config
st.set_page_config(
    page_title="Service Performance",
    page_icon="🏷️",
    layout="wide"
)

st.title("🏷️ Service/Product Performance")
st.markdown("Analyze performance by Service or Product (grouped by Campaign Name).")

# --- Sidebar ---
st.sidebar.header("Configuration")
render_client_selector()
use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

if len(date_range) != 2:
    st.stop()
start_date, end_date = date_range

# Load Credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view detailed service performance.")
    st.stop()

# --- Data Fetching ---
@st.cache_data(ttl=300)
def load_service_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    # Google: Get Campaign Data
    g_data = g_conn.get_data(start, end)
    
    # Meta: Get Campaign Data (using get_ad_set_data for granular or get_data for campaign)
    # get_data returns campaign level which is sufficient
    f_data = fb_conn.get_data(start, end)
    
    return g_data, f_data

with st.spinner("Fetching Service Data..."):
    g_df, f_df = load_service_data(start_date, end_date, use_mock_data, google_creds, fb_creds)

# --- Processing ---
# 1. Load Lead Data to get Service Mapping
from utils.data_processing import load_lead_data
client_id = st.session_state.get('selected_client_id')
if client_id == "ALL": client_id = None
lead_df = load_lead_data(client_id=client_id)

campaign_service_map = {}
if not lead_df.empty and 'Service' in lead_df.columns:
    # Create a map of Campaign ID -> Service
    # We take the most frequent Service for each Campaign ID to handle inconsistencies
    # Or just take the first one if simple
    
    # Group by Campaign ID and find mode of Service
    for cid, group in lead_df.groupby('Campaign ID'):
        if not group['Service'].empty:
            top_service = group['Service'].mode()[0]
            campaign_service_map[str(cid)] = top_service

# 2. Combine API Data
combined_df = pd.concat([g_df, f_df], ignore_index=True)

if combined_df.empty:
    st.warning("No data available.")
    st.stop()

# 3. Map Service
if campaign_service_map:
    # Ensure Campaign ID is string
    if 'Campaign ID' in combined_df.columns:
        combined_df['Campaign ID'] = combined_df['Campaign ID'].astype(str)
        combined_df['Service/Product'] = combined_df['Campaign ID'].map(campaign_service_map).fillna("Unassigned")
    else:
        # Fallback if no ID (shouldn't happen with our connectors)
        combined_df['Service/Product'] = "Unassigned"
else:
    # Fallback to Campaign Name if no mapping found
    st.info("No Service mapping found in Lead Data. Grouping by Campaign Name.")
    combined_df['Service/Product'] = combined_df['Campaign']

# Group by Service
service_stats = combined_df.groupby('Service/Product').agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'ConversionValue': 'sum',
    'Clicks': 'sum',
    'Impressions': 'sum'
}).reset_index()

# Metrics
service_stats['CPA'] = (service_stats['Spend'] / service_stats['Conversions']).replace([float('inf')], 0).fillna(0)
service_stats['CPC'] = (service_stats['Spend'] / service_stats['Clicks']).replace([float('inf')], 0).fillna(0)
service_stats['CTR'] = (service_stats['Clicks'] / service_stats['Impressions'] * 100).fillna(0)
service_stats['ROAS'] = (service_stats['ConversionValue'] / service_stats['Spend']).replace([float('inf')], 0).fillna(0)

# Sort by Spend
service_stats = service_stats.sort_values(by='Spend', ascending=False)

# --- Visualizations ---

# 1. Top Services by Spend vs Conversions
st.subheader("Top Services by Spend & Conversions")
fig_bar = px.bar(
    service_stats.head(10), 
    x='Service/Product', 
    y=['Spend', 'Conversions'], 
    barmode='group',
    title='Spend vs Conversions by Service',
    text_auto='.2s'
)
st.plotly_chart(fig_bar, use_container_width=True)

# 2. Spend Distribution (Treemap)
st.subheader("Spend Distribution")
fig_tree = px.treemap(
    service_stats, 
    path=['Service/Product'], 
    values='Spend',
    color='CPA',
    color_continuous_scale='RdBu_r',
    title='Spend Distribution (Color = CPA)'
)
st.plotly_chart(fig_tree, use_container_width=True)

# 3. Detailed Table
st.subheader("Detailed Performance")
display_df = service_stats.copy()
display_df['Spend'] = display_df['Spend'].map('₹{:,.2f}'.format)
display_df['Revenue'] = display_df['ConversionValue'].map('₹{:,.2f}'.format)
display_df['CPA'] = display_df['CPA'].map('₹{:,.2f}'.format)
display_df['CPC'] = display_df['CPC'].map('₹{:,.2f}'.format)
display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
display_df['ROAS'] = display_df['ROAS'].map('{:.2f}x'.format)

st.dataframe(display_df, use_container_width=True, hide_index=True)
