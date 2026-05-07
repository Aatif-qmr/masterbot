import os
import json
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_PATH = os.path.expanduser("~/.qnt/oauth_creds.json")

def get_credentials():
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"OAuth credentials not found at {TOKEN_PATH}")
    
    with open(TOKEN_PATH, 'r') as f:
        creds_data = json.load(f)
    
    creds = Credentials(
        token=creds_data.get('access_token'),
        refresh_token=creds_data.get('refresh_token'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id="681255809395-oo8ft2oprdrup9e3aqf6av3hmdib135j.apps.googleusercontent.com",
        scopes=creds_data.get('scope', '').split(' ')
    )
    
    if creds.expired:
        creds.refresh(Request())
        
    return creds

def create_sheet():
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        
        sheet_name = "MasterBot Test Sheet"
        sh = gc.create(sheet_name)
        
        print(f"Successfully created sheet: {sheet_name}")
        print(f"URL: https://docs.google.com/spreadsheets/d/{sh.id}")
        print(f"ID: {sh.id}")
        
    except Exception as e:
        print(f"Failed to create sheet: {e}")

if __name__ == "__main__":
    create_sheet()
