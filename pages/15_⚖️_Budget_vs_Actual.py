import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.data_processing import load_lead_data, merge_api_and_leads, get_hierarchical_campaign_data
from utils.currency import format_currency, get_currency_symbol
from utils.data_loader import load_client_data, filter_data
from datetime import datetime, timedelta

st.set_page_config(page_title="Budget vs Actual", page_icon="⚖️", layout="wide")

st.title("⚖️ Budget vs Actual Analysis")
st.markdown("Track your ad spend against your allocated budget.")

# --- Data Loading ---
# --- Sidebar Filters ---
st.sidebar.header("Configuration")

from utils.auth_helper import render_client_selector
render_client_selector()

if st.session_state.get('selected_client_id') == "ALL":
    st.warning("Please select a specific client to view this report.")
    st.stop()

client_id = st.session_state['selected_client_id']

# --- Sidebar Filters ---
st.sidebar.header("Configuration")
total_budget = st.sidebar.number_input("Total Monthly Budget", min_value=0.0, value=500000.0, step=10000.0, format="%.2f")

st.sidebar.subheader("Date Range")
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

# --- Metrics Calculation ---
total_spend = combined_df['Spend'].sum()
remaining_budget = total_budget - total_spend
utilization = (total_spend / total_budget * 100) if total_budget > 0 else 0
burn_rate = total_spend / len(pd.to_datetime(combined_df['Date']).unique()) if not combined_df.empty else 0

# --- KPI Cards ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Budget", format_currency(total_budget))

with col2:
    st.metric("Actual Spend", format_currency(total_spend), delta=f"{utilization:.1f}% Used", delta_color="off")

with col3:
    st.metric("Remaining Budget", format_currency(remaining_budget), delta=f"{100-utilization:.1f}% Left")

with col4:
    st.metric("Daily Burn Rate", format_currency(burn_rate))

# --- Charts ---

# 1. Budget Utilization Gauge
fig_gauge = go.Figure(go.Indicator(
    mode = "gauge+number+delta",
    value = total_spend,
    domain = {'x': [0, 1], 'y': [0, 1]},
    title = {'text': "Budget Utilization"},
    delta = {'reference': total_budget, 'increasing': {'color': "red"}},
    gauge = {
        'axis': {'range': [None, total_budget * 1.2], 'tickwidth': 1, 'tickcolor': "darkblue"},
        'bar': {'color': "#6366f1"},
        'bgcolor': "white",
        'borderwidth': 2,
        'bordercolor': "gray",
        'steps': [
            {'range': [0, total_budget * 0.8], 'color': "#d1fae5"}, # Greenish
            {'range': [total_budget * 0.8, total_budget], 'color': "#fef3c7"}, # Yellowish
            {'range': [total_budget, total_budget * 1.2], 'color': "#fee2e2"} # Reddish
        ],
        'threshold': {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': total_budget
        }
    }
))

# 2. Daily Spend Trend
daily_spend = combined_df.groupby('Date')['Spend'].sum().reset_index()
fig_trend = px.line(daily_spend, x='Date', y='Spend', title='Daily Spend Trend', markers=True)
fig_trend.add_hline(y=burn_rate, line_dash="dash", annotation_text="Avg Burn Rate", annotation_position="top left")

c1, c2 = st.columns(2)
c1.plotly_chart(fig_gauge, use_container_width=True)
c2.plotly_chart(fig_trend, use_container_width=True)

# --- Campaign Wise Budget Table ---
st.subheader("Campaign Budget Allocation")

# We don't have individual campaign budgets, so we'll simulate/allow input or just show spend
# For now, just show spend and % of total spend
camp_data = combined_df.groupby('Campaign').agg({'Spend': 'sum', 'Conversions': 'sum'}).reset_index()
camp_data['% of Total Spend'] = (camp_data['Spend'] / total_spend * 100).map('{:.1f}%'.format)
camp_data['CPA'] = camp_data['Spend'] / camp_data['Conversions']

# Format currency columns for display
camp_data_display = camp_data.copy()
camp_data_display['Spend'] = camp_data_display['Spend'].apply(lambda x: format_currency(x))
camp_data_display['CPA'] = camp_data_display['CPA'].apply(lambda x: format_currency(x))

st.dataframe(camp_data_display, use_container_width=True)

# --- Alerts ---
if total_spend > total_budget:
    st.error(f"⚠️ Budget Exceeded! You are over budget by {format_currency(total_spend - total_budget)}")
elif utilization > 90:
    st.warning(f"⚠️ Budget Critical! You have used {utilization:.1f}% of your budget.")
else:
    st.success("✅ Budget is on track.")
