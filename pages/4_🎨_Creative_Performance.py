import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.config_manager import load_credentials

# Page Config
st.set_page_config(
    page_title="Creative Performance",
    page_icon="🎨",
    layout="wide"
)

st.title("🎨 Creative Performance")
st.markdown("Analyze performance at the Ad/Creative level.")

# --- Config & Data ---
# --- Config & Data ---
st.sidebar.header("Configuration")

from utils.auth_helper import render_client_selector
render_client_selector()

use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

if len(date_range) != 2:
    st.stop()
start_date, end_date = date_range

from utils.auth_helper import get_context_credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view detailed creative performance.")
    st.stop()

@st.cache_data(ttl=300)
def load_ad_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    g_ads = g_conn.get_ad_data(start, end)
    f_ads = fb_conn.get_ad_data(start, end)
    
    return g_ads, f_ads

with st.spinner("Fetching creative data..."):
    g_df, f_df = load_ad_data(start_date, end_date, use_mock_data, google_creds, fb_creds)

# --- Tabs ---
tab_google, tab_facebook = st.tabs(["Google Ads", "Facebook Ads"])

def render_creative_view(df, platform_name):
    if df.empty:
        st.info(f"No creative data for {platform_name}.")
        return

    # --- Analysis ---
    st.subheader(f"Top Performing Creatives ({platform_name})")

    # Aggregate by Ad Name (Creative)
    creative_summary = df.groupby(['Ad', 'Campaign']).agg({
        'Spend': 'sum',
        'Conversions': 'sum',
        'ConversionValue': 'sum',
        'Clicks': 'sum',
        'Impressions': 'sum'
    }).reset_index()

    creative_summary['CTR'] = (creative_summary['Clicks'] / creative_summary['Impressions'] * 100).fillna(0)
    creative_summary['CPC'] = (creative_summary['Spend'] / creative_summary['Clicks']).fillna(0)
    creative_summary['CPA'] = (creative_summary['Spend'] / creative_summary['Conversions']).fillna(0)
    creative_summary['ROI'] = ((creative_summary['ConversionValue'] - creative_summary['Spend']) / creative_summary['Spend'] * 100).fillna(0)

    # Filter Options
    col1, col2 = st.columns(2)
    with col1:
        min_spend = st.number_input(f"Minimum Spend (₹) - {platform_name}", value=0, key=f"min_spend_{platform_name}")
    with col2:
        sort_by = st.selectbox(f"Sort By - {platform_name}", ["ROI", "Conversions", "CTR", "Spend"], index=0, key=f"sort_{platform_name}")

    filtered_creatives = creative_summary[creative_summary['Spend'] >= min_spend].sort_values(by=sort_by, ascending=False)

    # Display Table
    display_df = filtered_creatives.copy()
    display_df['Spend'] = display_df['Spend'].map('₹{:,.2f}'.format)
    display_df['Revenue'] = display_df['ConversionValue'].map('₹{:,.2f}'.format)
    display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
    display_df['CPC'] = display_df['CPC'].map('₹{:,.2f}'.format)
    display_df['CPA'] = display_df['CPA'].map('₹{:,.2f}'.format)
    display_df['ROI'] = display_df['ROI'].map('{:.0f}%'.format)

    st.dataframe(
        display_df[['Ad', 'Campaign', 'Spend', 'Revenue', 'Conversions', 'ROI', 'CTR', 'CPA']],
        use_container_width=True,
        hide_index=True
    )

    # --- Scatter Plot ---
    st.subheader(f"Creative Efficiency: CTR vs ROI ({platform_name})")
    if not filtered_creatives.empty:
        fig_scatter = px.scatter(
            filtered_creatives, 
            x='CTR', 
            y='ROI', 
            size='Spend', 
            hover_name='Ad',
            title=f'Creative Performance Matrix (Size = Spend) - {platform_name}'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("No data to plot.")

with tab_google:
    render_creative_view(g_df, "Google Ads")

with tab_facebook:
    render_creative_view(f_df, "Facebook Ads")
