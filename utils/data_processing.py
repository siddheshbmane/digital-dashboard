import pandas as pd
import numpy as np

def aggregate_data(google_df, fb_df):
    """
    Combines data from multiple sources and calculates derived metrics.
    """
    combined_df = pd.concat([google_df, fb_df], ignore_index=True)
    
    # Calculate derived metrics safely (handling division by zero)
    combined_df['CTR'] = np.where(combined_df['Impressions'] > 0, 
                                  combined_df['Clicks'] / combined_df['Impressions'] * 100, 0)
    
    combined_df['CPC'] = np.where(combined_df['Clicks'] > 0, 
                                  combined_df['Spend'] / combined_df['Clicks'], 0)
    
    combined_df['CPA'] = np.where(combined_df['Conversions'] > 0, 
                                  combined_df['Spend'] / combined_df['Conversions'], 0)
    
    return combined_df

def get_funnel_data(df):
    """
    Aggregates data for the Lead Stage Funnel.
    Assumes: Impressions -> Clicks -> Conversions (Leads) -> Qualified Leads (Est) -> Closed (Est)
    """
    if df.empty:
        return pd.DataFrame()
        
    impressions = df['Impressions'].sum()
    clicks = df['Clicks'].sum()
    leads = df['Conversions'].sum()
    
    # Estimations for demo purposes (since we don't have CRM data yet)
    qualified = int(leads * 0.8) 
    closed = int(leads * 0.2)
    
    funnel_data = pd.DataFrame({
        'Stage': ['Impressions', 'Clicks', 'Leads', 'Qualified', 'Closed'],
        'Value': [impressions, clicks, leads, qualified, closed]
    })
    return funnel_data

def get_revenue_timeline(df):
    """
    Aggregates daily revenue for the timeline chart.
    """
    if df.empty:
        return pd.DataFrame()
    
    # Ensure ConversionValue exists, default to 0
    if 'ConversionValue' not in df.columns:
        df['ConversionValue'] = 0.0
        
    daily_rev = df.groupby('Date')['ConversionValue'].sum().reset_index()
    daily_rev['CumulativeRevenue'] = daily_rev['ConversionValue'].cumsum()
    return daily_rev

def get_platform_comparison(df):
    """
    Aggregates metrics by Source (Platform).
    """
    if df.empty:
        return pd.DataFrame()
        
    comp = df.groupby('Source').agg({
        'Spend': 'sum',
        'Conversions': 'sum',
        'ConversionValue': 'sum' if 'ConversionValue' in df.columns else lambda x: 0
    }).reset_index()
    
    # Calculate CPA
    comp['CPA'] = np.where(comp['Conversions'] > 0, comp['Spend'] / comp['Conversions'], 0)
    return comp

def get_hierarchical_campaign_data(df):
    """
    Prepares data for the campaign table.
    """
    if df.empty:
        return pd.DataFrame()
        
    # Group by Campaign and Source
    camp_data = df.groupby(['Campaign', 'Source']).agg({
        'Spend': 'sum',
        'Clicks': 'sum',
        'Impressions': 'sum',
        'Conversions': 'sum',
        'ConversionValue': 'sum' if 'ConversionValue' in df.columns else lambda x: 0
    }).reset_index()
    
    camp_data['CTR'] = np.where(camp_data['Impressions'] > 0, camp_data['Clicks'] / camp_data['Impressions'] * 100, 0)
    camp_data['CPC'] = np.where(camp_data['Clicks'] > 0, camp_data['Spend'] / camp_data['Clicks'], 0)
    camp_data['CPA'] = np.where(camp_data['Conversions'] > 0, camp_data['Spend'] / camp_data['Conversions'], 0)
    camp_data['ROI'] = np.where(camp_data['Spend'] > 0, (camp_data['ConversionValue'] - camp_data['Spend']) / camp_data['Spend'] * 100, 0)
    
    return camp_data

