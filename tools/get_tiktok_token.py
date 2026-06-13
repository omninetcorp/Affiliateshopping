"""
One-time OAuth flow to get a TikTok access token (with PKCE).
Uses manual code copy since TikTok doesn't allow localhost redirects.

Usage:
    python tools/get_tiktok_token.py
"""

import base64
import hashlib
import json
import os
import urllib.parse
import urllib.request
import webbrowser

CLIENT_KEY = input("Paste your sandbox Client Key: ").strip()
CLIENT_SECRET = input("Paste your sandbox Client Secret: ").strip()

REDIRECT_URI = "https://omninetcorp.github.io/Affiliateshopping/"
SCOPE = "video.publish,video.upload"

# PKCE
code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()

auth_url = (
    f"https://www.tiktok.com/v2/auth/authorize/"
    f"?client_key={CLIENT_KEY}"
    f"&scope={urllib.parse.quote(SCOPE)}"
    f"&response_type=code"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&state=tiktok_auth"
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=S256"
)

print(f"\nOpening browser for TikTok login...")
webbrowser.open(auth_url)
print("\nAfter you log in and authorize:")
print("  1. TikTok will redirect to your GitHub page")
print("  2. Copy the FULL URL from the browser address bar")
print("  3. Paste it below\n")

full_url = input("Paste the full redirect URL here: ").strip()

parsed = urllib.parse.urlparse(full_url)
params = urllib.parse.parse_qs(parsed.query)
auth_code = params.get("code", [None])[0]

if not auth_code:
    print("No code found in URL. Make sure you copied the full URL after the redirect.")
    exit(1)

print(f"\nAuth code received. Exchanging for access token...")

token_data = urllib.parse.urlencode({
    "client_key": CLIENT_KEY,
    "client_secret": CLIENT_SECRET,
    "code": auth_code,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI,
    "code_verifier": code_verifier,
}).encode()

req = urllib.request.Request(
    "https://open.tiktokapis.com/v2/oauth/token/",
    data=token_data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
except urllib.request.HTTPError as e:
    print(f"Token exchange failed: {e.read().decode()}")
    exit(1)

access_token = result.get("access_token")
refresh_token = result.get("refresh_token")
expires_in = result.get("expires_in", 0)

print("\n" + "="*60)
print("SUCCESS! Add this to your .env file:")
print("="*60)
print(f"TIKTOK_ACCESS_TOKEN_WOMENSWEAR_01={access_token}")
print(f"TIKTOK_REFRESH_TOKEN_WOMENSWEAR_01={refresh_token}")
print(f"\nToken expires in {expires_in//86400} days")
print("="*60)
