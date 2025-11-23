import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from utils.auth_helper import render_client_selector, get_context_credentials
from connectors.google_ads import GoogleAdsConnector
from utils.currency import format_currency

# Page Config
st.set_page_config(page_title="Geographic Analysis", page_icon="🗺️", layout="wide")

# --- Top-Level Filters ---
st.title("🗺️ Geographic Performance")
st.markdown("Analyze performance by City and State directly from Google Ads.")

# Create a container for filters at the top
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Client Selector
        render_client_selector(key_suffix="_geo")
        
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
with st.spinner("Fetching Geographic Data from Google Ads..."):
    # Get Credentials
    google_creds, _, _ = get_context_credentials()
    
    # Initialize Connector
    use_mock = not bool(google_creds)
    connector = GoogleAdsConnector(credentials=google_creds, use_mock=use_mock)
    
    # Fetch Data
    geo_data = connector.get_geo_data(start_date, end_date)

if geo_data.empty:
    st.info("No geographic data available for the selected period.")
    st.stop()

# --- Calculations ---
# Ensure numeric columns
cols_to_numeric = ['Impressions', 'Clicks', 'Spend', 'Conversions', 'ConversionValue']
for col in cols_to_numeric:
    if col in geo_data.columns:
        geo_data[col] = pd.to_numeric(geo_data[col], errors='coerce').fillna(0)

# Metrics
total_impressions = geo_data['Impressions'].sum()
total_clicks = geo_data['Clicks'].sum()
total_spend = geo_data['Spend'].sum()
total_conversions = geo_data['Conversions'].sum() if 'Conversions' in geo_data.columns else 0
total_revenue = geo_data['ConversionValue'].sum() if 'ConversionValue' in geo_data.columns else 0

avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
avg_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
roas = (total_revenue / total_spend * 100) if total_spend > 0 else 0

# Calculated Columns
geo_data['CTR'] = (geo_data['Clicks'] / geo_data['Impressions'] * 100).fillna(0)
geo_data['CPC'] = (geo_data['Spend'] / geo_data['Clicks']).replace([float('inf')], 0).fillna(0)
if 'Conversions' in geo_data.columns:
    geo_data['CPA'] = (geo_data['Spend'] / geo_data['Conversions']).replace([float('inf')], 0).fillna(0)
    geo_data['ROAS'] = (geo_data['ConversionValue'] / geo_data['Spend'] * 100).replace([float('inf')], 0).fillna(0)
else:
    geo_data['CPA'] = 0
    geo_data['ROAS'] = 0

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
    st.subheader("Top Locations by Spend")
    top_spend = geo_data.sort_values('Spend', ascending=False).head(10)
    fig_spend = px.bar(top_spend, x='Spend', y='Location', orientation='h', title="Top Locations by Spend", text_auto='.2s')
    fig_spend.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_spend, use_container_width=True)

with c2:
    st.subheader("Top Locations by Conversions")
    if total_conversions > 0:
        top_conv = geo_data.sort_values('Conversions', ascending=False).head(10)
        fig_conv = px.bar(top_conv, x='Conversions', y='Location', orientation='h', title="Top Locations by Conversions", text_auto=True)
        fig_conv.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_conv, use_container_width=True)
    else:
        st.info("No conversions to display.")

# 3. Map / Distribution (Simulated with Pie for now as we don't have lat/long easily)
st.subheader("Spend Distribution by Location")
fig_pie = px.pie(geo_data.head(15), values='Spend', names='Location', title="Spend Share by Top 15 Locations", hole=0.4)
st.plotly_chart(fig_pie, use_container_width=True)


# 4. Detailed Table
st.subheader("Detailed Geographic Performance")

# Format for display
display_df = geo_data.copy()
display_df['Spend'] = display_df['Spend'].apply(format_currency)
display_df['CPC'] = display_df['CPC'].apply(format_currency)
display_df['CPA'] = display_df['CPA'].apply(format_currency)
display_df['Revenue'] = display_df['ConversionValue'].apply(format_currency)
display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
display_df['ROAS'] = display_df['ROAS'].map('{:.0f}%'.format)

st.dataframe(
    display_df[['Location', 'Spend', 'Impressions', 'Clicks', 'CTR', 'CPC', 'Conversions', 'CPA', 'Revenue', 'ROAS']],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Location": "Location",
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