def load_lead_data(client_id=None, filepath="leads_data.csv"):
    """
    Loads processed lead data from CSV.
    If client_id is provided, loads leads_data_{client_id}.csv.
    Otherwise loads default filepath.
    """
    import os
    
    if client_id:
        filepath = f"leads_data_{client_id}.csv"
        
    if os.path.exists(filepath):
        try:
            # Don't force string types - let pandas infer types (integers for IDs)
            return pd.read_csv(filepath)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def merge_api_and_leads(api_df, lead_df):
    """
    Merges API data with Lead data based on Campaign ID and Ad Group/Set ID.
    Logic:
    1. If API data is Granular (has Ad Group/Set ID):
       - Match leads with Ad Group/Set ID to specific rows.
       - Leads with ONLY Campaign ID (no Ad Group/Set ID) are appended as new "Unattributed" rows.
    2. If API data is Campaign Level (no Ad Group/Set ID):
       - Match ALL leads based on Campaign ID.
    """
    if api_df.empty:
        return api_df
        
    if lead_df.empty:
        # Default if no leads uploaded
        api_df['Qualified Leads'] = (api_df['Conversions'] * 0.765).astype(int) # Default estimate
        return api_df
    
    # Ensure ID columns exist
    if 'Campaign ID' not in api_df.columns:
        api_df['Qualified Leads'] = (api_df['Conversions'] * 0.765).astype(int)
        return api_df
        
    api_df = api_df.copy()
    lead_df = lead_df.copy()
    
    # Normalize IDs to integers for proper matching
    # Use regular int with fillna(-1) for missing values to avoid Int64 compatibility issues
    api_df['Campaign ID'] = pd.to_numeric(api_df['Campaign ID'], errors='coerce').fillna(-1).astype(int)
    lead_df['Campaign ID'] = pd.to_numeric(lead_df['Campaign ID'], errors='coerce').fillna(-1).astype(int)
    
    if 'Ad Group ID' in lead_df.columns:
        lead_df['Ad Group ID'] = pd.to_numeric(lead_df['Ad Group ID'], errors='coerce').fillna(-1).astype(int)
    if 'Ad Set ID' in lead_df.columns:
        lead_df['Ad Set ID'] = pd.to_numeric(lead_df['Ad Set ID'], errors='coerce').fillna(-1).astype(int)

    # --- Check API Level ---
    is_google_granular = 'AdGroup ID' in api_df.columns
    is_fb_granular = 'AdSet ID' in api_df.columns
    is_granular = is_google_granular or is_fb_granular

    api_df['Qualified Leads'] = 0

    if not is_granular:
        # --- Campaign Level Merge ---
        # Aggregate ALL leads by Campaign ID
        campaign_leads = lead_df.groupby('Campaign ID').agg(
            Total_Leads=('Lead Stage', 'count'),
            Qualified_Leads=('Is Qualified', 'sum')
        ).reset_index()
        
        merged_df = pd.merge(api_df, campaign_leads, how='left', on='Campaign ID')
        
        mask = merged_df['Total_Leads'].notna()
        merged_df.loc[mask, 'Conversions'] = merged_df.loc[mask, 'Total_Leads']
        merged_df.loc[mask, 'Qualified Leads'] = merged_df.loc[mask, 'Qualified_Leads']
        
        return merged_df.drop(columns=['Total_Leads', 'Qualified_Leads'], errors='ignore')

    else:
        # --- Granular Merge ---
        
        # 1. Google Logic
        if is_google_granular:
            # Convert AdGroup ID to int for matching
            api_df['AdGroup ID'] = pd.to_numeric(api_df['AdGroup ID'], errors='coerce').fillna(-1).astype(int)
            
            # Split leads - filter out -1 (missing) values
            granular_leads = lead_df[lead_df['Ad Group ID'] > 0]
            campaign_only_leads = lead_df[lead_df['Ad Group ID'] <= 0]
            
            # A. Match Granular
            g_leads_agg = granular_leads.groupby(['Campaign ID', 'Ad Group ID']).agg(
                Total_Leads=('Lead Stage', 'count'),
                Qualified_Leads=('Is Qualified', 'sum')
            ).reset_index()
            
            merged_df = pd.merge(api_df, g_leads_agg, how='left', left_on=['Campaign ID', 'AdGroup ID'], right_on=['Campaign ID', 'Ad Group ID'])
            
            mask = merged_df['Total_Leads'].notna()
            merged_df.loc[mask, 'Conversions'] = merged_df.loc[mask, 'Total_Leads']
            merged_df.loc[mask, 'Qualified Leads'] = merged_df.loc[mask, 'Qualified_Leads']
            merged_df = merged_df.drop(columns=['Total_Leads', 'Qualified_Leads', 'Ad Group ID'], errors='ignore')
            
            # B. Append Campaign Only
            if not campaign_only_leads.empty:
                c_leads_agg = campaign_only_leads.groupby('Campaign ID').agg(
                    Total_Leads=('Lead Stage', 'count'),
                    Qualified_Leads=('Is Qualified', 'sum')
                ).reset_index()
                
                # We need to map Campaign ID to Campaign Name for the new rows
                # Create a map from the existing API data
                camp_map = api_df[['Campaign ID', 'Campaign']].drop_duplicates().set_index('Campaign ID')['Campaign'].to_dict()
                
                new_rows = []
                for _, row in c_leads_agg.iterrows():
                    cid = row['Campaign ID']
                    if cid in camp_map and cid > 0: # Only add if campaign exists in API data and is valid
                        new_rows.append({
                            'Date': api_df['Date'].max(), # Assign to latest date? Or min?
                            'Campaign': camp_map[cid],
                            'Campaign ID': cid,
                            'AdGroup': 'Unattributed',
                            'AdGroup ID': -1,  # Use -1 for missing
                            'Source': 'Google Ads',
                            'Impressions': 0,
                            'Clicks': 0,
                            'Spend': 0,
                            'Conversions': row['Total_Leads'],
                            'Qualified Leads': row['Qualified_Leads'],
                            'ConversionValue': 0
                        })
                
                if new_rows:
                    merged_df = pd.concat([merged_df, pd.DataFrame(new_rows)], ignore_index=True)

            return merged_df

        # 2. Facebook Logic
        if is_fb_granular:
            # Convert AdSet ID to int for matching
            api_df['AdSet ID'] = pd.to_numeric(api_df['AdSet ID'], errors='coerce').fillna(-1).astype(int)
            
            # Split leads - filter out -1 (missing) values
            granular_leads = lead_df[lead_df['Ad Set ID'] > 0]
            campaign_only_leads = lead_df[lead_df['Ad Set ID'] <= 0]
            
            # A. Match Granular
            f_leads_agg = granular_leads.groupby(['Campaign ID', 'Ad Set ID']).agg(
                Total_Leads=('Lead Stage', 'count'),
                Qualified_Leads=('Is Qualified', 'sum')
            ).reset_index()
            
            merged_df = pd.merge(api_df, f_leads_agg, how='left', left_on=['Campaign ID', 'AdSet ID'], right_on=['Campaign ID', 'Ad Set ID'])
            
            mask = merged_df['Total_Leads'].notna()
            merged_df.loc[mask, 'Conversions'] = merged_df.loc[mask, 'Total_Leads']
            merged_df.loc[mask, 'Qualified Leads'] = merged_df.loc[mask, 'Qualified_Leads']
            merged_df = merged_df.drop(columns=['Total_Leads', 'Qualified_Leads', 'Ad Set ID_y'], errors='ignore')
            if 'Ad Set ID' in merged_df.columns: merged_df = merged_df.drop(columns=['Ad Set ID'])

            # B. Append Campaign Only
            if not campaign_only_leads.empty:
                c_leads_agg = campaign_only_leads.groupby('Campaign ID').agg(
                    Total_Leads=('Lead Stage', 'count'),
                    Qualified_Leads=('Is Qualified', 'sum')
                ).reset_index()
                
                camp_map = api_df[['Campaign ID', 'Campaign']].drop_duplicates().set_index('Campaign ID')['Campaign'].to_dict()
                
                new_rows = []
                for _, row in c_leads_agg.iterrows():
                    cid = row['Campaign ID']
                    if cid in camp_map and cid > 0:  # Only add if campaign exists and is valid
                        new_rows.append({
                            'Date': api_df['Date'].max(),
                            'Campaign': camp_map[cid],
                            'Campaign ID': cid,
                            'AdSet': 'Unattributed',
                            'AdSet ID': -1,  # Use -1 for missing
                            'Source': 'Facebook Ads',
                            'Impressions': 0,
                            'Clicks': 0,
                            'Spend': 0,
                            'Conversions': row['Total_Leads'],
                            'Qualified Leads': row['Qualified_Leads'],
                            'ConversionValue': 0
                        })
                
                if new_rows:
                    merged_df = pd.concat([merged_df, pd.DataFrame(new_rows)], ignore_index=True)
            
            return merged_df

    return api_df

