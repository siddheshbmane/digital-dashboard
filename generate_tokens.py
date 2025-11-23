import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    print("🚀 Google Ads Refresh Token Generator")
    print("-------------------------------------")
    print("This script will help you generate a Refresh Token for Streamlit Cloud.")
    print("You need your Client ID and Client Secret from the Google Cloud Console.")
    print("")

    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()

    if not client_id or not client_secret:
        print("❌ Error: Client ID and Secret are required.")
        return

    # Create a temporary client config
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    scopes = ["https://www.googleapis.com/auth/adwords"]

    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
        print("\n⏳ Opening browser for authentication...")
        creds = flow.run_local_server(port=0)
        
        print("\n✅ Authentication Successful!")
        print("-------------------------------------")
        print(f"Refresh Token: {creds.refresh_token}")
        print("-------------------------------------")
        print("\n👉 Copy the Refresh Token above and paste it into your Streamlit Cloud Secrets (or credentials.json).")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
