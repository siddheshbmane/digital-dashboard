import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from utils.auth_helper import render_client_selector, get_context_credentials
from connectors.google_ads import GoogleAdsConnector
from utils.currency import format_currency

# Page Config
st.set_page_config(page_title="Keyword Analysis", page_icon="🔑", layout="wide")

# --- Top-Level Filters ---
st.title("🔑 Keyword Analysis")
st.markdown("Analyze performance of your Search Keywords directly from Google Ads.")

# Create a container for filters at the top
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Client Selector
        render_client_selector(key_suffix="_keyword")
        
    with col2:
        # Date Range
        today = datetime.today()
        last_30_days = today - timedelta(days=30)
        date_range = st.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

    with col3:
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

# Check Client Selection
if st.session_state.get('selected_client_id') == "ALL":
    st.warning("Please select a specific client to view this report.")
    st.stop()

if 'selected_client_id' not in st.session_state:
    st.warning("Please select a client.")
    st.stop()

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
    
start_date, end_date = date_range

# --- Data Loading ---
with st.spinner("Fetching Keyword Data from Google Ads..."):
    # Get Credentials
    google_creds, _, _ = get_context_credentials()
    
    # Initialize Connector
    # Check if we should use mock data (usually based on config or failure)
    # For now, we'll assume real data if creds exist, else mock if configured?
    # The connector handles mock if creds are None but use_mock is True.
    # We'll check if creds are empty.
    use_mock = not bool(google_creds)
    
    connector = GoogleAdsConnector(credentials=google_creds, use_mock=use_mock)
    
    # Fetch Data
    kw_data = connector.get_keyword_data(start_date, end_date)

if kw_data.empty:
    st.info("No keyword data available for the selected period.")
    st.stop()

# --- Calculations ---
# Ensure numeric columns
cols_to_numeric = ['Impressions', 'Clicks', 'Spend', 'Conversions', 'ConversionValue']
for col in cols_to_numeric:
    if col in kw_data.columns:
        kw_data[col] = pd.to_numeric(kw_data[col], errors='coerce').fillna(0)

# Metrics
total_impressions = kw_data['Impressions'].sum()
total_clicks = kw_data['Clicks'].sum()
total_spend = kw_data['Spend'].sum()
total_conversions = kw_data['Conversions'].sum()
total_revenue = kw_data['ConversionValue'].sum()

avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
avg_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
roas = (total_revenue / total_spend * 100) if total_spend > 0 else 0

# Calculated Columns for DataFrame
kw_data['CTR'] = (kw_data['Clicks'] / kw_data['Impressions'] * 100).fillna(0)
kw_data['CPC'] = (kw_data['Spend'] / kw_data['Clicks']).replace([float('inf')], 0).fillna(0)
kw_data['CPA'] = (kw_data['Spend'] / kw_data['Conversions']).replace([float('inf')], 0).fillna(0)
kw_data['ROAS'] = (kw_data['ConversionValue'] / kw_data['Spend'] * 100).replace([float('inf')], 0).fillna(0)

# --- UI Layout ---

# 1. Top Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Spend", format_currency(total_spend))
m2.metric("Total Conversions", int(total_conversions))
m3.metric("Avg CPA", format_currency(avg_cpa))
m4.metric("ROAS", f"{roas:.0f}%")

m5, m6, m7, m8 = st.columns(4)
m5.metric("Impressions", f"{int(total_impressions):,}")
m6.metric("Clicks", f"{int(total_clicks):,}")
m7.metric("CTR", f"{avg_ctr:.2f}%")
m8.metric("Avg CPC", format_currency(avg_cpc))

st.markdown("---")

# 2. Charts
c1, c2 = st.columns(2)

with c1:
    st.subheader("Top 10 Keywords by Spend")
    top_spend = kw_data.sort_values('Spend', ascending=False).head(10)
    fig_spend = px.bar(top_spend, x='Spend', y='Keyword', orientation='h', title="Top Keywords by Spend", text_auto='.2s')
    fig_spend.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_spend, use_container_width=True)

with c2:
    st.subheader("Top 10 Keywords by Conversions")
    top_conv = kw_data.sort_values('Conversions', ascending=False).head(10)
    fig_conv = px.bar(top_conv, x='Conversions', y='Keyword', orientation='h', title="Top Keywords by Conversions", text_auto=True)
    fig_conv.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_conv, use_container_width=True)

# 3. Scatter Plot (CPA vs Conversions)
st.subheader("Keyword Efficiency: CPA vs Conversions")
fig_scatter = px.scatter(
    kw_data[kw_data['Conversions'] > 0], 
    x='CPA', 
    y='Conversions', 
    size='Spend', 
    color='ROAS',
    hover_name='Keyword', 
    title="CPA vs Conversions (Size = Spend, Color = ROAS)",
    log_x=True # CPA can vary widely
)
st.plotly_chart(fig_scatter, use_container_width=True)

# 4. Detailed Table
st.subheader("Detailed Keyword Performance")

# Format for display
display_df = kw_data.copy()
display_df['Spend'] = display_df['Spend'].apply(format_currency)
display_df['CPC'] = display_df['CPC'].apply(format_currency)
display_df['CPA'] = display_df['CPA'].apply(format_currency)
display_df['Revenue'] = display_df['ConversionValue'].apply(format_currency)
display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
display_df['ROAS'] = display_df['ROAS'].map('{:.0f}%'.format)

st.dataframe(
    display_df[['Keyword', 'Spend', 'Impressions', 'Clicks', 'CTR', 'CPC', 'Conversions', 'CPA', 'Revenue', 'ROAS']],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Keyword": "Keyword",
        "Spend": "Cost",
        "Impressions": "Impr.",
        "Clicks": "Clicks",
        "CTR": "CTR",
        "CPC": "CPC",
        "Conversions": "Conv.",
        "CPA": "CPA",
        "Revenue": "Conv. Value",
        "ROAS": "ROAS"
    }
)
