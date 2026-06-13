import requests
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TIKTOK_ACCESS_TOKEN_WOMENSWEAR_01")
print(f"Token found: {'yes' if token else 'NO - check .env'}")

r = requests.get(
    "https://open.tiktokapis.com/v2/user/info/?fields=display_name,username",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"Status: {r.status_code}")
print(r.json())
