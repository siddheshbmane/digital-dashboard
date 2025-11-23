import streamlit as st
from utils.config_manager import load_credentials, save_credentials
from utils.auth_manager import AuthManager

st.set_page_config(page_title="Connections", page_icon="🔗", layout="wide")

st.title("🔗 Data Connections")
st.markdown("Connect your ad platforms to start fetching data.")

auth_manager = AuthManager()
saved_creds = load_credentials()

# --- Google Ads ---
st.header("Google Ads")
with st.container(border=True):
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Configuration")
        # We still need Client ID/Secret to initiate the flow
        g_saved = saved_creds.get("google", {})
        client_id = st.text_input("Client ID", value=g_saved.get("client_id", ""), type="password", key="g_client_id")
        client_secret = st.text_input("Client Secret", value=g_saved.get("client_secret", ""), type="password", key="g_client_secret")
        developer_token = st.text_input("Developer Token", value=g_saved.get("developer_token", ""), type="password", key="g_dev_token")
        
        # Optional: Manual Refresh Token Entry (for Cloud users who can't use the button)
        st.markdown("**OR**")
        manual_refresh = st.text_input("Refresh Token (Manual Entry)", value=g_saved.get("refresh_token", ""), type="password", help="Paste your Refresh Token here if you are on Cloud.", key="g_manual_refresh")
        
        if st.button("Sign in with Google"):
            if not client_id or not client_secret or not developer_token:
                st.error("Please enter Client ID, Client Secret, and Developer Token.")
            else:
                # Check for manual refresh token first
                if manual_refresh:
                    st.success("Using manually entered Refresh Token.")
                    temp_creds = {
                        "developer_token": developer_token,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": manual_refresh
                    }
                    if "google" not in saved_creds: saved_creds["google"] = {}
                    saved_creds["google"].update(temp_creds)
                    save_credentials(saved_creds)
                    st.rerun()
                else:
                    with st.spinner("Opening browser for authentication..."):
                        config = {"client_id": client_id, "client_secret": client_secret}
                        refresh_token = auth_manager.google_oauth_flow(config)
                        
                        if refresh_token:
                            st.success("Authentication successful!")
                            # Save preliminary creds to session state or file to use for fetching accounts
                            temp_creds = {
                                "developer_token": developer_token,
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "refresh_token": refresh_token
                            }
                            # Update saved creds structure
                            if "google" not in saved_creds: saved_creds["google"] = {}
                            saved_creds["google"].update(temp_creds)
                            save_credentials(saved_creds)
                            st.rerun()

    with col2:
        st.subheader("Account Selection")
        if saved_creds.get("google", {}).get("refresh_token"):
            st.success("✅ Connected to Google Ads")
            
            # Fetch Accounts
            if st.button("Refresh Accounts", key="g_refresh"):
                accounts = auth_manager.get_google_accounts(saved_creds["google"])
                st.session_state["google_accounts"] = accounts
            
            accounts = st.session_state.get("google_accounts", [])
            if not accounts:
                 # Try to load if not in session but we have creds
                 accounts = auth_manager.get_google_accounts(saved_creds["google"])
                 st.session_state["google_accounts"] = accounts

            if accounts:
                # Create a map for display
                account_map = {f"{acc['name']} ({acc['id']}) {'[Manager]' if acc['is_manager'] else ''}": acc for acc in accounts}
                options = list(account_map.keys())
                
                # Determine default index for main account
                saved_customer_id = saved_creds.get("google", {}).get("customer_id")
                saved_login_id = saved_creds.get("google", {}).get("login_customer_id")
                
                # If we have a login_customer_id, it means the main account selected was the Manager
                # If not, the main account was the Client (customer_id)
                target_main_id = saved_login_id if saved_login_id else saved_customer_id
                
                default_index = 0
                if target_main_id:
                    for i, name in enumerate(options):
                        if account_map[name]['id'] == target_main_id:
                            default_index = i
                            break

                selected_name = st.selectbox("Select Ad Account", options=options, index=default_index, key="g_select")
                
                selected_acc = account_map[selected_name]
                
                final_customer_id = selected_acc['id']
                login_customer_id = None
                
                # If it's a manager, allow selecting a sub-account
                if selected_acc['is_manager']:
                    st.info(f"Selected Manager Account: {selected_acc['name']}. Fetching sub-accounts...")
                    
                    # Fetch sub-accounts
                    manager_id = selected_acc['id']
                    cache_key = f"g_subs_{manager_id}"
                    
                    if cache_key not in st.session_state or st.button("Refresh Sub-accounts"):
                        sub_accounts = auth_manager.get_google_sub_accounts(manager_id, saved_creds["google"])
                        st.session_state[cache_key] = sub_accounts
                    
                    sub_accounts = st.session_state.get(cache_key, [])
                    
                    if sub_accounts:
                        sub_map = {f"{sub['name']} ({sub['id']})": sub for sub in sub_accounts}
                        sub_options = list(sub_map.keys())
                        
                        # Determine default index for sub-account
                        sub_default_index = 0
                        if saved_customer_id:
                            for i, name in enumerate(sub_options):
                                if sub_map[name]['id'] == saved_customer_id:
                                    sub_default_index = i
                                    break
                        
                        selected_sub_name = st.selectbox("Select Client Account", options=sub_options, index=sub_default_index, key="g_sub_select")
                        selected_sub = sub_map[selected_sub_name]
                        
                        final_customer_id = selected_sub['id']
                        login_customer_id = manager_id # We access sub-account VIA the manager
                        st.success(f"Selected Client: {selected_sub['name']}")
                    else:
                        st.warning("No enabled sub-accounts found for this Manager.")
                
                if st.button("Save Google Configuration", key="g_save_btn"):
                    saved_creds["google"]["customer_id"] = final_customer_id
                    if login_customer_id:
                        saved_creds["google"]["login_customer_id"] = login_customer_id
                    else:
                        # Clear it if not needed, to avoid stale data
                        saved_creds["google"].pop("login_customer_id", None)
                        
                    if save_credentials(saved_creds):
                        st.success("Configuration Saved Successfully!")
                        st.toast("Google Configuration Saved!", icon="✅")
                    else:
                        st.error("Failed to save configuration.")
            else:
                st.warning("No accounts found or failed to fetch.")
        else:
            st.info("Sign in to select accounts.")

