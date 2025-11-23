import streamlit as st
import pandas as pd
import os
from utils.data_processing import apply_qualification_rules

# Page Config
st.set_page_config(
    page_title="Lead Upload",
    page_icon="📥",
    layout="wide"
)

st.title("📥 Upload Lead Data")
st.markdown("Upload your lead sheet to match leads with campaign data.")

# Sidebar
st.sidebar.header("Configuration")
from utils.auth_helper import render_client_selector
render_client_selector()

from utils.auth_helper import get_context_credentials
_, _, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Uploading leads here will save them to a shared file.")
    st.info("It is recommended to select a specific client before uploading to ensure data consistency.")
    # We don't stop here, just warn, as the user might want to upload a master sheet.

# --- Client Context ---
client_id = st.session_state.get('selected_client_id')
if client_id == "ALL":
    client_id = None # Fallback to default if ALL is selected (though warned)

# Determine File Path
if client_id:
    LEADS_FILE = f"leads_data_{client_id}.csv"
else:
    LEADS_FILE = "leads_data.csv"


# Load Client Config for Pre-selection
from utils.client_manager import load_clients, update_client_config
clients = load_clients()
current_client = next((c for c in clients if c['id'] == client_id), None)
saved_qualified_stages = current_client.get('qualified_stages', []) if current_client else []

# Debug: Show loaded config in sidebar
if client_id and current_client:
    with st.sidebar.expander("🔍 Debug: Loaded Config", expanded=False):
        st.write(f"**Client ID:** {client_id}")
        st.write(f"**Qualified Stages:** {saved_qualified_stages}")
        st.write(f"**Service Column:** {current_client.get('service_column', 'Not set')}")

# --- Constants ---
REQUIRED_COLUMNS = ["Campaign ID", "Lead Stage"]
# Note: "Ad Group ID" or "Ad Set ID" is also required but we check for either.

