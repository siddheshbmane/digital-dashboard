import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.data_processing import load_lead_data, merge_api_and_leads, get_platform_comparison
from utils.currency import format_currency
from utils.data_loader import load_client_data, filter_data
from datetime import datetime, timedelta

st.set_page_config(page_title="Platform Comparison", page_icon="📱", layout="wide")

st.title("📱 Platform Comparison")
st.markdown("Google Ads vs Meta (Facebook/Instagram) Ads.")

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
st.sidebar.header("Filters")
today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", (last_30_days, today))

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()

start_date, end_date = date_range

# Load Data
google_df, fb_df = load_client_data(client_id, start_date, end_date)
leads_df = load_lead_data(client_id)

# Merge
google_merged = merge_api_and_leads(google_df, leads_df)
fb_merged = merge_api_and_leads(fb_df, leads_df)
combined_df = pd.concat([google_merged, fb_merged], ignore_index=True)

if combined_df.empty:
    st.warning("No data available.")
    st.stop()

# --- Comparison Data ---
comp_data = get_platform_comparison(combined_df)
comp_data = comp_data.set_index('Source')

# Ensure both platforms exist in index for comparison
for platform in ['Google Ads', 'Facebook Ads']:
    if platform not in comp_data.index:
        comp_data.loc[platform] = 0

# --- Head-to-Head Metrics ---
st.subheader("Head-to-Head Comparison")

metrics = [
    ('Spend', 'Total Spend', True), # True = Higher is "more volume", but efficiency depends
    ('Conversions', 'Total Leads', True),
    ('CPA', 'Cost Per Lead', False), # False = Lower is better
    ('ConversionValue', 'Revenue', True)
]

for metric, label, higher_is_better in metrics:
    g_val = comp_data.loc['Google Ads', metric]
    f_val = comp_data.loc['Facebook Ads', metric]
    
    diff = g_val - f_val
    pct_diff = (diff / f_val * 100) if f_val > 0 else 0
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        st.markdown(f"**{label}**")
    with col2:
        # Progress bar style comparison
        total = g_val + f_val
        if total > 0:
            g_pct = g_val / total
            st.progress(g_pct)
            st.caption(f"Google: {format_currency(g_val) if 'Spend' in metric or 'Value' in metric or 'CPA' in metric else int(g_val)} vs Meta: {format_currency(f_val) if 'Spend' in metric or 'Value' in metric or 'CPA' in metric else int(f_val)}")
    with col3:
        if diff > 0:
            st.success(f"Google +{pct_diff:.1f}%")
        elif diff < 0:
            st.info(f"Meta +{abs(pct_diff):.1f}%")
        else:
            st.text("Equal")

# --- Radar Chart (Efficiency) ---
st.subheader("Efficiency Score")

# Normalize metrics for radar chart (0-1 scale)
# We need to invert CPA so higher is better for the chart
categories = ['Lead Volume', 'Revenue', 'Cost Efficiency (1/CPA)', 'Conversion Rate']
# Calculate Conversion Rate manually as it might not be in comp_data
comp_data['Clicks'] = combined_df.groupby('Source')['Clicks'].sum()
comp_data['ConvRate'] = comp_data['Conversions'] / comp_data['Clicks']

g_cpa_inv = 1/comp_data.loc['Google Ads', 'CPA'] if comp_data.loc['Google Ads', 'CPA'] > 0 else 0
f_cpa_inv = 1/comp_data.loc['Facebook Ads', 'CPA'] if comp_data.loc['Facebook Ads', 'CPA'] > 0 else 0

# Simple normalization (max of the two becomes 1)
def norm(v1, v2):
    m = max(v1, v2)
    return (v1/m, v2/m) if m > 0 else (0, 0)

g_vol, f_vol = norm(comp_data.loc['Google Ads', 'Conversions'], comp_data.loc['Facebook Ads', 'Conversions'])
g_rev, f_rev = norm(comp_data.loc['Google Ads', 'ConversionValue'], comp_data.loc['Facebook Ads', 'ConversionValue'])
g_eff, f_eff = norm(g_cpa_inv, f_cpa_inv)
g_cr, f_cr = norm(comp_data.loc['Google Ads', 'ConvRate'], comp_data.loc['Facebook Ads', 'ConvRate'])

fig_radar = go.Figure()

fig_radar.add_trace(go.Scatterpolar(
    r=[g_vol, g_rev, g_eff, g_cr],
    theta=categories,
    fill='toself',
    name='Google Ads'
))
fig_radar.add_trace(go.Scatterpolar(
    r=[f_vol, f_rev, f_eff, f_cr],
    theta=categories,
    fill='toself',
    name='Meta Ads'
))

fig_radar.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 1]
        )),
    showlegend=True
)

st.plotly_chart(fig_radar, use_container_width=True)

# --- Detailed Table ---
st.subheader("Detailed Platform Metrics")
st.dataframe(comp_data.style.format({
    'Spend': lambda x: format_currency(x),
    'ConversionValue': lambda x: format_currency(x),
    'CPA': lambda x: format_currency(x),
    'ConvRate': '{:.2f}%'
}), use_container_width=True)
