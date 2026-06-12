"""
constants.py — All magic numbers and configuration constants for RefAgent.
Never hardcode values in business logic — reference them from here.
"""

from pathlib import Path

# ════════════════════════════════════════════════════
# PATHS
# ════════════════════════════════════════════════════

BASE_DIR       = Path(__file__).parent.parent
DATA_DIR       = BASE_DIR / "data"
SESSIONS_DIR   = DATA_DIR / "sessions"
LIBRARY_DIR    = DATA_DIR / "library"
SCRIPTS_DIR    = BASE_DIR / "scripts"
UPLOADS_DIR    = DATA_DIR / "uploads"    # incoming .session / .zip files from Telegram
CONFIG_FILE    = BASE_DIR / "config.json"
SESSIONS_DB    = DATA_DIR / "sessions.db"
RESULTS_DB     = DATA_DIR / "results.db"

# ════════════════════════════════════════════════════
# ANIMATION
# ════════════════════════════════════════════════════

ANIMATOR_FRAMES       = ["Working", "Working.", "Working..", "Working..."]
ANIMATOR_FRAME_DELAY  = 0.8   # seconds between frames
THINKING_FRAMES       = ["Thinking", "Thinking.", "Thinking..", "Thinking..."]
READING_FRAMES        = ["Read", "Read.", "Read..", "Read..."]
SENDING_FRAMES        = ["Sending", "Sending.", "Sending..", "Sending..."]
CONNECTING_FRAMES     = ["Connecting", "Connecting.", "Connecting..", "Connecting..."]

# ════════════════════════════════════════════════════
# LLM PROVIDERS
# ════════════════════════════════════════════════════

OPENROUTER_BASE_URL    = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_PATH   = "/chat/completions"
OPENROUTER_MODELS_PATH = "/models"
OPENROUTER_MODELS_CACHE_TTL = 3600  # 1 hour in seconds

FAVORITEAPI_CHAT_PATH  = "/api/v1/chat"
FAVORITEAPI_ME_PATH    = "/api/v1/me"
FAVORITEAPI_RESET_PATH = "/api/v1/reset"
FAVORITEAPI_MODELS_PATH = "/api/v1/models"

FAVORITEAPI_CTX_WARN_KB   = 150   # start compressing above this
FAVORITEAPI_CTX_LIMIT_KB  = 180   # hard limit

BAI_BASE_URL        = "https://api.b.ai/v1"
BAI_CHAT_PATH       = "/chat/completions"
BAI_MODELS_PATH     = "/models"
BAI_MODELS_CACHE_TTL = 3600
BAI_FREE_MODELS     = frozenset({"kimi-k2.5", "glm-5", "glm-5.1", "minimax-m2.5"})
BAI_DEFAULT_MODEL   = "kimi-k2.5"

# ════════════════════════════════════════════════════
# MODEL BROWSER
# ════════════════════════════════════════════════════

MODELS_PER_PAGE = 10

# ════════════════════════════════════════════════════
# TELEGRAM ACCOUNT LIMITS (referral rules)
# ════════════════════════════════════════════════════

UID_THRESHOLD_FRESH  = 8_500_000_000
UID_THRESHOLD_NORMAL = 7_000_000_000

TIMING_BETWEEN_REFERRALS  = 60    # hard minimum seconds between credits
TIMING_BETWEEN_ACCOUNTS   = 20    # seconds between account processing
TIMING_BOT_RESPONSE       = 5     # seconds to wait for bot reply
TIMING_BOT_RESPONSE_RETRY = 2     # seconds between retry attempts
TIMING_BOT_MAX_ATTEMPTS   = 5     # max attempts to get bot response
TIMING_DM_RETRY           = 10    # seconds between DM attempts

# ════════════════════════════════════════════════════
# TEMP SCRIPTS
# ════════════════════════════════════════════════════

SCRIPT_TIMEOUT          = 60     # default execution timeout seconds
SCRIPT_MAX_AGE_HOURS    = 24     # auto-cleanup scripts older than this

# ════════════════════════════════════════════════════
# BOT UI TEXT
# ════════════════════════════════════════════════════

BOT_VERSION = "0.1.0"
BOT_NAME    = "RefAgent"