# --- Facebook Ads ---
st.header("Facebook Ads")
with st.container(border=True):
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Configuration")
        f_saved = saved_creds.get("facebook", {})
        app_id = st.text_input("App ID", value=f_saved.get("app_id", ""), key="f_app_id")
        app_secret = st.text_input("App Secret", value=f_saved.get("app_secret", ""), type="password", key="f_app_secret")
        # Facebook User Access Token is usually manual for server-side apps unless we implement a full web flow
        access_token = st.text_input("User Access Token", value=f_saved.get("access_token", ""), type="password", help="Generate this from Graph API Explorer", key="f_token")
        
        if st.button("Connect Facebook"):
            if not app_id or not app_secret or not access_token:
                st.error("Please enter App ID, App Secret, and Access Token.")
            else:
                # Verify token works
                temp_creds = {"app_id": app_id, "app_secret": app_secret, "access_token": access_token}
                accounts = auth_manager.get_facebook_accounts(temp_creds)
                
                if accounts:
                    st.success("Authentication successful!")
                    if "facebook" not in saved_creds: saved_creds["facebook"] = {}
                    saved_creds["facebook"].update(temp_creds)
                    save_credentials(saved_creds)
                    st.session_state["fb_accounts"] = accounts
                    st.rerun()
                else:
                    st.error("Failed to connect or no accounts found.")

    with col2:
        st.subheader("Account Selection")
        if saved_creds.get("facebook", {}).get("access_token"):
            st.success("✅ Connected to Facebook")
            
            if st.button("Refresh Accounts", key="f_refresh"):
                accounts = auth_manager.get_facebook_accounts(saved_creds["facebook"])
                st.session_state["fb_accounts"] = accounts
            
            accounts = st.session_state.get("fb_accounts", [])
            if not accounts:
                 accounts = auth_manager.get_facebook_accounts(saved_creds["facebook"])
                 st.session_state["fb_accounts"] = accounts

            if accounts:
                account_map = {f"{acc['name']} ({acc['id']})": acc for acc in accounts}
                options = list(account_map.keys())
                
                saved_ad_account_id = saved_creds.get("facebook", {}).get("ad_account_id")
                default_index = 0
                if saved_ad_account_id:
                    for i, name in enumerate(options):
                        if account_map[name]['id'] == saved_ad_account_id:
                            default_index = i
                            break
                
                selected_name = st.selectbox("Select Ad Account", options=options, index=default_index, key="f_select")
                
                selected_acc = account_map[selected_name]
                st.info(f"Selected: {selected_acc['name']}")
                
                if st.button("Save Facebook Configuration", key="f_save_btn"):
                    saved_creds["facebook"]["ad_account_id"] = selected_acc['id']
                    if save_credentials(saved_creds):
                        st.success("Configuration Saved Successfully!")
                        st.toast("Facebook Configuration Saved!", icon="✅")
                    else:
                        st.error("Failed to save configuration.")
        else:
            st.info("Connect to select accounts.")
