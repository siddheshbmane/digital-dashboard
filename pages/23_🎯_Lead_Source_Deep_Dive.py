import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from utils.data_loader import load_client_data
from utils.data_processing import merge_api_and_leads, get_source_stage_data, load_lead_data
from utils.currency import format_currency

# Page Config
st.set_page_config(
    page_title="Lead Source Deep Dive",
    page_icon="🎯",
    layout="wide"
)

# --- Top-Level Filters (Layout Change) ---
st.title("🎯 Lead Source Deep Dive")
st.markdown("Detailed analysis of lead sources and their conversion funnels.")

# Create a container for filters at the top
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Client Selector
        from utils.auth_helper import render_client_selector
        render_client_selector(key_suffix="_top") # Use suffix to avoid key collision if sidebar also has it
        
    with col2:
        # Date Range
        today = datetime.today()
        last_30_days = today - timedelta(days=30)
        date_range = st.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

    with col3:
        # Refresh Button (Streamlit reruns on interaction, so this is just visual mostly, but can clear cache)
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

client_id = st.session_state['selected_client_id']

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
    
start_date, end_date = date_range

# --- Data Loading ---
with st.spinner("Fetching Source Data..."):
    # Load API Data
    google_df, fb_df = load_client_data(client_id, start_date, end_date)
    
    # Load Lead Data
    leads_df = load_lead_data(client_id)

# Merge Data
# We need granular merge to get source info for leads if possible
google_merged = merge_api_and_leads(google_df, leads_df)
fb_merged = merge_api_and_leads(fb_df, leads_df)
combined_df = pd.concat([google_merged, fb_merged], ignore_index=True)

if combined_df.empty:
    st.warning("No data available for the selected period.")
    st.stop()

# --- Processing for Source Analysis ---

# 1. Source Summary Metrics
# Group by Source
source_stats = combined_df.groupby('Source').agg({
    'Spend': 'sum',
    'Conversions': 'sum', # Total Leads
    'Qualified Leads': 'sum',
    'ConversionValue': 'sum',
    'Clicks': 'sum',
    'Impressions': 'sum'
}).reset_index()

# Calculate Metrics
source_stats['CPL'] = (source_stats['Spend'] / source_stats['Conversions']).replace([float('inf')], 0).fillna(0)
source_stats['CPQL'] = (source_stats['Spend'] / source_stats['Qualified Leads']).replace([float('inf')], 0).fillna(0)
source_stats['Qual Rate'] = (source_stats['Qualified Leads'] / source_stats['Conversions'] * 100).fillna(0)
source_stats['ROI'] = ((source_stats['ConversionValue'] - source_stats['Spend']) / source_stats['Spend'] * 100).replace([float('inf')], 0).fillna(0)

# --- Visualizations ---

# Row 1: Summary Cards (Custom HTML-like cards using metric)
st.subheader("Source Performance Overview")
cols = st.columns(len(source_stats))

for idx, row in source_stats.iterrows():
    with cols[idx % 4]: # Wrap every 4
        with st.container(border=True):
            st.markdown(f"### {row['Source']}")
            st.metric("Total Leads", int(row['Conversions']))
            st.metric("Qual Rate", f"{row['Qual Rate']:.1f}%", delta_color="normal")
            st.metric("Avg CPL", format_currency(row['CPL']))
            st.metric("ROI", f"{row['ROI']:.1f}%")

st.markdown("---")

# Row 2: Charts
col1, col2 = st.columns(2)

with col1:
    st.subheader("Lead Distribution by Source")
    fig_pie = px.pie(source_stats, values='Conversions', names='Source', hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.subheader("Qualification Rate Comparison")
    fig_bar = px.bar(source_stats, x='Source', y='Qual Rate', color='Source', title="Qualification Rate (%)")
    st.plotly_chart(fig_bar, use_container_width=True)

# Row 3: CPL & ROI
col3, col4 = st.columns(2)

with col3:
    st.subheader("Cost Per Lead (CPL)")
    fig_cpl = px.bar(source_stats, x='Source', y='CPL', color='Source', title="Lower is Better")
    st.plotly_chart(fig_cpl, use_container_width=True)

with col4:
    st.subheader("Return on Investment (ROI)")
    fig_roi = px.bar(source_stats, x='Source', y='ROI', color='Source', title="Higher is Better")
    st.plotly_chart(fig_roi, use_container_width=True)

# --- Stage-wise Funnel Analysis ---
st.markdown("---")
st.subheader("Stage-wise Lead Analysis by Source")

# We need to get stage counts per source.
# Since 'combined_df' is aggregated/merged, it might not have row-level lead stage info unless we used the granular merge 
# AND the API data was granular enough to keep multiple rows per campaign.
# Actually, `merge_api_and_leads` aggregates leads into 'Conversions' and 'Qualified Leads' columns.
# It DOES NOT preserve the individual lead stages in the output dataframe (it drops them after counting).

# To get the detailed stage breakdown (New, Contacted, Qualified, Proposal, Won, Lost),
# we need to go back to the raw `leads_df` and try to attribute it to Source.
# We can use `leads_df` and map Campaign ID -> Source using `combined_df` (or API data).

# Create Campaign -> Source Map
campaign_source_map = combined_df[['Campaign ID', 'Source']].drop_duplicates().set_index('Campaign ID')['Source'].to_dict()

if not leads_df.empty:
    # Ensure Campaign ID is int
    leads_df['Campaign ID'] = pd.to_numeric(leads_df['Campaign ID'], errors='coerce').fillna(-1).astype(int)
    
    # Map Source
    leads_df['Source'] = leads_df['Campaign ID'].map(campaign_source_map).fillna("Organic/Direct")
    
    # Group by Stage and Source
    stage_source_counts = leads_df.groupby(['Lead Stage', 'Source']).size().reset_index(name='Count')
    
    # Pivot for Table Display
    pivot_table = stage_source_counts.pivot(index='Lead Stage', columns='Source', values='Count').fillna(0).astype(int)
    
    # Add Total Column
    pivot_table['Total'] = pivot_table.sum(axis=1)
    
    # Sort by Total (descending) or custom order if we had one
    pivot_table = pivot_table.sort_values('Total', ascending=False)
    
    st.dataframe(pivot_table, use_container_width=True)
    
else:
    st.info("No detailed lead data available for stage analysis.")

# --- Detailed Metrics Table ---
st.markdown("---")
st.subheader("Detailed Source Metrics")

display_df = source_stats.copy()
display_df['Spend'] = display_df['Spend'].apply(format_currency)
display_df['Revenue'] = display_df['ConversionValue'].apply(format_currency)
display_df['CPL'] = display_df['CPL'].apply(format_currency)
display_df['CPQL'] = display_df['CPQL'].apply(format_currency)
display_df['Qual Rate'] = display_df['Qual Rate'].map('{:.1f}%'.format)
display_df['ROI'] = display_df['ROI'].map('{:.1f}%'.format)

st.dataframe(
    display_df[['Source', 'Conversions', 'Qualified Leads', 'Qual Rate', 'Spend', 'Revenue', 'CPL', 'CPQL', 'ROI']],
    use_container_width=True,
    hide_index=True
)
