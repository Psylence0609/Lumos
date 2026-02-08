#!/usr/bin/env python3
"""Google Calendar OAuth setup script.

This script runs the OAuth flow to get an access token for Google Calendar.
Run this once to authenticate and save the token.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import settings

# Scopes required for Google Calendar read-only access
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Path to save the token
TOKEN_PATH = project_root / "token.json"
CREDENTIALS_PATH = project_root / "credentials.json"


def main():
    """Run the OAuth flow and save the token."""
    creds = None

    # Check if token already exists
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # If no valid credentials, run the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh the token
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            # Run the OAuth flow
            print("Starting OAuth flow...")
            print(f"Client ID: {settings.google_client_id[:20]}...")

            if not settings.google_client_id or settings.google_client_id == "your_google_client_id_here":
                print("\n❌ ERROR: Google Client ID not configured!")
                print("Please set GOOGLE_CLIENT_ID in your .env file")
                sys.exit(1)

            # Create flow from client ID and secret
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": [
                            "http://localhost:8080/",
                            "urn:ietf:wg:oauth:2.0:oob",
                        ],
                    }
                },
                SCOPES,
            )

            # Run the flow (opens browser for authentication)
            print("\n browser will open for authentication...")
            print("   If it doesn't open, copy the URL from the terminal")
            creds = flow.run_local_server(port=8080)

        # Save the token for future use
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"\n✅ Token saved to {TOKEN_PATH}")

    print("\n✅ Google Calendar OAuth setup complete!")
    print("   The token will be used automatically by the calendar client.")


if __name__ == "__main__":
    main()