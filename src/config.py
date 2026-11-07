"""Project paths and a few analysis settings, resolved relative to the project root."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_CSV = RAW_DIR / "ecommerce_returns_synthetic_data.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DATABASE_PATH = PROJECT_ROOT / "data" / "analytics.duckdb"
SQL_DIR = PROJECT_ROOT / "sql"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

SOURCE_URL = "https://www.kaggle.com/datasets/sayalikhot21/synthetic-dataset-for-e-commerce-return-analysis"
DOWNLOAD_URL = "https://www.kaggle.com/api/v1/datasets/download/sayalikhot21/synthetic-dataset-for-e-commerce-return-analysis"

# Display rule only, not a statistical test: segments with fewer eligible
# purchases than this are kept but labelled "low support".
DEFAULT_MIN_SUPPORT = 50

# Display rule for the action table: a category-specific action is suggested only
# when its leading recorded reason is at least this many percentage points ahead
# of the next reason. Otherwise the reason mix does not single out a mechanism.
MIN_REASON_LEAD_PP = 5.0

# Fixed unit-price band boundaries live in sql/00_schema.sql (analytics_orders view).

UNKNOWN_REASON = "Unknown / not provided"
UNKNOWN_LABEL = "Unknown / not provided"