def get_geographic_data(df):
    """
    Aggregates data by City and State.
    """
    if df.empty:
        return pd.DataFrame()
    
    # Check if City/State columns exist
    if 'City' not in df.columns:
        df['City'] = 'Unknown'
    if 'State' not in df.columns:
        df['State'] = 'Unknown'
        
    geo_data = df.groupby(['City', 'State']).agg({
        'Conversions': 'sum', # Leads
        'Qualified Leads': 'sum' if 'Qualified Leads' in df.columns else lambda x: 0,
        'ConversionValue': 'sum' if 'ConversionValue' in df.columns else lambda x: 0,
        'Spend': 'sum' if 'Spend' in df.columns else lambda x: 0
    }).reset_index()
    
    # Calculate derived metrics
    geo_data['CPL'] = np.where(geo_data['Conversions'] > 0, geo_data['Spend'] / geo_data['Conversions'], 0)
    geo_data['Qualification Rate'] = np.where(geo_data['Conversions'] > 0, 
                                              geo_data['Qualified Leads'] / geo_data['Conversions'] * 100, 0)
    
    return geo_data

def get_keyword_data(df):
    """
    Aggregates data by Keyword.
    """
    if df.empty or 'Keyword' not in df.columns:
        return pd.DataFrame()
        
    kw_data = df.groupby('Keyword').agg({
        'Clicks': 'sum',
        'Impressions': 'sum',
        'Spend': 'sum',
        'Conversions': 'sum',
        'Qualified Leads': 'sum' if 'Qualified Leads' in df.columns else lambda x: 0
    }).reset_index()
    
    kw_data['CTR'] = np.where(kw_data['Impressions'] > 0, kw_data['Clicks'] / kw_data['Impressions'] * 100, 0)
    kw_data['CPC'] = np.where(kw_data['Clicks'] > 0, kw_data['Spend'] / kw_data['Clicks'], 0)
    kw_data['CPL'] = np.where(kw_data['Conversions'] > 0, kw_data['Spend'] / kw_data['Conversions'], 0)
    kw_data['Conv Rate'] = np.where(kw_data['Clicks'] > 0, kw_data['Conversions'] / kw_data['Clicks'] * 100, 0)
    
    return kw_data

