import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.config_manager import load_credentials
from utils.data_processing import (
    load_lead_data,
    merge_api_and_leads
)

# Page Config
st.set_page_config(
    page_title="Lead Analysis",
    page_icon="🕵️",
    layout="wide"
)

st.title("🕵️ Lead Quality Analysis")
st.markdown("Analyze lead quality, cost-per-qualified-lead (CPQL), and identify your best performing campaigns.")

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
    st.info("Please select a start and end date.")
    st.stop()
start_date, end_date = date_range

from utils.auth_helper import get_context_credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view detailed lead analysis.")
    st.stop()

@st.cache_data(ttl=300)
def load_analysis_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    # We need granular data for matching
    g_data = g_conn.get_ad_group_data(start, end)
    f_data = fb_conn.get_ad_set_data(start, end)
    
    return g_data, f_data

with st.spinner("Fetching and Merging Data..."):
    if not use_mock_data and (not google_creds.get('developer_token') and not fb_creds.get('access_token')):
         st.warning("⚠️ No credentials found. Please go to 'Connections' or use Mock Data.")
         st.stop()
         
    g_df, f_df = load_analysis_data(start_date, end_date, use_mock_data, google_creds, fb_creds)
    
    # Load Leads
    client_id = st.session_state.get('selected_client_id')
    if client_id == "ALL": client_id = None
    
    lead_df = load_lead_data(client_id=client_id)
    
    if lead_df.empty and not use_mock_data:
         st.warning("⚠️ No lead data uploaded. Please go to 'Lead Upload' to add your lead sheet for quality analysis.")
         # We continue but metrics will be 0 or estimated if we fallback (but we want to emphasize real data here)
    
    # Merge
    if not lead_df.empty:
        g_df = merge_api_and_leads(g_df, lead_df)
        f_df = merge_api_and_leads(f_df, lead_df)
    else:
        # Initialize columns if no leads
        if not g_df.empty: g_df['Qualified Leads'] = 0
        if not f_df.empty: f_df['Qualified Leads'] = 0

    # Combine for Overview
    # Normalize columns
    if not g_df.empty:
        g_df['AdGroup/AdSet'] = g_df['AdGroup']
        g_df_clean = g_df.drop(columns=['AdGroup', 'AdGroup ID'], errors='ignore')
    else:
        g_df_clean = pd.DataFrame()

    if not f_df.empty:
        f_df['AdGroup/AdSet'] = f_df['AdSet']
        f_df_clean = f_df.drop(columns=['AdSet', 'AdSet ID'], errors='ignore')
    else:
        f_df_clean = pd.DataFrame()

    combined_df = pd.concat([g_df_clean, f_df_clean], ignore_index=True)

    if combined_df.empty:
        st.warning("No data available.")
        st.stop()

    # --- Debug Info ---
    with st.expander("🛠️ Debug: Data Merge Verification"):
        st.write("Check if IDs match between your API data and Lead Sheet.")
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.subheader("API Data Sample (IDs)")
            if not combined_df.empty:
                cols_to_show = ['Source', 'Campaign', 'Campaign ID']
                if 'AdGroup/AdSet' in combined_df.columns: cols_to_show.append('AdGroup/AdSet')
                # Try to find the ID cols
                if 'AdGroup ID' in g_df.columns: cols_to_show.append('AdGroup ID') # Note: merged df might have dropped it or renamed
                # Actually combined_df dropped them in the code above?
                # Let's look at g_df and f_df before concat
                st.write("Google Ads Sample:")
                if not g_df.empty: st.dataframe(g_df[['Campaign', 'Campaign ID', 'AdGroup', 'AdGroup ID']].head().astype(str))
                st.write("Facebook Ads Sample:")
                if not f_df.empty: st.dataframe(f_df[['Campaign', 'Campaign ID', 'AdSet', 'AdSet ID']].head().astype(str))
        
        with col_d2:
            st.subheader("Lead Sheet Sample (IDs)")
            if not lead_df.empty:
                st.dataframe(lead_df[['Campaign ID', 'Ad Group ID', 'Ad Set ID', 'Lead Stage', 'Is Qualified']].head().astype(str))
            else:
                st.write("No lead data loaded.")

# --- KPIs ---
st.subheader("Quality Overview")

total_spend = combined_df['Spend'].sum()
total_leads = combined_df['Conversions'].sum()
total_qualified = combined_df['Qualified Leads'].sum()