# --- File Uploader ---
uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.write("Preview:")
        st.dataframe(df.head())

        # --- UTM Extraction ---
        if 'UTM URL' in df.columns:
            st.info("Found 'UTM URL' column. Attempting to extract IDs...")
            from urllib.parse import urlparse, parse_qs

            def extract_ids(url):
                """
                Extract Campaign ID, Ad Group ID, and Ad ID from UTM URL.
                Returns integers for proper matching with API data.
                """
                try:
                    if pd.isna(url) or url == '':
                        return pd.Series([None, None, None])
                    
                    parsed = urlparse(str(url))
                    params = parse_qs(parsed.query)
                    
                    # Extract parameters (first value if list)
                    campaign_id_str = params.get('utm_campaign', [None])[0]
                    adgroup_id_str = params.get('utm_adgroup', [None])[0]
                    ad_id_str = params.get('utm_adid', [None])[0]
                    
                    # Convert to integers for proper matching with API data
                    campaign_id = None
                    adgroup_id = None
                    ad_id = None
                    
                    if campaign_id_str:
                        try:
                            # Remove any non-numeric characters and convert to int
                            campaign_id = int(''.join(filter(str.isdigit, str(campaign_id_str))))
                        except (ValueError, TypeError):
                            campaign_id = None
                    
                    if adgroup_id_str:
                        try:
                            adgroup_id = int(''.join(filter(str.isdigit, str(adgroup_id_str))))
                        except (ValueError, TypeError):
                            adgroup_id = None
                    
                    if ad_id_str:
                        try:
                            ad_id = int(''.join(filter(str.isdigit, str(ad_id_str))))
                        except (ValueError, TypeError):
                            ad_id = None
                    
                    return pd.Series([campaign_id, adgroup_id, ad_id])
                except Exception as e:
                    return pd.Series([None, None, None])

            extracted = df['UTM URL'].apply(extract_ids)
            extracted.columns = ['Extracted Campaign ID', 'Extracted Ad Group ID', 'Extracted Ad ID']
            
            # Show extraction preview
            st.write("**UTM Extraction Preview:**")
            preview_df = pd.DataFrame({
                'UTM URL': df['UTM URL'].head(),
                'Campaign ID': extracted['Extracted Campaign ID'].head(),
                'Ad Group ID': extracted['Extracted Ad Group ID'].head(),
                'Ad ID': extracted['Extracted Ad ID'].head()
            })
            st.dataframe(preview_df)
            
            # Count successful extractions
            campaign_extracted = extracted['Extracted Campaign ID'].notna().sum()
            adgroup_extracted = extracted['Extracted Ad Group ID'].notna().sum()
            ad_extracted = extracted['Extracted Ad ID'].notna().sum()
            
            st.success(f"✅ Extracted {campaign_extracted} Campaign IDs, {adgroup_extracted} Ad Group IDs, {ad_extracted} Ad IDs")
            
            # Fill/Create Campaign ID
            if 'Campaign ID' not in df.columns:
                df['Campaign ID'] = extracted['Extracted Campaign ID']
            else:
                df['Campaign ID'] = df['Campaign ID'].fillna(extracted['Extracted Campaign ID'])
            
            # Fill/Create Ad Group ID (Google)
            if 'Ad Group ID' not in df.columns:
                df['Ad Group ID'] = extracted['Extracted Ad Group ID']
            else:
                df['Ad Group ID'] = df['Ad Group ID'].fillna(extracted['Extracted Ad Group ID'])

            # Fill/Create Ad Set ID (Meta) - map utm_adgroup to this too
            if 'Ad Set ID' not in df.columns:
                df['Ad Set ID'] = extracted['Extracted Ad Group ID']
            else:
                df['Ad Set ID'] = df['Ad Set ID'].fillna(extracted['Extracted Ad Group ID'])
            
            # Fill/Create Ad ID (if column exists or create it)
            if 'Ad ID' not in df.columns:
                df['Ad ID'] = extracted['Extracted Ad ID']
            else:
                df['Ad ID'] = df['Ad ID'].fillna(extracted['Extracted Ad ID'])
                
            st.success("UTM Extraction Complete. Updated Preview:")
            st.dataframe(df.head())
        
        # --- Validation ---
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        
        has_ad_group_id = "Ad Group ID" in df.columns
        has_ad_set_id = "Ad Set ID" in df.columns
        
        if missing_cols:
            st.error(f"Missing required columns: {', '.join(missing_cols)}")
        elif not (has_ad_group_id or has_ad_set_id):
             st.error("Missing required column: 'Ad Group ID' (for Google) or 'Ad Set ID' (for Facebook).")
        else:
            # --- Processing ---
            st.success("File validation successful!")
            
            # --- Advanced Validation ---
            validation_warnings = []
            
            # 1. Missing Campaign IDs
            if 'Campaign ID' in df.columns:
                # Check for NaN, 0, or -1 (after potential extraction/filling)
                # Note: extraction happens before this, so we check the current state
                missing_cid = pd.to_numeric(df['Campaign ID'], errors='coerce').fillna(0).eq(0) | \
                              pd.to_numeric(df['Campaign ID'], errors='coerce').eq(-1)
                missing_count = missing_cid.sum()
                if missing_count > 0:
                    pct = (missing_count / len(df)) * 100
                    if pct > 5: # Warn if > 5% missing
                        validation_warnings.append(f"⚠️ **Missing Campaign IDs**: {missing_count} rows ({pct:.1f}%) are missing Campaign IDs. These leads won't be attributed to campaigns.")

            # 2. Duplicate Leads
            # Try to find a unique identifier
            unique_cols = [c for c in df.columns if 'lead' in c.lower() and 'id' in c.lower()] # e.g. Lead ID
            if not unique_cols:
                unique_cols = [c for c in df.columns if 'email' in c.lower() or 'phone' in c.lower()]
            
            if unique_cols:
                # Use the first one found as primary key for check
                pk = unique_cols[0]
                duplicates = df[pk].duplicated().sum()
                if duplicates > 0:
                    validation_warnings.append(f"⚠️ **Duplicate Leads**: Found {duplicates} duplicate entries based on column '{pk}'.")
            
            if validation_warnings:
                with st.expander("⚠️ Validation Warnings", expanded=True):
                    for w in validation_warnings:
                        st.markdown(w)
            
            # Normalize Lead Stage for Selection
            df['Lead Stage Normalized'] = df['Lead Stage'].astype(str).str.strip().str.lower()
            unique_stages = sorted(df['Lead Stage Normalized'].unique().tolist())
            
            # Dynamic Qualification Selection
            st.subheader("Define Qualified Leads")
            st.markdown("Select which lead stages should be considered as **Qualified Leads**.")
            
            # Pre-select if saved, otherwise default to common ones if found
            default_stages = ["admission", "interested", "prospect", "walk-in"]
            pre_selected = [s for s in unique_stages if s in saved_qualified_stages]
            if not pre_selected and not saved_qualified_stages:
                 pre_selected = [s for s in unique_stages if s in default_stages]
            
            selected_stages = st.multiselect(
                "Select Qualified Stages",
                options=unique_stages,
                default=pre_selected
            )

            # --- Service/Product Column Mapping ---
            st.subheader("Map Service/Product")
            st.markdown("Select the column that identifies the **Service** or **Product**.")
            
            # Try to auto-detect "Service" or "Product" or "Course"
            potential_service_cols = [c for c in df.columns if "service" in c.lower() or "product" in c.lower() or "course" in c.lower()]
            default_service_index = df.columns.get_loc(potential_service_cols[0]) if potential_service_cols else 0
            
            service_col = st.selectbox(
                "Select Service Column",
                options=["None"] + list(df.columns),
                index=default_service_index + 1 if potential_service_cols else 0
            )
            
            if st.button("Process and Save Leads"):
                # Normalize ID columns to integers for proper API matching
                # Use fillna(-1) for missing values to avoid Int64 compatibility issues
                if has_ad_group_id and not has_ad_set_id:
                    df['Ad Group ID'] = pd.to_numeric(df['Ad Group ID'], errors='coerce').fillna(-1).astype(int)
                    df['Ad Set ID'] = -1
                elif has_ad_set_id and not has_ad_group_id:
                    df['Ad Set ID'] = pd.to_numeric(df['Ad Set ID'], errors='coerce').fillna(-1).astype(int)
                    df['Ad Group ID'] = -1
                else:
                    df['Ad Group ID'] = pd.to_numeric(df['Ad Group ID'], errors='coerce').fillna(-1).astype(int)
                    df['Ad Set ID'] = pd.to_numeric(df['Ad Set ID'], errors='coerce').fillna(-1).astype(int)
                
                df['Campaign ID'] = pd.to_numeric(df['Campaign ID'], errors='coerce').fillna(-1).astype(int)
                
                # Convert Ad ID if present
                if 'Ad ID' in df.columns:
                    df['Ad ID'] = pd.to_numeric(df['Ad ID'], errors='coerce').fillna(-1).astype(int)
                
                # Show ID conversion summary
                st.info(f"**ID Conversion Summary:**")
                id_summary_cols = st.columns(3)
                id_summary_cols[0].metric("Campaign IDs", (df['Campaign ID'] > 0).sum())
                id_summary_cols[1].metric("Ad Group/Set IDs", 
                                          ((df['Ad Group ID'] > 0).sum() + (df['Ad Set ID'] > 0).sum()))
                if 'Ad ID' in df.columns:
                    id_summary_cols[2].metric("Ad IDs", (df['Ad ID'] > 0).sum())
                
                # Apply Qualification Logic
                stage_mask = df['Lead Stage Normalized'].isin(selected_stages)
                
                # Apply saved qualification rules
                saved_qual_rules = current_client.get('qualification_rules', []) if current_client else []
                rule_mask = apply_qualification_rules(df, saved_qual_rules)
                
                df['Is Qualified'] = stage_mask | rule_mask
                
                # Apply Service Mapping
                # 1. Column Mapping
                if service_col and service_col != "None":
                    df['Service'] = df[service_col].astype(str).str.strip()
                else:
                    df['Service'] = "Unassigned"

                # 2. Regex Mapping (Overwrite)
                saved_regex_rules = current_client.get('service_regex_rules', []) if current_client else []
                if saved_regex_rules and 'Campaign' in df.columns:
                    import re
                    for rule in saved_regex_rules:
                        pattern = rule.get('pattern')
                        service = rule.get('service')
                        if pattern and service:
                            try:
                                # Apply regex to Campaign column
                                mask = df['Campaign'].astype(str).str.contains(pattern, case=False, regex=True, na=False)
                                df.loc[mask, 'Service'] = service
                            except Exception:
                                continue

                # Save Config (if client selected)
                if client_id:
                    config_update = {'qualified_stages': selected_stages}
                    if service_col != "None":
                        config_update['service_column'] = service_col
                    update_client_config(client_id, config_update)
                    st.toast("Configuration saved!", icon="💾")
                
                # Debug: Show found stages and sample classification
                st.info(f"Qualified Stages: {selected_stages}")
                st.write("Sample Classification Preview:")
                st.dataframe(df[['Lead Stage', 'Lead Stage Normalized', 'Is Qualified']].head())
                
                # Save File
                df.to_csv(LEADS_FILE, index=False)
                st.success(f"Successfully saved {len(df)} leads to {LEADS_FILE}")
                
                # Show Summary
                st.subheader("Upload Summary")
                col1, col2 = st.columns(2)
                col1.metric("Total Leads", len(df))
                col2.metric("Qualified Leads", df['Is Qualified'].sum())
                
                st.dataframe(df['Lead Stage'].value_counts().reset_index().rename(columns={'index': 'Stage', 'Lead Stage': 'Count'}))

    except Exception as e:
        st.error(f"Error processing file: {e}")