def get_ad_performance_data(df):
    """
    Aggregates data by Ad Name/ID.
    """
    if df.empty:
        return pd.DataFrame()
        
    # Determine Ad Identifier
    ad_col = 'Ad Name' if 'Ad Name' in df.columns else ('Ad ID' if 'Ad ID' in df.columns else None)
    
    if not ad_col:
        return pd.DataFrame()
        
    ad_data = df.groupby(ad_col).agg({
        'Spend': 'sum',
        'Impressions': 'sum',
        'Clicks': 'sum',
        'Conversions': 'sum',
        'Qualified Leads': 'sum' if 'Qualified Leads' in df.columns else lambda x: 0,
        'ConversionValue': 'sum' if 'ConversionValue' in df.columns else lambda x: 0
    }).reset_index()
    
    ad_data['CTR'] = np.where(ad_data['Impressions'] > 0, ad_data['Clicks'] / ad_data['Impressions'] * 100, 0)
    ad_data['CPL'] = np.where(ad_data['Conversions'] > 0, ad_data['Spend'] / ad_data['Conversions'], 0)
    ad_data['ROI'] = np.where(ad_data['Spend'] > 0, (ad_data['ConversionValue'] - ad_data['Spend']) / ad_data['Spend'] * 100, 0)
    
    return ad_data

def get_time_trends(df, interval='D'):
    """
    Aggregates data by time interval.
    interval: 'D' (Daily), 'W' (Weekly), 'M' (Monthly)
    """
    if df.empty or 'Date' not in df.columns:
        return pd.DataFrame()
        
    df = df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    
    if interval == 'W':
        df['Period'] = df['Date'].dt.to_period('W').apply(lambda r: r.start_time)
    elif interval == 'M':
        df['Period'] = df['Date'].dt.to_period('M').apply(lambda r: r.start_time)
    else:
        df['Period'] = df['Date']
        
    trend_data = df.groupby('Period').agg({
        'Spend': 'sum',
        'Conversions': 'sum',
        'Qualified Leads': 'sum' if 'Qualified Leads' in df.columns else lambda x: 0,
        'ConversionValue': 'sum' if 'ConversionValue' in df.columns else lambda x: 0,
        'Clicks': 'sum',
        'Impressions': 'sum'
    }).reset_index()
    
    trend_data['CPL'] = np.where(trend_data['Conversions'] > 0, trend_data['Spend'] / trend_data['Conversions'], 0)
    trend_data['CPQL'] = np.where(trend_data['Qualified Leads'] > 0, trend_data['Spend'] / trend_data['Qualified Leads'], 0)
    
    return trend_data

