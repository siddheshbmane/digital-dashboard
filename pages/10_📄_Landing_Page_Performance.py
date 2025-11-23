import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.auth_helper import render_client_selector, get_context_credentials

# Page Config
st.set_page_config(
    page_title="Landing Page Performance",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Landing Page Performance")
st.markdown("Analyze performance by Landing Page URL.")

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
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view detailed landing page performance.")
    st.stop()

# --- Data Fetching ---
@st.cache_data(ttl=300)
def load_lp_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    # Google: Get Ad Data (now includes Landing Page)
    g_data = g_conn.get_ad_data(start, end)
    
    # Meta: Get Ad Data + URL Map
    f_data = fb_conn.get_ad_data(start, end)
    f_urls = fb_conn.get_ad_urls()
    
    # Map URLs to Meta Data
    if not f_data.empty:
        # Map by Ad Name (or ID if we had it in the main df, we have Ad Name)
        f_data['Landing Page'] = f_data['Ad'].map(f_urls).fillna("Unknown")
    
    return g_data, f_data

with st.spinner("Fetching Landing Page Data..."):
    g_df, f_df = load_lp_data(start_date, end_date, use_mock_data, google_creds, fb_creds)

# --- Processing ---
# Combine Data
combined_df = pd.concat([g_df, f_df], ignore_index=True)

if combined_df.empty:
    st.warning("No data available.")
    st.stop()

# Filter out Unknown URLs
lp_df = combined_df[combined_df['Landing Page'] != "Unknown"]

if lp_df.empty:
    st.warning("No landing page data found. Ensure your ads have final URLs set.")
    st.stop()

# Group by Landing Page
lp_stats = lp_df.groupby('Landing Page').agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'ConversionValue': 'sum',
    'Clicks': 'sum',
    'Impressions': 'sum'
}).reset_index()

# Metrics
lp_stats['CPA'] = (lp_stats['Spend'] / lp_stats['Conversions']).replace([float('inf')], 0).fillna(0)
lp_stats['CPC'] = (lp_stats['Spend'] / lp_stats['Clicks']).replace([float('inf')], 0).fillna(0)
lp_stats['CTR'] = (lp_stats['Clicks'] / lp_stats['Impressions'] * 100).fillna(0)
lp_stats['Conv Rate'] = (lp_stats['Conversions'] / lp_stats['Clicks'] * 100).fillna(0)

# --- Visualizations ---

# 1. Top LPs by Spend
st.subheader("Top Landing Pages by Spend")
top_lp = lp_stats.sort_values(by='Spend', ascending=False).head(10)
fig_spend = px.bar(top_lp, x='Spend', y='Landing Page', orientation='h', title='Top 10 Landing Pages by Spend', text='Spend')
fig_spend.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_spend, use_container_width=True)

# 2. Scatter: Spend vs Conv Rate
st.subheader("Landing Page Efficiency Matrix")
if not lp_stats.empty:
    fig_scatter = px.scatter(
        lp_stats, 
        x='Conv Rate', 
        y='CPA', 
        size='Spend', 
        hover_name='Landing Page',
        title='Conversion Rate vs CPA (Size = Spend)'
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# 3. Detailed Table
st.subheader("Detailed Performance")
display_df = lp_stats.copy()
display_df['Spend'] = display_df['Spend'].map('₹{:,.2f}'.format)
display_df['Revenue'] = display_df['ConversionValue'].map('₹{:,.2f}'.format)
display_df['CPA'] = display_df['CPA'].map('₹{:,.2f}'.format)
display_df['CPC'] = display_df['CPC'].map('₹{:,.2f}'.format)
display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
display_df['Conv Rate'] = display_df['Conv Rate'].map('{:.2f}%'.format)

st.dataframe(display_df, use_container_width=True, hide_index=True)
