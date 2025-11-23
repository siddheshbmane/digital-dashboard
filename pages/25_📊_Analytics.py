import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from utils.data_loader import load_client_data
from utils.data_processing import merge_api_and_leads, get_campaign_service_map, load_lead_data
from utils.currency import format_currency

# Page Config
st.set_page_config(
    page_title="Analytics",
    page_icon="📊",
    layout="wide"
)

# --- Top-Level Filters ---
st.title("📊 Analytics")
st.markdown("Comprehensive performance metrics and lead analysis.")

# Create a container for filters at the top
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Client Selector
        from utils.auth_helper import render_client_selector
        render_client_selector(key_suffix="_analytics")
        
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
with st.spinner("Fetching Analytics Data..."):
    # Load API Data
    google_df, fb_df = load_client_data(client_id, start_date, end_date)
    
    # Load Lead Data
    leads_df = load_lead_data(client_id)

# Merge Data for Source Attribution
google_merged = merge_api_and_leads(google_df, leads_df)
fb_merged = merge_api_and_leads(fb_df, leads_df)
combined_df = pd.concat([google_merged, fb_merged], ignore_index=True)

if combined_df.empty:
    st.warning("No data available for the selected period.")
    st.stop()

# --- Calculations ---

# 1. Master Summary Metrics
total_spend = combined_df['Spend'].sum()
total_leads = combined_df['Conversions'].sum() # From API (merged)
qualified_leads = combined_df['Qualified Leads'].sum()
total_revenue = combined_df['ConversionValue'].sum()

avg_cpl = (total_spend / total_leads) if total_leads > 0 else 0
avg_cpql = (total_spend / qualified_leads) if qualified_leads > 0 else 0
qual_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
overall_roas = (total_revenue / total_spend * 100) if total_spend > 0 else 0

# 2. Detailed Source Analysis
source_stats = combined_df.groupby('Source').agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum',
    'ConversionValue': 'sum'
}).reset_index()

source_stats['Qual Rate'] = (source_stats['Qualified Leads'] / source_stats['Conversions'] * 100).fillna(0)
source_stats['Avg CPL'] = (source_stats['Spend'] / source_stats['Conversions']).replace([float('inf')], 0).fillna(0)
source_stats['Avg CPQL'] = (source_stats['Spend'] / source_stats['Qualified Leads']).replace([float('inf')], 0).fillna(0)
source_stats['ROI'] = ((source_stats['ConversionValue'] - source_stats['Spend']) / source_stats['Spend'] * 100).replace([float('inf')], 0).fillna(0)

# 3. Stage-wise Lead Analysis
# We need raw leads_df for this to get stages
# Map Campaign ID to Source
if 'Campaign ID' in combined_df.columns:
    campaign_source_map = combined_df[['Campaign ID', 'Source']].drop_duplicates().set_index('Campaign ID')['Source'].to_dict()
else:
    campaign_source_map = {}

if not leads_df.empty:
    # Ensure IDs are int
    leads_df['Campaign ID'] = pd.to_numeric(leads_df['Campaign ID'], errors='coerce').fillna(-1).astype(int)
    leads_df['Source'] = leads_df['Campaign ID'].map(campaign_source_map).fillna("Organic/Direct")
    
    # Group by Stage and Sub-stage (if available, otherwise just Stage)
    # The screenshot shows "Lead Stage" and "Sub-Stage". 
    # Our current leads_df might only have 'Lead Stage'. 
    # Let's check columns. If no sub-stage, we just use Stage.
    # Assuming 'Lead Stage' is the main one.
    
    # We need to calculate:
    # - Total Leads
    # - Google Count
    # - Meta Count
    # - Lead % (Count / Total Leads)
    # - Lead Cost/Spend (Count * Overall Avg CPL)
    # - Lead Spend % (Lead Cost / Total Spend)
    
    # Filter leads to match the date range? 
    # The leads_df is usually all leads. We should filter by 'Date' if available.
    # Our load_lead_data doesn't filter by date. 
    # But `merge_api_and_leads` does implicit filtering when joining with API data.
    # For this standalone table, we should try to filter leads if they have a date column.
    if 'Date' in leads_df.columns:
        leads_df['Date'] = pd.to_datetime(leads_df['Date'])
        mask = (leads_df['Date'] >= pd.to_datetime(start_date)) & (leads_df['Date'] <= pd.to_datetime(end_date))
        filtered_leads = leads_df.loc[mask]
    else:
        # If no date in leads, we might be showing all leads. 
        # But the user expects consistency with the "Master Summary" (which uses API date range).
        # Let's assume for now we use all leads or try to match via Campaign ID which are active in that period.
        # Better: Use leads that matched in `combined_df`? 
        # No, `combined_df` is aggregated.
        # Let's use leads_df but acknowledge it might be total.
        filtered_leads = leads_df # Placeholder if no date
        
    # Grouping
    stage_groups = filtered_leads.groupby('Lead Stage')
    
    stage_data = []
    total_leads_count = len(filtered_leads)
    
    for stage, group in stage_groups:
        count = len(group)
        google_count = len(group[group['Source'] == 'Google Ads'])
        meta_count = len(group[group['Source'] == 'Facebook Ads']) # Assuming 'Facebook Ads' is the source name from connector
        
        lead_pct = (count / total_leads_count * 100) if total_leads_count > 0 else 0
        lead_cost = count * avg_cpl # Pro-rated cost
        lead_spend_pct = (lead_cost / total_spend * 100) if total_spend > 0 else 0
        
        # Sub-stages?
        # If the user has a 'Sub Stage' column, we'd group by that too.
        # For now, we'll just do main stage.
        
        stage_data.append({
            'Lead Stage': stage,
            'Total Leads': count,
            'Google': google_count,
            'Meta': meta_count,
            'Lead %': lead_pct,
            'Lead Cost/Spend': lead_cost,
            'Lead Spend %': lead_spend_pct
        })
        
    stage_df = pd.DataFrame(stage_data)
    if not stage_df.empty:
        stage_df = stage_df.sort_values('Total Leads', ascending=False)

