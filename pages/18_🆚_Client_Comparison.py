import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from utils.data_processing import load_lead_data, merge_api_and_leads
from utils.currency import format_currency
from utils.data_loader import load_client_data, filter_data
from utils.client_manager import get_active_clients
from datetime import datetime, timedelta

st.set_page_config(page_title="Client Comparison", page_icon="🆚", layout="wide")

st.title("🆚 Client Comparison")
st.markdown("Benchmark performance across all your clients.")

# --- Sidebar Filters ---
st.sidebar.header("Configuration")

from utils.auth_helper import render_client_selector
render_client_selector()

# --- Data Loading (All Clients) ---
active_clients = get_active_clients()
all_client_data = []

# Date Filter
st.sidebar.header("Filters")
today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", (last_30_days, today))

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()

start_date, end_date = date_range

with st.spinner("Loading data for all clients..."):
    for client in active_clients:
        cid = client['id']
        cname = client['name']
        
        # Load data
        g_df, f_df = load_client_data(cid, start_date, end_date)
        l_df = load_lead_data(cid)
        
        # Merge
        g_merged = merge_api_and_leads(g_df, l_df)
        f_merged = merge_api_and_leads(f_df, l_df)
        combined = pd.concat([g_merged, f_merged], ignore_index=True)
        
        if not combined.empty:
            # Aggregate
            summary = {
                'Client': cname,
                'Spend': combined['Spend'].sum(),
                'Conversions': combined['Conversions'].sum(),
                'Qualified Leads': combined['Qualified Leads'].sum() if 'Qualified Leads' in combined.columns else 0,
                'Revenue': combined['ConversionValue'].sum() if 'ConversionValue' in combined.columns else 0,
                'Impressions': combined['Impressions'].sum(),
                'Clicks': combined['Clicks'].sum()
            }
            all_client_data.append(summary)

if not all_client_data:
    st.warning("No data available for any client.")
    st.stop()

comp_df = pd.DataFrame(all_client_data)

# Derived Metrics
comp_df['CPL'] = np.where(comp_df['Conversions'] > 0, comp_df['Spend'] / comp_df['Conversions'], 0)
comp_df['CPQL'] = np.where(comp_df['Qualified Leads'] > 0, comp_df['Spend'] / comp_df['Qualified Leads'], 0)
comp_df['ROI'] = np.where(comp_df['Spend'] > 0, (comp_df['Revenue'] - comp_df['Spend']) / comp_df['Spend'] * 100, 0)
comp_df['Qual Rate'] = np.where(comp_df['Conversions'] > 0, comp_df['Qualified Leads'] / comp_df['Conversions'] * 100, 0)

# --- Leaderboards ---
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Top Spender")
    top_spend = comp_df.sort_values('Spend', ascending=False).iloc[0]
    st.metric(top_spend['Client'], format_currency(top_spend['Spend']))

with col2:
    st.subheader("Most Leads")
    top_leads = comp_df.sort_values('Conversions', ascending=False).iloc[0]
    st.metric(top_leads['Client'], f"{int(top_leads['Conversions'])}")

with col3:
    st.subheader("Best ROI")
    top_roi = comp_df.sort_values('ROI', ascending=False).iloc[0]
    st.metric(top_roi['Client'], f"{top_roi['ROI']:.1f}%")

# --- Charts ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("Spend vs Revenue")
    fig_rev = px.bar(comp_df, x='Client', y=['Spend', 'Revenue'], barmode='group', title="Spend vs Revenue by Client")
    st.plotly_chart(fig_rev, use_container_width=True)

with c2:
    st.subheader("Cost Per Lead (CPL)")
    fig_cpl = px.bar(comp_df, x='Client', y='CPL', title="CPL by Client (Lower is Better)", color='CPL', color_continuous_scale='RdYlGn_r')
    st.plotly_chart(fig_cpl, use_container_width=True)

# --- Efficiency Scatter ---
st.subheader("Efficiency Matrix: CPL vs Qualification Rate")
fig_eff = px.scatter(comp_df, x='CPL', y='Qual Rate', size='Conversions', color='Client', 
                     hover_name='Client', title="CPL vs Qual Rate (Size = Leads)")
# Invert X axis because lower CPL is better? No, standard scatter is fine, just interpret.
st.plotly_chart(fig_eff, use_container_width=True)

# --- Detailed Table ---
st.subheader("Detailed Client Performance")
st.dataframe(comp_df.style.format({
    'Spend': lambda x: format_currency(x),
    'Revenue': lambda x: format_currency(x),
    'CPL': lambda x: format_currency(x),
    'CPQL': lambda x: format_currency(x),
    'ROI': '{:.1f}%',
    'Qual Rate': '{:.1f}%'
}), use_container_width=True)