# --- Update Existing Qualification & Service Mapping ---
if os.path.exists(LEADS_FILE):
    # Always show this section if file exists, but maybe collapse it if uploading?
    # User asked for it to be accessible "at all times".
    # Let's put it in an expander if a file is being uploaded, or just show it below.
    # Actually, if uploading, we are replacing data, so this section applies to the OLD data.
    # But if not uploading, it applies to CURRENT data.
    
    st.markdown("---")
    with st.expander("⚙️ Manage Lead Configuration (Qualification & Service Mapping)", expanded=(uploaded_file is None)):
        st.markdown("Update the qualification criteria and service mapping for your **existing** lead data.")
        
        try:
            existing_df = pd.read_csv(LEADS_FILE)
            
            # Ensure normalized column exists
            if 'Lead Stage Normalized' not in existing_df.columns:
                existing_df['Lead Stage Normalized'] = existing_df['Lead Stage'].astype(str).str.strip().str.lower()
                
            unique_stages = sorted([str(s) for s in existing_df['Lead Stage Normalized'].unique().tolist() if pd.notna(s)])
            
            # Pre-select based on saved config
            pre_selected = [s for s in unique_stages if s in saved_qualified_stages]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("1. Qualification")
                new_selected_stages = st.multiselect(
                    "Update Qualified Stages",
                    options=unique_stages,
                    default=pre_selected,
                    key="update_stages"
                )
            
            with col2:
                st.subheader("2. Service Mapping")
                # Try to find current service column from config or guess
                current_service_col = current_client.get('service_column') if current_client else None
                
                # If not in config, try to guess from columns
                if not current_service_col:
                     potential = [c for c in existing_df.columns if "service" in c.lower() or "product" in c.lower()]
                     current_service_col = potential[0] if potential else "None"
                
                # Ensure it exists in df
                if current_service_col not in existing_df.columns and current_service_col != "None":
                    current_service_col = "None"
                    
                options = ["None"] + list(existing_df.columns)
                try:
                    idx = options.index(current_service_col) if current_service_col else 0
                except:
                    idx = 0
                    
                new_service_col = st.selectbox(
                    "Update Service Column",
                    options=options,
                    index=idx,
                    key="update_service_col"
                )
            
            # 3. Regex Mapping (New Row)
            st.markdown("---")
            st.subheader("3. Advanced: Regex Service Mapping")
            st.markdown("Map campaigns to services based on name patterns (Regex). **Priority over column mapping.**")
            
            current_rules = current_client.get('service_regex_rules', [])
            # Convert to DF for editor
            rules_df = pd.DataFrame(current_rules)
            if rules_df.empty:
                rules_df = pd.DataFrame(columns=['pattern', 'service'])
            
            edited_rules_df = st.data_editor(
                rules_df,
                num_rows="dynamic",
                column_config={
                    "pattern": st.column_config.TextColumn("Campaign Name Pattern (Regex)", help="e.g. '(?i)ppc' for case-insensitive 'ppc'"),
                    "service": st.column_config.TextColumn("Service Name", help="Target Service Name")
                },
                use_container_width=True,
                key="regex_rules_editor"
            )
            
            # 4. Qualification Rules (New Row)
            st.markdown("---")
            st.subheader("4. Advanced: Qualification Rules")
            st.markdown("Define additional rules to qualify leads. Leads matching **ANY** of these rules (or the selected stages) will be qualified.")
            
            current_qual_rules = current_client.get('qualification_rules', [])
            qual_rules_df = pd.DataFrame(current_qual_rules)
            if qual_rules_df.empty:
                qual_rules_df = pd.DataFrame(columns=['field', 'operator', 'value'])
            
            # Get columns for dropdown if possible
            field_options = list(existing_df.columns) if not existing_df.empty else []
            
            edited_qual_rules_df = st.data_editor(
                qual_rules_df,
                num_rows="dynamic",
                column_config={
                    "field": st.column_config.SelectboxColumn("Field", options=field_options, required=True),
                    "operator": st.column_config.SelectboxColumn("Operator", options=["equals", "contains", "greater_than", "less_than", "not_equals"], required=True),
                    "value": st.column_config.TextColumn("Value", required=True)
                },
                use_container_width=True,
                key="qual_rules_editor"
            )

            if st.button("Update Configuration"):
                # Get rules from editors
                new_regex_rules = edited_rules_df.to_dict('records')
                new_regex_rules = [r for r in new_regex_rules if r['pattern'] and r['service']]
                
                new_qual_rules = edited_qual_rules_df.to_dict('records')
                new_qual_rules = [r for r in new_qual_rules if r['field'] and r['operator'] and r['value']]

                # 1. Apply Qualification (Stages OR Rules)
                stage_mask = existing_df['Lead Stage Normalized'].isin(new_selected_stages)
                rule_mask = apply_qualification_rules(existing_df, new_qual_rules)
                existing_df['Is Qualified'] = stage_mask | rule_mask
                
                # 2. Apply Service Mapping
                if new_service_col and new_service_col != "None":
                    existing_df['Service'] = existing_df[new_service_col].astype(str).str.strip()
                else:
                    existing_df['Service'] = "Unassigned"
                
                # Save Config
                if client_id:
                    config_update = {'qualified_stages': new_selected_stages}
                    if new_service_col != "None":
                        config_update['service_column'] = new_service_col
                    
                    # Get rules from editor
                    config_update['service_regex_rules'] = new_regex_rules
                    config_update['qualification_rules'] = new_qual_rules
                    
                    success = update_client_config(client_id, config_update)
                    
                    if success:
                        st.success(f"✅ Configuration saved for client: {client_id}")
                        st.info(f"**Saved Settings:**\n- Qualified Stages: {new_selected_stages}\n- Service Column: {new_service_col}\n- Regex Rules: {len(new_regex_rules)}\n- Qual Rules: {len(new_qual_rules)}")
                        st.toast("Configuration updated!", icon="💾")
                    else:
                        st.error(f"Failed to save configuration for client: {client_id}")
                else:
                    st.warning("No client selected. Configuration not saved to client profile.")
                
                # Save File with updated qualification
                existing_df.to_csv(LEADS_FILE, index=False)
                
                # Show updated counts
                qualified_count = existing_df['Is Qualified'].sum()
                total_count = len(existing_df)
                st.success(f"Lead data updated! {qualified_count} out of {total_count} leads are now qualified.")
                
                # Rerun to refresh the page with new config
                st.rerun()
                
        except Exception as e:
            st.error(f"Error loading existing data: {e}")
            import traceback
            st.code(traceback.format_exc())

# --- Existing Data ---
if os.path.exists(LEADS_FILE):
    st.markdown("---")
    st.subheader(f"Current Stored Lead Data ({'Client Specific' if client_id else 'Shared'})")
    stored_df = pd.read_csv(LEADS_FILE)
    st.dataframe(stored_df)