# --- UI Layout ---

# 1. Master Summary
st.subheader("Master Summary")
st.markdown("Overall performance metrics across all platforms")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Ad Spend", format_currency(total_spend), "0.0% vs last period") # Delta placeholder
m2.metric("Total Leads", int(total_leads), "0.0% vs last period")
m3.metric("Qualified Leads", int(qualified_leads), f"{qual_rate:.1f}% qualification rate")
m4.metric("Total Revenue", format_currency(total_revenue), f"{overall_roas:.0f}% ROAS")

m5, m6, m7, m8 = st.columns(4)
m5.metric("Average CPL", format_currency(avg_cpl))
m6.metric("Average CPQL", format_currency(avg_cpql))
m7.metric("Qualification Rate", f"{qual_rate:.1f}%")
m8.metric("Overall ROAS", f"{overall_roas:.0f}%")

st.markdown("---")

# 2. Detailed Source Analysis
st.subheader("Lead Source Analysis")
st.markdown("Detailed breakdown of leads by source, stage, and campaign performance")

st.markdown("#### Detailed Source Analysis")
display_source = source_stats.copy()
display_source['Spend'] = display_source['Spend'].apply(format_currency)
display_source['Revenue'] = display_source['ConversionValue'].apply(format_currency)
display_source['Avg CPL'] = display_source['Avg CPL'].apply(format_currency)
display_source['Avg CPQL'] = display_source['Avg CPQL'].apply(format_currency)
display_source['Qual Rate'] = display_source['Qual Rate'].map('{:.1f}%'.format)
display_source['ROI'] = display_source['ROI'].map('{:.0f}%'.format)

st.dataframe(
    display_source[['Source', 'Spend', 'Conversions', 'Qualified Leads', 'Qual Rate', 'Avg CPL', 'Avg CPQL', 'Revenue', 'ROI']],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Spend": "Total Spend",
        "Conversions": "Total Leads",
        "Qualified Leads": "Qualified",
        "Qual Rate": "Qual. Rate",
        "Revenue": "Revenue",
        "ROI": "ROI"
    }
)

st.markdown("---")

# 3. Stage-wise Lead Analysis
st.subheader("Stage-wise Lead Analysis by Source")
st.markdown("Lead distribution across stages with source breakdown")

