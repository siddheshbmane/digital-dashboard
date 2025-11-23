import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.config_manager import load_credentials

# Page Config
st.set_page_config(
    page_title="Campaign Performance",
    page_icon="📢",
    layout="wide"
)

st.title("📢 Campaign Performance")
st.markdown("Drill down from Campaign to Ad Group/Ad Set level.")

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
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view detailed campaign performance.")
    st.stop()

@st.cache_data(ttl=300)
def load_granular_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    g_adgroups = g_conn.get_ad_group_data(start, end)
    f_adsets = fb_conn.get_ad_set_data(start, end)
    
    return g_adgroups, f_adsets

with st.spinner("Fetching granular data..."):
    g_df, f_df = load_granular_data(start_date, end_date, use_mock_data, google_creds, fb_creds)

# --- Tabs ---
tab_google, tab_facebook = st.tabs(["Google Ads (Ad Groups)", "Facebook Ads (Ad Sets)"])

def render_campaign_view(df, level_name):
    if df.empty:
        st.info(f"No data available for {level_name}.")
        return

    # Normalize column name
    if 'AdGroup' in df.columns:
        df['ChildLevel'] = df['AdGroup']
    elif 'AdSet' in df.columns:
        df['ChildLevel'] = df['AdSet']
    else:
        df['ChildLevel'] = "Unknown"

    # 1. Campaign Summary
    st.subheader("Campaign Overview")
    camp_summary = df.groupby(['Campaign']).agg({
        'Spend': 'sum',
        'Conversions': 'sum',
        'ConversionValue': 'sum',
        'Clicks': 'sum',
        'Impressions': 'sum'
    }).reset_index()

    camp_summary['ROI'] = ((camp_summary['ConversionValue'] - camp_summary['Spend']) / camp_summary['Spend'] * 100).fillna(0)
    camp_summary['CPA'] = (camp_summary['Spend'] / camp_summary['Conversions']).fillna(0)

    # Display as a selectable table
    selected_campaign = st.selectbox(f"Select a Campaign to Drill Down ({level_name})", options=["All"] + list(camp_summary['Campaign'].unique()))

    if selected_campaign != "All":
        filtered_df = df[df['Campaign'] == selected_campaign]
    else:
        filtered_df = df

    # 2. Child Level Performance
    st.subheader(f"{level_name} Performance {'(' + selected_campaign + ')' if selected_campaign != 'All' else ''}")

    child_summary = filtered_df.groupby(['ChildLevel', 'Campaign']).agg({
        'Spend': 'sum',
        'Conversions': 'sum',
        'ConversionValue': 'sum',
        'Clicks': 'sum',
        'Impressions': 'sum'
    }).reset_index()

    child_summary['CTR'] = (child_summary['Clicks'] / child_summary['Impressions'] * 100).fillna(0)
    child_summary['CPC'] = (child_summary['Spend'] / child_summary['Clicks']).fillna(0)
    child_summary['CPA'] = (child_summary['Spend'] / child_summary['Conversions']).fillna(0)
    child_summary['ROI'] = ((child_summary['ConversionValue'] - child_summary['Spend']) / child_summary['Spend'] * 100).fillna(0)

    # Formatting for display
    display_df = child_summary.copy()
    display_df['Spend'] = display_df['Spend'].map('₹{:,.2f}'.format)
    display_df['Revenue'] = display_df['ConversionValue'].map('₹{:,.2f}'.format)
    display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
    display_df['CPC'] = display_df['CPC'].map('₹{:,.2f}'.format)
    display_df['CPA'] = display_df['CPA'].map('₹{:,.2f}'.format)
    display_df['ROI'] = display_df['ROI'].map('{:.0f}%'.format)
    
    # Rename ChildLevel for display
    display_df = display_df.rename(columns={'ChildLevel': level_name})

    st.dataframe(
        display_df[[level_name, 'Campaign', 'Spend', 'Revenue', 'Conversions', 'CPA', 'ROI', 'CTR']],
        use_container_width=True,
        hide_index=True
    )

    # 3. Charts
    col1, col2 = st.columns(2)
    with col1:
        fig_spend = px.bar(child_summary, x='ChildLevel', y='Spend', title=f'Spend by {level_name}', color='Campaign')
        st.plotly_chart(fig_spend, use_container_width=True)

    with col2:
        fig_roi = px.bar(child_summary, x='ChildLevel', y='ROI', title=f'ROI % by {level_name}', color='Campaign')
        st.plotly_chart(fig_roi, use_container_width=True)

with tab_google:
    render_campaign_view(g_df, "Ad Group")

with tab_facebook:
    render_campaign_view(f_df, "Ad Set")
