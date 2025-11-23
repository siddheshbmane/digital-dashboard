import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.data_processing import (
    aggregate_data, 
    get_funnel_data, 
    get_revenue_timeline, 
    get_platform_comparison, 
    get_hierarchical_campaign_data,
    load_lead_data,
    merge_api_and_leads
)
from utils.config_manager import load_credentials

# Page Config
st.set_page_config(
    page_title="Client Deep Dive",
    page_icon="📈",
    layout="wide"
)

# --- Header ---
st.title("📈 Client Deep-Dive Report")
st.markdown("Detailed performance analysis for selected client.")

# --- Sidebar & Data Loading ---
st.sidebar.header("Configuration")

from utils.auth_helper import render_client_selector
render_client_selector()

use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

# Date Range
today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
start_date, end_date = date_range

# Load Credentials
from utils.auth_helper import get_context_credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. This report is designed for deep-diving into a single client.")
    st.info("Please select a specific client from the sidebar to view this report.")
    st.stop()

# Fetch Data
@st.cache_data(ttl=300)
def load_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    # We need granular data (Ad Group / Ad Set) to match IDs
    g_data = g_conn.get_ad_group_data(start, end)
    f_data = fb_conn.get_ad_set_data(start, end)
    
    return g_data, f_data

with st.spinner("Fetching Client Data..."):
    if not use_mock_data and (not google_creds.get('developer_token') and not fb_creds.get('access_token')):
         st.warning("⚠️ No credentials found. Please go to 'Connections' or use Mock Data.")
         st.stop()
         
    google_df, fb_df = load_data(start_date, end_date, use_mock_data, google_creds, fb_creds)
    
    # Load and Merge Lead Data
    client_id = st.session_state.get('selected_client_id')
    if client_id == "ALL": client_id = None
    
    lead_df = load_lead_data(client_id=client_id)
    if not lead_df.empty:
        google_df = merge_api_and_leads(google_df, lead_df)
        fb_df = merge_api_and_leads(fb_df, lead_df)
        st.toast("Lead data merged successfully!", icon="✅")
    
    if google_df.empty and fb_df.empty:
        st.warning("No data found for the selected range.")
        st.stop()

# --- Tabs ---
tab_overview, tab_google, tab_facebook = st.tabs(["Overview", "Google Ads", "Facebook Ads"])

def render_dashboard(df, platform_name):
    if df.empty:
        st.info(f"No data for {platform_name}.")
        return

    # --- KPI Cards ---
    st.markdown(f"### {platform_name} KPIs")

    # Calculate KPIs
    total_spend = df['Spend'].sum()
    total_leads = df['Conversions'].sum()
    total_revenue = df['ConversionValue'].sum() if 'ConversionValue' in df.columns else 0
    
    if 'Qualified Leads' in df.columns:
        qualified_leads = df['Qualified Leads'].sum()
        ql_label = "Real Data"
    else:
        qualified_leads = int(total_leads * 0.765) # Estimated
        ql_label = "Est (76.5%)"

    avg_cpl = (total_spend / total_leads) if total_leads > 0 else 0
    avg_cpql = (total_spend / qualified_leads) if qualified_leads > 0 else 0
    roi = ((total_revenue - total_spend) / total_spend * 100) if total_spend > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Spend", f"₹{total_spend:,.0f}")
    col2.metric("Total Leads", f"{total_leads:,.0f}")
    col3.metric("Qualified Leads", f"{qualified_leads:,.0f}", ql_label)
    col4.metric("Revenue", f"₹{total_revenue:,.0f}", f"{roi:.0f}% ROI")

    col5, col6, col7 = st.columns(3)
    col5.metric("Avg CPL", f"₹{avg_cpl:,.0f}")
    col6.metric("Avg CPQL", f"₹{avg_cpql:,.0f}")
    col7.metric("Conversion Rate", f"{(total_leads/df['Clicks'].sum()*100):.2f}%" if df['Clicks'].sum() > 0 else "0%")

    st.markdown("---")

    # --- Charts ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Lead Stage Funnel")
        funnel_df = get_funnel_data(df)
        if not funnel_df.empty:
            fig_funnel = px.funnel(funnel_df, x='Value', y='Stage', title='Marketing Funnel')
            st.plotly_chart(fig_funnel, use_container_width=True)
        else:
            st.info("No data for funnel.")

    with col_right:
        st.subheader("Cumulative Revenue Timeline")
        rev_df = get_revenue_timeline(df)
        if not rev_df.empty:
            fig_rev = px.line(rev_df, x='Date', y='CumulativeRevenue', title='Cumulative Revenue Over Time', markers=True)
            fig_rev.update_layout(xaxis_title="Date", yaxis_title="Revenue (₹)")
            st.plotly_chart(fig_rev, use_container_width=True)
        else:
            st.info("No revenue data available.")

    # --- Campaign Table ---
    st.markdown("---")
    st.subheader("Campaign Performance")

    camp_data = get_hierarchical_campaign_data(df)
    if not camp_data.empty:
        # Format columns
        display_df = camp_data.copy()
        display_df['Spend'] = display_df['Spend'].map('₹{:,.2f}'.format)
        display_df['Revenue'] = display_df['ConversionValue'].map('₹{:,.2f}'.format)
        display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
        display_df['CPC'] = display_df['CPC'].map('₹{:,.2f}'.format)
        display_df['CPA'] = display_df['CPA'].map('₹{:,.2f}'.format)
        display_df['ROI'] = display_df['ROI'].map('{:.0f}%'.format)
        
        # Reorder columns
        cols = ['Campaign', 'Spend', 'Clicks', 'Impressions', 'CTR', 'Conversions', 'CPA', 'Revenue', 'ROI']
        st.dataframe(display_df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("No campaign data available.")

with tab_overview:
    combined_df = aggregate_data(google_df, fb_df)
    
    # Platform Comparison (Only in Overview)
    st.subheader("Platform Comparison")
    comp_df = get_platform_comparison(combined_df)
    if not comp_df.empty:
        fig_comp = px.bar(comp_df, x='Source', y=['Spend', 'ConversionValue'], barmode='group', title='Spend vs Revenue by Platform')
        st.plotly_chart(fig_comp, use_container_width=True)
    
    render_dashboard(combined_df, "Combined")

with tab_google:
    render_dashboard(google_df, "Google Ads")

with tab_facebook:
    render_dashboard(fb_df, "Facebook Ads")