def get_source_stage_data(lead_df):
    """
    Aggregates lead counts by Stage and Source (derived from Campaign/AdGroup).
    Note: This requires leads to be already merged or have source info.
    If leads don't have explicit 'Source' column, we might need to infer it from Campaign/AdGroup ID matching.
    However, for the 'Lead Source Deep Dive', we often start with the merged API+Lead data.
    
    But wait, the 'Stage-wise Lead Analysis' table in the HTML shows counts for EACH stage.
    The merged API data usually only has 'Conversions' (Total Leads) and 'Qualified Leads'.
    It doesn't have a row for every single lead stage unless we use the raw lead_df.
    
    So this function should work on the raw `lead_df` but needs to know the Source of each lead.
    We can infer Source from 'Campaign ID' if we have a map, or if 'Source' is in lead_df.
    """
    if lead_df.empty:
        return pd.DataFrame()
        
    # If 'Source' is not in lead_df, we can't easily break down by source without joining with API data.
    # But we can try to infer from 'Platform' or 'Source' column if it exists.
    # Or we rely on the fact that we usually merge this later.
    
    # Let's assume we can pass a dataframe that HAS 'Source' and 'Lead Stage'.
    # If not, we return a simple stage breakdown.
    
    if 'Source' not in lead_df.columns:
        # Fallback: just group by stage
        return lead_df['Lead Stage'].value_counts().reset_index()
        
    stage_data = lead_df.groupby(['Lead Stage', 'Source']).size().reset_index(name='Count')
    return stage_data

def get_campaign_service_map(lead_df, service_col=None):
    """
    Creates a mapping from Campaign ID to Service/Product based on lead data.
    service_col: Optional column name to use for Service/Product.
    """
    if lead_df.empty:
        return {}
        
    # Determine which column to use
    target_col = 'Service'
    if service_col and service_col in lead_df.columns:
        target_col = service_col
    elif 'Service' in lead_df.columns:
        target_col = 'Service'
    elif 'Product' in lead_df.columns:
        target_col = 'Product'
    else:
        return {}
        
    campaign_service_map = {}
    # Group by Campaign ID and find mode of Service
    if 'Campaign ID' in lead_df.columns:
        for cid, group in lead_df.groupby('Campaign ID'):
            if not group[target_col].empty:
                # Use mode (most frequent) service for this campaign
                try:
                    # Drop NA values before finding mode
                    valid_values = group[target_col].dropna()
                    if not valid_values.empty:
                        top_service = valid_values.mode()[0]
                        campaign_service_map[int(cid)] = top_service
                except (IndexError, ValueError):
                    continue
                    
    return campaign_service_map

def get_service_performance_data(combined_df, service_map):
    """
    Aggregates performance metrics by Service/Product.
    """
    if combined_df.empty:
        return pd.DataFrame()
        
    df = combined_df.copy()
    
    # Ensure Campaign ID is present and integer
    if 'Campaign ID' in df.columns:
        df['Campaign ID'] = pd.to_numeric(df['Campaign ID'], errors='coerce').fillna(-1).astype(int)
        # Map Service
        df['Service'] = df['Campaign ID'].map(service_map).fillna("Unassigned")
    else:
        df['Service'] = "Unassigned"
        
    # Group
    service_stats = df.groupby('Service').agg({
        'Spend': 'sum',
        'Conversions': 'sum',
        'Qualified Leads': 'sum' if 'Qualified Leads' in df.columns else lambda x: 0,
        'ConversionValue': 'sum' if 'ConversionValue' in df.columns else lambda x: 0,
        'Clicks': 'sum',
        'Impressions': 'sum'
    }).reset_index()
    
    # Metrics
    service_stats['CPA'] = np.where(service_stats['Conversions'] > 0, service_stats['Spend'] / service_stats['Conversions'], 0)
    service_stats['CPC'] = np.where(service_stats['Clicks'] > 0, service_stats['Spend'] / service_stats['Clicks'], 0)
    service_stats['CTR'] = np.where(service_stats['Impressions'] > 0, service_stats['Clicks'] / service_stats['Impressions'] * 100, 0)
    service_stats['ROAS'] = np.where(service_stats['Spend'] > 0, service_stats['ConversionValue'] / service_stats['Spend'], 0)
    service_stats['Conv Rate'] = np.where(service_stats['Clicks'] > 0, service_stats['Conversions'] / service_stats['Clicks'] * 100, 0)
    
    # Pipeline Value (Estimated as Revenue * 0.8 for now, or just Revenue)
    # The HTML template had "Pipeline Value" separate from Revenue. 
    # We'll just use Revenue (ConversionValue) for now as we don't have open deal value.
    service_stats['Pipeline Value'] = service_stats['ConversionValue'] 
    
    return service_stats