avg_cpl = (total_spend / total_leads) if total_leads > 0 else 0
avg_cpql = (total_spend / total_qualified) if total_qualified > 0 else 0
quality_rate = (total_qualified / total_leads * 100) if total_leads > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"₹{total_spend:,.0f}")
col2.metric("Total Leads", f"{total_leads:,.0f}")
col3.metric("Qualified Leads", f"{total_qualified:,.0f}", f"{quality_rate:.1f}% Quality Rate")
col4.metric("Avg CPQL", f"₹{avg_cpql:,.0f}", delta=f"CPL: ₹{avg_cpl:,.0f}", delta_color="off")

st.markdown("---")

# --- Visualizations ---

# 1. Platform Comparison
st.subheader("Platform Quality Battle")
platform_stats = combined_df.groupby('Source').agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum'
}).reset_index()

platform_stats['CPQL'] = (platform_stats['Spend'] / platform_stats['Qualified Leads']).replace([float('inf'), -float('inf')], 0).fillna(0)
platform_stats['Quality %'] = (platform_stats['Qualified Leads'] / platform_stats['Conversions'] * 100).fillna(0)

col_left, col_right = st.columns(2)

with col_left:
    fig_qual = px.bar(platform_stats, x='Source', y='Qualified Leads', title='Qualified Leads by Platform', color='Source')
    st.plotly_chart(fig_qual, use_container_width=True)

with col_right:
    fig_cpql = px.bar(platform_stats, x='Source', y='CPQL', title='Cost Per Qualified Lead (Lower is Better)', color='Source')
    st.plotly_chart(fig_cpql, use_container_width=True)

# 2. Campaign Leaderboard
st.markdown("---")
st.subheader("🏆 Campaign Quality Leaderboard")

camp_stats = combined_df.groupby(['Campaign', 'Source']).agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum'
}).reset_index()

camp_stats['CPQL'] = (camp_stats['Spend'] / camp_stats['Qualified Leads']).replace([float('inf'), -float('inf')], 0).fillna(0)
camp_stats['Quality %'] = (camp_stats['Qualified Leads'] / camp_stats['Conversions'] * 100).fillna(0)

# Filter out zero qualified leads for better chart
active_camps = camp_stats[camp_stats['Qualified Leads'] > 0].sort_values(by='Qualified Leads', ascending=False)

if not active_camps.empty:
    fig_camp = px.bar(active_camps, x='Qualified Leads', y='Campaign', orientation='h', color='Source', 
                      title='Top Campaigns by Qualified Leads', text='Qualified Leads')
    fig_camp.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_camp, use_container_width=True)
else:
    st.info("No campaigns with qualified leads found.")

# Table View
st.dataframe(
    camp_stats.sort_values(by='Qualified Leads', ascending=False).style.format({
        'Spend': '₹{:,.2f}',
        'CPQL': '₹{:,.2f}',
        'Quality %': '{:.1f}%'
    }),
    use_container_width=True
)

# 3. Efficiency Matrix (Ad Set Level)
st.markdown("---")
st.subheader("🎯 Ad Set Efficiency Matrix")
st.markdown("Identify 'Stars' (High Volume, Low Cost) and 'Cash Cows' (Low Cost, Moderate Volume).")

adset_stats = combined_df.groupby(['AdGroup/AdSet', 'Campaign', 'Source']).agg({
    'Spend': 'sum',
    'Qualified Leads': 'sum'
}).reset_index()

adset_stats['CPQL'] = (adset_stats['Spend'] / adset_stats['Qualified Leads']).replace([float('inf'), -float('inf')], 0).fillna(0)

# Filter for meaningful data
filtered_adsets = adset_stats[adset_stats['Qualified Leads'] > 0]

if not filtered_adsets.empty:
    fig_scatter = px.scatter(
        filtered_adsets,
        x='Qualified Leads',
        y='CPQL',
        size='Spend',
        color='Source',
        hover_name='AdGroup/AdSet',
        hover_data=['Campaign'],
        title='CPQL vs Qualified Volume (Size = Spend)'
    )
    # Invert Y axis because lower CPQL is better
    # fig_scatter.update_yaxes(autorange="reversed") 
    # Actually, standard scatter is fine, but user needs to know lower Y is better.
    
    st.plotly_chart(fig_scatter, use_container_width=True)
else:
    st.info("No ad sets with qualified leads to plot.")
