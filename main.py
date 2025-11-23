import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.data_processing import aggregate_data
from utils.config_manager import load_credentials, save_credentials

from utils.client_manager import get_active_clients
from utils.auth_helper import render_client_selector

# Page Configuration
st.set_page_config(
    page_title="Ads Reporting Dashboard",
    page_icon="📊",
    layout="wide"
)

# Title and Description
st.title("📊 Ads Reporting Dashboard")
st.markdown("Monitor your ad performance across Google and Facebook.")

# Sidebar - Configuration
st.sidebar.header("Configuration")

# --- Client Selection ---
render_client_selector()
# Check if "All Clients" is selected for local logic
is_all_clients = st.session_state.get('selected_client_id') == "ALL"

# Load active clients (needed for both single client and all clients modes)
active_clients = get_active_clients()

selected_client = None
if not is_all_clients and 'selected_client_id' in st.session_state:
    # We need selected_client object for the logic below (overriding creds manually in main.py for now, 
    # though we should switch to get_context_credentials eventually. 
    # For now, let's just re-fetch it to minimize changes to main.py logic structure)
    selected_client = next((c for c in active_clients if c['id'] == st.session_state.selected_client_id), None)

# Data Source Toggle
use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

# Date Filter
st.sidebar.subheader("Date Range")
today = datetime.today()
last_30_days = today - timedelta(days=30)

date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(last_30_days, today),
    max_value=today
)

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()

start_date, end_date = date_range

# Credentials Input (if not using mock data)
google_creds = {}
fb_creds = {}

# Load saved credentials
saved_creds = load_credentials()

# Fetch Data Function
from utils.data_loader import load_data

if not use_mock_data:
    # Check if we have valid config
    g_config = saved_creds.get("google", {})
    f_config = saved_creds.get("facebook", {})
    
    has_google = bool(g_config.get("refresh_token") and g_config.get("customer_id"))
    has_facebook = bool(f_config.get("access_token") and f_config.get("ad_account_id"))
    
    if not has_google and not has_facebook:
        st.warning("⚠️ No active connections found.")
        st.info("Please go to the **Connections** page to set up your ad accounts.")
        st.stop()
    
    if has_google:
        st.sidebar.success(f"✅ Google Ads Connected")
        google_creds = g_config
        
    if has_facebook:
        st.sidebar.success(f"✅ Facebook Ads Connected")
        fb_creds = f_config
        
    # Add a link/button to manage connections
    st.sidebar.page_link("pages/1_🔗_Connections.py", label="Manage Connections", icon="🔗")
    st.sidebar.page_link("pages/8_👥_Client_Management.py", label="Manage Clients", icon="👥")

