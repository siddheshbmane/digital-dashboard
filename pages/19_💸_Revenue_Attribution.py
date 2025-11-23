import streamlit as st
import pandas as pd
import plotly.express as px
from utils.data_processing import load_lead_data, merge_api_and_leads, get_revenue_timeline, get_platform_comparison
from utils.currency import format_currency
from utils.data_loader import load_client_data, filter_data
from datetime import datetime, timedelta

st.set_page_config(page_title="Revenue Attribution", page_icon="💸", layout="wide")

st.title("💸 Revenue Attribution")
st.markdown("Track revenue generation and ROI across channels.")

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

# --- Top Metrics ---
col1, col2, col3, col4 = st.columns(4)
total_rev = combined_df['ConversionValue'].sum() if 'ConversionValue' in combined_df.columns else 0
total_spend = combined_df['Spend'].sum()
roi = (total_rev - total_spend) / total_spend * 100 if total_spend > 0 else 0
avg_deal_size = total_rev / combined_df['Conversions'].sum() if combined_df['Conversions'].sum() > 0 else 0

with col1:
    st.metric("Total Revenue", format_currency(total_rev))

with col2:
    st.metric("Total Spend", format_currency(total_spend))

with col3:
    st.metric("ROI (ROAS)", f"{roi:.1f}%")

with col4:
    st.metric("Avg Deal Size", format_currency(avg_deal_size))

# --- Charts ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("Revenue by Source")
    source_data = get_platform_comparison(combined_df)
    if not source_data.empty:
        fig_source = px.pie(source_data, values='ConversionValue', names='Source', title="Revenue Share", hole=0.4)
        st.plotly_chart(fig_source, use_container_width=True)
    else:
        st.info("No revenue data by source.")

with c2:
    st.subheader("Cumulative Revenue Timeline")
    timeline_data = get_revenue_timeline(combined_df)
    if not timeline_data.empty:
        fig_time = px.area(timeline_data, x='Date', y='CumulativeRevenue', title="Cumulative Revenue Growth")
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("No timeline data available.")

# --- Top Campaigns by Revenue ---
st.subheader("Top Revenue Generating Campaigns")
camp_rev = combined_df.groupby('Campaign').agg({
    'ConversionValue': 'sum',
    'Spend': 'sum',
    'Conversions': 'sum'
}).reset_index().sort_values('ConversionValue', ascending=False).head(10)

camp_rev['ROI'] = (camp_rev['ConversionValue'] - camp_rev['Spend']) / camp_rev['Spend'] * 100
camp_rev['CPA'] = camp_rev['Spend'] / camp_rev['Conversions']

st.dataframe(camp_rev.style.format({
    'ConversionValue': lambda x: format_currency(x),
    'Spend': lambda x: format_currency(x),
    'CPA': lambda x: format_currency(x),
    'ROI': '{:.1f}%'
}), use_container_width=True)