if not leads_df.empty:
    # --- Expandable Stage Analysis ---
    
    # 1. Detect Sub-Stage Column
    sub_stage_col = 'Sub Stage'
    possible_cols = ['Sub Stage', 'Sub-Stage', 'Reason', 'Disposition', 'Notes']
    
    found_col = next((c for c in possible_cols if c in leads_df.columns), None)
    
    if found_col:
        leads_df['Sub Stage'] = leads_df[found_col].fillna('Unspecified')
    else:
        leads_df['Sub Stage'] = 'TOTAL' # Default if no sub-stage info
        
    # Group by Stage and Sub-Stage
    stage_sub_groups = leads_df.groupby(['Lead Stage', 'Sub Stage'])
    
    # Calculate metrics for each (Stage, Sub-Stage) pair
    detailed_data = []
    for (stage, sub_stage), group in stage_sub_groups:
        count = len(group)
        google_count = len(group[group['Source'] == 'Google Ads'])
        meta_count = len(group[group['Source'] == 'Facebook Ads'])
        
        lead_pct = (count / total_leads_count * 100) if total_leads_count > 0 else 0
        lead_cost = count * avg_cpl
        lead_spend_pct = (lead_cost / total_spend * 100) if total_spend > 0 else 0
        
        detailed_data.append({
            'Lead Stage': stage,
            'Sub-Stage': sub_stage,
            'Total Leads': count,
            'Google': google_count,
            'Meta': meta_count,
            'Lead %': lead_pct,
            'Lead Cost/Spend': lead_cost,
            'Lead Spend %': lead_spend_pct
        })
        
    detailed_df = pd.DataFrame(detailed_data)
    
    # Header Row
    # Adjust column ratios to match screenshot
    col_ratios = [2.5, 2.5, 1, 1, 1, 1, 1.5, 1]
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns(col_ratios)
    h1.markdown("**LEAD STAGE**")
    h2.markdown("**SUB-STAGE**")
    h3.markdown("**TOTAL LEADS**")
    h4.markdown("**GOOGLE**")
    h5.markdown("**META**")
    h6.markdown("**LEAD %**")
    h7.markdown("**LEAD COST/SPEND**")
    h8.markdown("**LEAD SPEND %**")
    
    st.divider()
    
    # Iterate through unique Stages
    if not detailed_df.empty:
        # Sort stages by Total Leads desc
        stage_totals = detailed_df.groupby('Lead Stage')['Total Leads'].sum().sort_values(ascending=False)
        sorted_stages = stage_totals.index.tolist()
        
        for stage in sorted_stages:
            stage_subset = detailed_df[detailed_df['Lead Stage'] == stage]
            
            # Calculate Stage Summary
            s_total = stage_subset['Total Leads'].sum()
            s_google = stage_subset['Google'].sum()
            s_meta = stage_subset['Meta'].sum()
            s_pct = (s_total / total_leads_count * 100) if total_leads_count > 0 else 0
            s_cost = s_total * avg_cpl
            s_spend_pct = (s_cost / total_spend * 100) if total_spend > 0 else 0
            
            # Render Expander
            # Label shows Stage and Total
            with st.expander(f"{stage} (Total: {s_total})", expanded=False):
                
                # 1. Render TOTAL Row (Summary) inside expander for alignment
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(col_ratios)
                c1.markdown(f"**{stage}**")
                c2.markdown("**TOTAL**")
                c3.markdown(f"**{s_total}**")
                c4.markdown(f"**{s_google}**")
                c5.markdown(f"**{s_meta}**")
                c6.markdown(f"**{s_pct:.2f}%**")
                c7.markdown(f"**{format_currency(s_cost)}**")
                c8.markdown(f"**{s_spend_pct:.2f}%**")
                
                st.divider()
                
                # 2. Render Sub-Stage Rows
                for _, row in stage_subset.iterrows():
                    # Skip if sub-stage is 'TOTAL' (though we created it, we might want to show it if it's the only one)
                    # Actually, if we have sub-stages, we show them.
                    # If the only sub-stage is 'TOTAL' (default), we effectively show the summary row again?
                    # Let's show all rows from detailed_df.
                    
                    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(col_ratios)
                    c1.write("") # Indent or empty
                    c2.write(row['Sub-Stage'])
                    c3.write(str(row['Total Leads']))
                    c4.write(str(row['Google']))
                    c5.write(str(row['Meta']))
                    c6.write(f"{row['Lead %']:.2f}%")
                    c7.write(format_currency(row['Lead Cost/Spend']))
                    c8.write(f"{row['Lead Spend %']:.2f}%")

    # Grand Total Footer
    st.divider()
    t1, t2, t3, t4, t5, t6, t7, t8 = st.columns(col_ratios)
    t1.markdown("**GRAND TOTAL**")
    t2.markdown("")
    t3.markdown(f"**{total_leads_count}**")
    t4.markdown(f"**{detailed_df['Google'].sum() if not detailed_df.empty else 0}**")
    t5.markdown(f"**{detailed_df['Meta'].sum() if not detailed_df.empty else 0}**")
    t6.markdown("**100.00%**")
    t7.markdown(f"**{format_currency(total_spend)}**")
    t8.markdown("**100.00%**")

else:
    st.info("No lead data available to display stage analysis.")