# --- Main Logic ---
with st.spinner("Fetching data..."):
    if is_all_clients:
        # --- Master Summary Logic ---
        master_df = pd.DataFrame()
        
        progress_bar = st.progress(0)
        total_clients = len(active_clients)
        
        for i, client in enumerate(active_clients):
            # Override creds
            c_g_creds = google_creds.copy()
            c_f_creds = fb_creds.copy()
            
            if client.get('google_id'): c_g_creds['customer_id'] = client['google_id']
            if client.get('meta_id'): c_f_creds['ad_account_id'] = client['meta_id']
            
            g_df, f_df = load_data(start_date, end_date, use_mock_data, c_g_creds, c_f_creds)
            
            c_combined = aggregate_data(g_df, f_df)
            if not c_combined.empty:
                c_combined['Client Name'] = client['name']
                master_df = pd.concat([master_df, c_combined], ignore_index=True)
            
            progress_bar.progress((i + 1) / total_clients)
            
        progress_bar.empty()
        
        if master_df.empty:
             st.warning("No data found for any active clients.")
             st.stop()
             
        # --- Master Summary Dashboard ---
        st.header("🏢 Master Summary Dashboard")
        
        # KPIs
        m_spend = master_df['Spend'].sum()
        m_leads = master_df['Conversions'].sum()
        m_rev = master_df['ConversionValue'].sum() if 'ConversionValue' in master_df.columns else 0
        m_roi = ((m_rev - m_spend) / m_spend * 100) if m_spend > 0 else 0
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Spend (All Clients)", f"₹{m_spend:,.2f}")
        k2.metric("Total Leads", f"{m_leads:,.0f}")
        k3.metric("Total Revenue", f"₹{m_rev:,.2f}")
        k4.metric("Overall ROI", f"{m_roi:.2f}%")
        
        # Charts
        c1, c2 = st.columns(2)
        
        # Lead Volume by Client
        client_leads = master_df.groupby(['Client Name', 'Source'])['Conversions'].sum().reset_index()
        fig_leads = px.bar(client_leads, x='Client Name', y='Conversions', color='Source', title='Lead Volume by Client', barmode='group')
        c1.plotly_chart(fig_leads, use_container_width=True)
        
        # Cost Efficiency (CPL) by Client
        client_spend = master_df.groupby('Client Name').agg({'Spend': 'sum', 'Conversions': 'sum'}).reset_index()
        client_spend['CPL'] = client_spend['Spend'] / client_spend['Conversions']
        fig_cpl = px.bar(client_spend, x='Client Name', y='CPL', title='Cost Per Lead (CPL) by Client')
        c2.plotly_chart(fig_cpl, use_container_width=True)
        
        # Performance Table
        st.subheader("Client Performance Summary")
        perf_table = master_df.groupby('Client Name').agg({
            'Spend': 'sum',
            'Conversions': 'sum',
            'Clicks': 'sum',
            'Impressions': 'sum'
        }).reset_index()
        perf_table['CPL'] = perf_table['Spend'] / perf_table['Conversions']
        perf_table['CTR'] = perf_table['Clicks'] / perf_table['Impressions'] * 100
        
        st.dataframe(perf_table.style.format({'Spend': '₹{:,.2f}', 'CPL': '₹{:,.2f}', 'CTR': '{:.2f}%'}), use_container_width=True)

    else:
        # --- Single Client Logic (Existing) ---
        
        # Override with Client IDs if selected
        if selected_client:
            if selected_client.get('google_id'):
                google_creds['customer_id'] = selected_client['google_id']
            if selected_client.get('meta_id'):
                fb_creds['ad_account_id'] = selected_client['meta_id']

        google_df, fb_df = load_data(start_date, end_date, use_mock_data, google_creds, fb_creds)
        
        if google_df.empty and fb_df.empty:
            st.warning("No data found for the selected range/credentials.")
            st.stop()
            
        combined_df = aggregate_data(google_df, fb_df)
    
        # KPIs
        st.header("Key Performance Indicators")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_spend = combined_df['Spend'].sum()
        total_impressions = combined_df['Impressions'].sum()
        total_clicks = combined_df['Clicks'].sum()
        total_conversions = combined_df['Conversions'].sum()
        
        # Calculate aggregate rates
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
        avg_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
        
        kpi1.metric("Total Spend", f"₹{total_spend:,.2f}", delta_color="inverse")
        kpi2.metric("Impressions", f"{total_impressions:,.0f}")
        kpi3.metric("Clicks", f"{total_clicks:,.0f}", f"{avg_ctr:.2f}% CTR")
        kpi4.metric("Conversions", f"{total_conversions:,.0f}", f"₹{avg_cpa:.2f} CPA")
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["Overview", "Google Ads", "Facebook Ads"])
        
        with tab1:
            st.subheader("Performance Trends")
            
            # Aggregate by Date and Source
            daily_df = combined_df.groupby(['Date', 'Source']).sum(numeric_only=True).reset_index()
            
            # Recalculate rates for daily data
            daily_df['CTR'] = daily_df['Clicks'] / daily_df['Impressions'] * 100
            daily_df['CPC'] = daily_df['Spend'] / daily_df['Clicks']
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_spend = px.line(daily_df, x='Date', y='Spend', color='Source', title='Daily Spend Trend')
                st.plotly_chart(fig_spend, use_container_width=True)
                
                fig_ctr = px.line(daily_df, x='Date', y='CTR', color='Source', title='Click-Through Rate (CTR) %')
                st.plotly_chart(fig_ctr, use_container_width=True)
        
            with col2:
                fig_clicks = px.bar(daily_df, x='Date', y='Clicks', color='Source', title='Daily Clicks')
                st.plotly_chart(fig_clicks, use_container_width=True)
                
                fig_cpc = px.line(daily_df, x='Date', y='CPC', color='Source', title='Cost Per Click (CPC) ₹')
                st.plotly_chart(fig_cpc, use_container_width=True)
        
            st.subheader("Detailed Data")
            st.dataframe(combined_df, use_container_width=True)
        
        with tab2:
            st.subheader("Google Ads Performance")
            if not google_df.empty:
                st.dataframe(google_df, use_container_width=True)
                
                campaign_df = google_df.groupby('Campaign').sum(numeric_only=True).reset_index()
                col1, col2 = st.columns(2)
                with col1:
                    fig_camp = px.pie(campaign_df, values='Spend', names='Campaign', title='Spend by Campaign')
                    st.plotly_chart(fig_camp, use_container_width=True)
                with col2:
                    fig_conv = px.bar(campaign_df, x='Campaign', y='Conversions', title='Conversions by Campaign')
                    st.plotly_chart(fig_conv, use_container_width=True)
            else:
                st.info("No Google Ads data available.")
        
        with tab3:
            st.subheader("Facebook Ads Performance")
            if not fb_df.empty:
                st.dataframe(fb_df, use_container_width=True)
                
                campaign_df = fb_df.groupby('Campaign').sum(numeric_only=True).reset_index()
                col1, col2 = st.columns(2)
                with col1:
                    fig_camp = px.pie(campaign_df, values='Spend', names='Campaign', title='Spend by Campaign')
                    st.plotly_chart(fig_camp, use_container_width=True)
                with col2:
                    fig_conv = px.bar(campaign_df, x='Campaign', y='Conversions', title='Conversions by Campaign')
                    st.plotly_chart(fig_conv, use_container_width=True)
            else:
                st.info("No Facebook Ads data available.")
