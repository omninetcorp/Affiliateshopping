import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TIKTOK_ACCESS_TOKEN_WOMENSWEAR_01", "")
print(f"Length: {len(token)}")
print(f"Starts with: {token[:10] if token else 'EMPTY'}")
print(f"Has spaces: {' ' in token}")
print(f"Has newlines: {chr(10) in token or chr(13) in token}")
