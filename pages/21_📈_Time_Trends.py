import streamlit as st
import pandas as pd
import plotly.express as px
from utils.data_processing import load_lead_data, merge_api_and_leads, get_time_trends
from utils.currency import format_currency
from utils.data_loader import load_client_data, filter_data
from datetime import datetime, timedelta

st.set_page_config(page_title="Time Trends", page_icon="📈", layout="wide")

st.title("📈 Time-based Performance Trends")
st.markdown("Analyze how your metrics evolve over time.")

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

# --- Interval Selection ---
interval = st.sidebar.selectbox("Time Interval", ["Daily", "Weekly", "Monthly"])
interval_map = {"Daily": "D", "Weekly": "W", "Monthly": "M"}

# --- Trend Data ---
trend_data = get_time_trends(combined_df, interval=interval_map[interval])

# --- Charts ---
st.subheader(f"{interval} Spend & Leads Trend")
fig_combo = px.bar(trend_data, x='Period', y='Spend', title="Spend vs Leads", 
                   labels={'Spend': 'Spend (Bar)'}, color_discrete_sequence=['#6366f1'])
fig_combo.add_scatter(x=trend_data['Period'], y=trend_data['Conversions'], mode='lines+markers', 
                      name='Leads (Line)', yaxis='y2', line=dict(color='#10b981', width=3))

fig_combo.update_layout(
    yaxis=dict(title="Spend"),
    yaxis2=dict(title="Leads", overlaying='y', side='right'),
    hovermode='x unified'
)
st.plotly_chart(fig_combo, use_container_width=True)

# --- CPL Trend ---
st.subheader(f"{interval} CPL Trend")
fig_cpl = px.line(trend_data, x='Period', y='CPL', title="Cost Per Lead Trend", markers=True)
st.plotly_chart(fig_cpl, use_container_width=True)

# --- Day of Week Analysis ---
st.subheader("Day of Week Performance")
combined_df['DayOfWeek'] = pd.to_datetime(combined_df['Date']).dt.day_name()
# Order: Mon -> Sun
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_data = combined_df.groupby('DayOfWeek').agg({
    'Conversions': 'mean', # Average leads per day
    'CPA': 'mean'
}).reindex(days_order).reset_index()

c1, c2 = st.columns(2)
with c1:
    fig_dow_leads = px.bar(dow_data, x='DayOfWeek', y='Conversions', title="Avg Leads by Day of Week")
    st.plotly_chart(fig_dow_leads, use_container_width=True)

with c2:
    fig_dow_cpa = px.line(dow_data, x='DayOfWeek', y='CPA', title="Avg CPA by Day of Week", markers=True)
    st.plotly_chart(fig_dow_cpa, use_container_width=True)

# --- Detailed Table ---
st.subheader("Detailed Trend Data")
st.dataframe(trend_data.style.format({
    'Spend': lambda x: format_currency(x),
    'CPL': lambda x: format_currency(x),
    'CPQL': lambda x: format_currency(x),
    'ConversionValue': lambda x: format_currency(x)
}), use_container_width=True)
