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
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
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

            # Try to detect client type and create appropriate flow
            # First, try as Installed App (Desktop app)
            try:
                print("Attempting OAuth flow as Desktop/Installed app...")
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
                print("\n✅ Browser will open for authentication...")
                print("   If it doesn't open, copy the URL from the terminal")
                creds = flow.run_local_server(port=8080)
            except Exception as e:
                # If installed app fails, try as Web application
                if "invalid_client" in str(e).lower() or "401" in str(e):
                    print(f"\n⚠️  Installed app flow failed: {e}")
                    print("Trying as Web application client...")
                    try:
                        flow = Flow.from_client_config(
                            {
                                "web": {
                                    "client_id": settings.google_client_id,
                                    "client_secret": settings.google_client_secret,
                                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                    "token_uri": "https://oauth2.googleapis.com/token",
                                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                                    "redirect_uris": [
                                        "http://localhost:8080/",
                                    ],
                                }
                            },
                            SCOPES,
                            redirect_uri="http://localhost:8080/",
                        )
                        # Run the flow (opens browser for authentication)
                        print("\n✅ Browser will open for authentication...")
                        print("   If it doesn't open, copy the URL from the terminal")
                        creds = flow.run_local_server(port=8080)
                    except Exception as e2:
                        print(f"\n❌ Web application flow also failed: {e2}")
                        print("\nTroubleshooting:")
                        print("1. Verify your Client ID and Client Secret in .env file")
                        print("2. In Google Cloud Console, check your OAuth client type:")
                        print("   - For Desktop app: Use 'Desktop app' or 'Installed app' type")
                        print("   - For Web app: Use 'Web application' type")
                        print("3. Ensure redirect URI 'http://localhost:8080/' is added")
                        print("4. Make sure OAuth consent screen is configured")
                        raise
                else:
                    raise

        # Save the token for future use
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"\n✅ Token saved to {TOKEN_PATH}")

    print("\n✅ Google Calendar OAuth setup complete!")
    print("   The token will be used automatically by the calendar client.")


if __name__ == "__main__":
    main()