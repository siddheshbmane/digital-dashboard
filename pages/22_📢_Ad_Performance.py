import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from utils.data_processing import load_lead_data, merge_api_and_leads, get_ad_performance_data
from utils.currency import format_currency
from utils.data_loader import load_client_data, filter_data
from datetime import datetime, timedelta

st.set_page_config(page_title="Ad Performance", page_icon="📢", layout="wide")

st.title("📢 Individual Ad Performance")
st.markdown("Analyze performance metrics for individual ads.")

# --- Data Loading ---
# --- Sidebar Filters ---
st.sidebar.header("Configuration")

from utils.auth_helper import render_client_selector
render_client_selector()

if st.session_state.get('selected_client_id') == "ALL":
    st.warning("Please select a specific client to view this report.")
    st.stop()

client_id = st.session_state['selected_client_id']

# --- Date Filter ---
today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", (last_30_days, today))

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()

start_date, end_date = date_range

# --- Data Loading (Granular) ---
from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.auth_helper import get_context_credentials

google_creds, fb_creds, _ = get_context_credentials()
use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

@st.cache_data(ttl=300)
def load_ad_level_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    g_data = g_conn.get_ad_data(start, end)
    f_data = fb_conn.get_ad_data(start, end)
    
    return g_data, f_data

with st.spinner("Fetching Ad-level data..."):
    google_df, fb_df = load_ad_level_data(start_date, end_date, use_mock_data, google_creds, fb_creds)
    leads_df = load_lead_data(client_id)

    # --- Debug Info ---
    with st.expander("Debug Info (Click to Expand)", expanded=False):
        st.write(f"**Selected Client ID:** {client_id}")
        st.write(f"**Google Customer ID:** {google_creds.get('customer_id')}")
        st.write(f"**Facebook Account ID:** {fb_creds.get('ad_account_id')}")
        st.write(f"**Google Rows Fetched:** {len(google_df)}")
        st.write(f"**Facebook Rows Fetched:** {len(fb_df)}")
        if not google_df.empty:
            st.write("Google Columns:", google_df.columns.tolist())
            st.dataframe(google_df.head())
        if not fb_df.empty:
            st.write("Facebook Columns:", fb_df.columns.tolist())
            st.dataframe(fb_df.head())

# Merge
# Note: merge_api_and_leads logic might need adjustment if it expects 'Ad Group ID' or 'Ad Set ID'
# get_ad_data returns 'AdGroup' name but maybe not ID in all mock cases? 
# Let's check connectors. Google get_ad_data returns AdGroup name.
# We might need to ensure merge works. For now, let's try standard merge.
google_merged = merge_api_and_leads(google_df, leads_df)
fb_merged = merge_api_and_leads(fb_df, leads_df)
combined_df = pd.concat([google_merged, fb_merged], ignore_index=True)

# --- Ad Data ---
ad_data = get_ad_performance_data(combined_df)

if ad_data.empty:
    st.warning("No Ad-level data available. Ensure your data includes 'Ad Name' or 'Ad ID'.")
    st.stop()

# --- Performance Score Calculation ---
# Simple Score: (Leads * 0.4) + (ROI * 0.3) + (CTR * 10 * 0.3) normalized?
# Let's just use a simple weighted rank for now
# Normalize columns
if not ad_data.empty:
    max_leads = ad_data['Conversions'].max()
    max_roi = ad_data['ROI'].max()
    min_cpl = ad_data[ad_data['CPL'] > 0]['CPL'].min()
    
    # Avoid division by zero
    max_leads = 1 if max_leads == 0 else max_leads
    max_roi = 1 if max_roi == 0 else max_roi
    min_cpl = 1 if pd.isna(min_cpl) or min_cpl == 0 else min_cpl

    # Score = (Leads/MaxLeads * 40) + (ROI/MaxROI * 30) + (MinCPL/CPL * 30)
    ad_data['Score'] = (
        (ad_data['Conversions'] / max_leads * 40) +
        (ad_data['ROI'] / max_roi * 30) +
        (np.where(ad_data['CPL'] > 0, min_cpl / ad_data['CPL'], 0) * 30)
    ).fillna(0).astype(int)

# --- Top Ads Cards ---
st.subheader("Top 5 Performing Ads")
top_ads = ad_data.sort_values('Score', ascending=False).head(5)

cols = st.columns(len(top_ads)) if len(top_ads) > 0 else []
for i, (index, row) in enumerate(top_ads.iterrows()):
    with cols[i]:
        st.markdown(f"### #{i+1} {row.name if row.name else 'Ad'}") # row.name is the index (Ad Name)
        st.metric("Score", f"{row['Score']}/100")
        st.caption(f"Leads: {int(row['Conversions'])}")
        st.caption(f"CPL: {format_currency(row['CPL'])}")
        st.caption(f"ROI: {row['ROI']:.1f}%")

# --- Charts ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("Top Ads by Leads")
    fig_leads = px.bar(top_ads, x='Conversions', y=top_ads.index, orientation='h', title="Leads Generated")
    st.plotly_chart(fig_leads, use_container_width=True)

with c2:
    st.subheader("ROI vs CPL")
    fig_scatter = px.scatter(ad_data, x='CPL', y='ROI', size='Conversions', hover_name=ad_data.index,
                             title="ROI vs CPL (Size = Leads)")
    st.plotly_chart(fig_scatter, use_container_width=True)

# --- Detailed Table ---
st.subheader("All Ads Performance")
st.dataframe(ad_data.style.format({
    'Spend': lambda x: format_currency(x),
    'CPL': lambda x: format_currency(x),
    'ROI': '{:.1f}%',
    'CTR': '{:.2f}%'
}), use_container_width=True)
