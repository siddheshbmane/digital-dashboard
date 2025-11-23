import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from utils.data_loader import load_client_data
from utils.data_processing import merge_api_and_leads, get_campaign_service_map, get_service_performance_data, load_lead_data
from utils.currency import format_currency

# Page Config
st.set_page_config(
    page_title="Service Analytics",
    page_icon="📦",
    layout="wide"
)

# --- Top-Level Filters (Layout Change) ---
st.title("📦 Service Analytics")
st.markdown("Performance analysis by Service or Product line.")

# Create a container for filters at the top
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Client Selector
        from utils.auth_helper import render_client_selector
        render_client_selector(key_suffix="_top")
        use_mock_data = st.checkbox("Use Mock Data", value=False)
        
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

client_id = st.session_state['selected_client_id']

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
    
start_date, end_date = date_range

# --- Data Loading ---
with st.spinner("Fetching Service Data..."):
    # Load API Data
    google_df, fb_df = load_client_data(client_id, start_date, end_date, use_mock_data=use_mock_data)
    
    # Load Lead Data (Essential for Service Mapping)
    leads_df = load_lead_data(client_id)

# Merge Data
# We need to merge to get Campaign IDs aligned
google_merged = merge_api_and_leads(google_df, leads_df)
fb_merged = merge_api_and_leads(fb_df, leads_df)
combined_df = pd.concat([google_merged, fb_merged], ignore_index=True)

if combined_df.empty:
    st.warning("No data available for the selected period.")
    st.stop()

# --- Configuration ---
from utils.client_manager import get_active_clients, update_client_config

# Get current client config
active_clients = get_active_clients()
current_client = next((c for c in active_clients if c['id'] == client_id), None)
current_service_col = current_client.get('service_column') if current_client else None
current_regex_rules = current_client.get('service_regex_rules') if current_client else None

with st.expander("Configuration", expanded=False):
    st.write("Configure which column in your uploaded leads represents the Service or Product.")
    
    if not leads_df.empty:
        # Filter out likely non-service columns (dates, IDs) to make list cleaner
        potential_cols = [c for c in leads_df.columns if 'ID' not in c and 'Date' not in c and 'Time' not in c]
        # Ensure current selection is in list
        if current_service_col and current_service_col not in potential_cols:
            potential_cols.append(current_service_col)
            
        selected_col = st.selectbox(
            "Select Service/Product Column", 
            options=[""] + sorted(potential_cols),
            index=potential_cols.index(current_service_col) + 1 if current_service_col in potential_cols else 0,
            help="Select the column that identifies the service or product sold."
        )
        
        if st.button("Save Configuration"):
            if selected_col:
                update_client_config(client_id, {'service_column': selected_col})
                st.success(f"Saved '{selected_col}' as the Service column for this client.")
                st.cache_data.clear()
                st.rerun()
            else:
                # If cleared
                update_client_config(client_id, {'service_column': None})
                st.success("Cleared Service column configuration.")
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("Upload lead data to configure columns.")

# --- Processing ---

# 1. Get Service Map from Leads
# Use the configured column if available
service_map = get_campaign_service_map(leads_df, service_col=current_service_col, regex_rules=current_regex_rules)

if not service_map:
    if current_service_col:
        st.warning(f"Configuration set to '{current_service_col}', but no valid mapping found. Checking default columns...")
        # Try default fallback
        service_map = get_campaign_service_map(leads_df, regex_rules=current_regex_rules)
        
    if not service_map:
        st.info("No Service/Product mapping found in lead data. Showing data by Campaign Name instead.")
        # Fallback: Use Campaign Name as 'Service'
        combined_df['Service'] = combined_df['Campaign']
        
        service_stats = combined_df.groupby('Campaign').agg({
            'Spend': 'sum',
            'Conversions': 'sum',
            'Qualified Leads': 'sum',
            'ConversionValue': 'sum',
            'Clicks': 'sum',
            'Impressions': 'sum'
        }).reset_index().rename(columns={'Campaign': 'Service'})
        
        # Calc metrics manually for fallback
        service_stats['CPA'] = (service_stats['Spend'] / service_stats['Conversions']).replace([float('inf')], 0).fillna(0)
        service_stats['Conv Rate'] = (service_stats['Conversions'] / service_stats['Clicks'] * 100).fillna(0)
        service_stats['Pipeline Value'] = service_stats['ConversionValue']
    else:
         service_stats = get_service_performance_data(combined_df, service_map)
else:
    service_stats = get_service_performance_data(combined_df, service_map)

# Sort by Spend
service_stats = service_stats.sort_values('Spend', ascending=False)

# --- Visualizations ---

# Row 1: Summary Cards
st.subheader("Service Performance Overview")
cols = st.columns(len(service_stats))

# Limit to top 4 for cards if too many
top_services = service_stats.head(4)

for idx, row in top_services.iterrows():
    with cols[idx % 4]:
        with st.container(border=True):
            st.markdown(f"### {row['Service']}")
            st.metric("Revenue", format_currency(row['ConversionValue']))
            st.metric("Conv Rate", f"{row['Conv Rate']:.1f}%")
            st.metric("Pipeline Value", format_currency(row['Pipeline Value']))

st.markdown("---")

# Row 2: Charts
col1, col2 = st.columns(2)

with col1:
    st.subheader("Revenue by Service")
    fig_rev = px.pie(service_stats, values='ConversionValue', names='Service', hole=0.4, title="Revenue Distribution")
    st.plotly_chart(fig_rev, use_container_width=True)

with col2:
    st.subheader("Conversion Rate by Service")
    fig_conv = px.bar(service_stats, x='Service', y='Conv Rate', color='Service', title="Conversion Rate (%)")
    st.plotly_chart(fig_conv, use_container_width=True)

# Row 3: Lead Volume & Deal Size
col3, col4 = st.columns(2)

with col3:
    st.subheader("Lead Volume by Service")
    fig_vol = px.bar(service_stats, x='Service', y='Conversions', color='Service', title="Total Leads")
    st.plotly_chart(fig_vol, use_container_width=True)

with col4:
    st.subheader("Pipeline Value by Service")
    fig_pipe = px.bar(service_stats, x='Service', y='Pipeline Value', color='Service', title="Estimated Pipeline Value")
    st.plotly_chart(fig_pipe, use_container_width=True)

# --- Detailed Table ---
st.markdown("---")
st.subheader("Detailed Service Analysis")

display_df = service_stats.copy()
display_df['Spend'] = display_df['Spend'].apply(format_currency)
display_df['Revenue'] = display_df['ConversionValue'].apply(format_currency)
display_df['Pipeline Value'] = display_df['Pipeline Value'].apply(format_currency)
display_df['CPA'] = display_df['CPA'].apply(format_currency)
display_df['Conv Rate'] = display_df['Conv Rate'].map('{:.1f}%'.format)

st.dataframe(
    display_df[['Service', 'Conversions', 'Qualified Leads', 'Conv Rate', 'Spend', 'Revenue', 'Pipeline Value', 'CPA']],
    use_container_width=True,
    hide_index=True
)
