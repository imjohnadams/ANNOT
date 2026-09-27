import os

from dotenv import load_dotenv

_ANNOT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_ANNOT_ROOT, ".env"))

# Supported input formats
SUPPORTED_EXTENSIONS = {".pdf", ".epub", ".mobi", ".txt", ".azw", ".azw3"}

# Calibre
CALIBRE_ENV_VAR = "CALIBRE_PATH"
CALIBRE_DEFAULT_PATHS = [
    r"C:\Program Files\Calibre2\ebook-convert.exe",
    r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
]

# Token estimation (tiktoken encoding)
TIKTOKEN_ENCODING = "cl100k_base"

# Per-annotation output token assumptions (scaled by quotes_per_page cap)
OUTPUT_QUOTE_TOKENS_LOW = 30
OUTPUT_QUOTE_TOKENS_HIGH = 80
OUTPUT_ANNOTATION_TOKENS_LOW = 60
OUTPUT_ANNOTATION_TOKENS_HIGH = 180
OUTPUT_JSON_OVERHEAD_PER_ANNOT = 20

# Quotes-per-page / quality controls
MIN_QUOTES_PER_PAGE = 1
MAX_QUOTES_PER_PAGE = 10
DEFAULT_QUOTES_PER_PAGE = 1
DEFAULT_QUALITY = "medium"
QUALITY_CHOICES = {
    1: "low",
    2: "medium",
    3: "high",
}
# Skip quality prompt and use medium when selected pages reach this
QUALITY_SKIP_PAGE_THRESHOLD = 100
# Warn when a high density cap is paired with high quality
QPP_HIGH_QUALITY_WARN_THRESHOLD = 3

QUALITY_DESCRIPTIONS = {
    "low": "what important passages mean",
    "medium": "meaning and why the passage matters",
    "high": "concepts, evidence, methods, assumptions, and limits",
}

# High-quality notes tend to run longer
QUALITY_OUTPUT_TOKEN_MULTIPLIER = {
    "low": 0.85,
    "medium": 1.0,
    "high": 1.35,
}

# Cost rates (USD per token)
OUTPUT_COST_REGULAR = 1.20 / 1_000_000
INPUT_COST_ESTIMATE = 0.40 / 1_000_000

BUDGET_WARN_USD = 0.75

# Header/footer detection
HEADER_FOOTER_MIN_PAGE_RATIO = 0.30
HEADER_FOOTER_SCAN_LINES = 2

# Front matter
FRONT_MATTER_MAX_SCAN_PAGES = 25
FRONT_MATTER_MIN_CONTENT_WORDS = 150

# LUNA / OpenAI API
LUNA_API_KEY = os.environ.get("LUNA_API_KEY", "")
LUNA_BASE_URL = os.environ.get(
    "LUNA_BASE_URL", "https://api.openai.com/v1"
).rstrip("/")
LUNA_MODEL = os.environ.get("LUNA_MODEL", "gpt-5.6-luna")

MAX_CONTEXT_TOKENS = 1_050_000
MAX_OUTPUT_TOKENS = 128_000
CHUNK_OUTPUT_TOKEN_BUDGET = 100_000
DOCUMENT_FRAME_MAX_TOKENS = 1_500
MAX_API_RETRIES = 3

PROMPT_FILE = os.path.join(_ANNOT_ROOT, "prompt.md")

# Research-note categories stored in JSON/CSV. Not printed on the PDF.
ANNOTATION_CATEGORIES = (
    "CONCEPT",
    "METHOD",
    "RESULT",
    "EVIDENCE",
    "DEFINITION",
    "INTERPRETATION",
    "LIMITATION",
    "ASSUMPTION",
    "IMPORTANT",
    "QUESTION",
    "CONTEXT",
    "TECHNICAL",
)
GROUNDING_STATUSES = (
    "source_fact",
    "interpretation",
    "uncertain",
)
UNKNOWN = "[UNKNOWN]"
FALLBACK_CATEGORY = "CONTEXT"
FALLBACK_GROUNDING = "uncertain"
