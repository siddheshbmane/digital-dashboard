import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.auth_helper import render_client_selector, get_context_credentials

# Page Config
st.set_page_config(
    page_title="Source Performance",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Source Performance Report")
st.markdown("Compare performance across Google (Search, Display, Video) and Meta (Facebook, Instagram).")

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
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view detailed source performance.")
    st.stop()

# --- Data Fetching ---
@st.cache_data(ttl=300)
def load_source_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    # Google: Get Campaign Data (contains 'Campaign Type')
    g_data = g_conn.get_data(start, end)
    
    # Meta: Get Platform Breakdown
    f_data = fb_conn.get_breakdown_data(start, end, breakdown='publisher_platform')
    
    return g_data, f_data

with st.spinner("Fetching Source Data..."):
    g_df, f_df = load_source_data(start_date, end_date, use_mock_data, google_creds, fb_creds)

# --- Processing ---
source_data = []

# Process Google Data
if not g_df.empty:
    # Group by Campaign Type
    g_grouped = g_df.groupby('Campaign Type').agg({
        'Spend': 'sum',
        'Conversions': 'sum',
        'ConversionValue': 'sum',
        'Clicks': 'sum',
        'Impressions': 'sum'
    }).reset_index()
    
    for _, row in g_grouped.iterrows():
        source_data.append({
            'Platform': 'Google Ads',
            'Source': f"Google - {row['Campaign Type']}",
            'Spend': row['Spend'],
            'Conversions': row['Conversions'],
            'Revenue': row['ConversionValue'],
            'Clicks': row['Clicks'],
            'Impressions': row['Impressions']
        })

# Process Meta Data
if not f_df.empty:
    # Group by Breakdown (Platform)
    f_grouped = f_df.groupby('Breakdown').agg({
        'Spend': 'sum',
        'Clicks': 'sum',
        'Impressions': 'sum'
    }).reset_index()
    
    # Note: Breakdown data usually doesn't have conversions/revenue in the same way unless we fetch it specifically.
    # The current get_breakdown_data only fetches spend/imps/clicks.
    # Limitation: We might miss conversion data for Meta split by platform here.
    # For now, we'll show Spend/Clicks/Imps.
    
    for _, row in f_grouped.iterrows():
        platform_name = row['Breakdown'].replace('_', ' ').title()
        source_data.append({
            'Platform': 'Meta Ads',
            'Source': f"Meta - {platform_name}",
            'Spend': row['Spend'],
            'Conversions': 0, # Placeholder as breakdown api didn't return it
            'Revenue': 0,
            'Clicks': row['Clicks'],
            'Impressions': row['Impressions']
        })

source_df = pd.DataFrame(source_data)

if source_df.empty:
    st.warning("No data available.")
    st.stop()

# Calculate Metrics
source_df['CPA'] = (source_df['Spend'] / source_df['Conversions']).replace([float('inf')], 0).fillna(0)
source_df['CPC'] = (source_df['Spend'] / source_df['Clicks']).replace([float('inf')], 0).fillna(0)
source_df['CTR'] = (source_df['Clicks'] / source_df['Impressions'] * 100).fillna(0)
source_df['ROAS'] = (source_df['Revenue'] / source_df['Spend']).replace([float('inf')], 0).fillna(0)

# --- Visualizations ---

# 1. Spend Distribution
col1, col2 = st.columns(2)
with col1:
    fig_spend = px.pie(source_df, values='Spend', names='Source', title='Spend Distribution by Source')
    st.plotly_chart(fig_spend, use_container_width=True)

with col2:
    # For conversions, filter out 0s (Meta breakdown limitation)
    conv_df = source_df[source_df['Conversions'] > 0]
    if not conv_df.empty:
        fig_conv = px.pie(conv_df, values='Conversions', names='Source', title='Conversion Distribution (Google Only)')
        st.plotly_chart(fig_conv, use_container_width=True)
    else:
        st.info("No conversion data available for distribution.")

# 2. Efficiency Comparison
st.subheader("Efficiency Comparison")
fig_eff = px.bar(source_df, x='Source', y=['CPC', 'CPA'], barmode='group', title='Cost Efficiency (CPC & CPA)')
st.plotly_chart(fig_eff, use_container_width=True)

# 3. Detailed Table
st.subheader("Detailed Performance")
display_df = source_df.copy()
display_df['Spend'] = display_df['Spend'].map('₹{:,.2f}'.format)
display_df['Revenue'] = display_df['Revenue'].map('₹{:,.2f}'.format)
display_df['CPA'] = display_df['CPA'].map('₹{:,.2f}'.format)
display_df['CPC'] = display_df['CPC'].map('₹{:,.2f}'.format)
display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
display_df['ROAS'] = display_df['ROAS'].map('{:.2f}x'.format)

st.dataframe(display_df, use_container_width=True, hide_index=True)
