import os
import secrets
from dotenv import load_dotenv

load_dotenv()

VK_ACCESS_TOKEN = os.environ["VK_ACCESS_TOKEN"]
VK_GROUP_ID = os.environ["VK_GROUP_ID"]
APP_SECRET = os.environ["APP_SECRET"]
VK_API_VERSION = "5.199"
VK_API_BASE = "https://api.vk.com/method"

# VK rate limit: 20 req/s for community tokens
VK_RATE_LIMIT = 20

# HMAC key for signing session cookies (auto-generated per deploy)
COOKIE_SIGN_KEY = os.environ.get("COOKIE_SIGN_KEY", secrets.token_hex(32))
