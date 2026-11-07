"""E-commerce Returns Analytics dashboard (three pages).

Run from the project root:
    python -m streamlit run dashboard/app.py --server.address 127.0.0.1
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from src.config import DATABASE_PATH  # noqa: E402
from src.database import DatabaseLockedError  # noqa: E402

st.set_page_config(page_title="E-commerce Returns Analytics", layout="wide")

if not DATABASE_PATH.exists():
    st.title("E-commerce Returns Analytics")
    st.error(f"No database found at `{DATABASE_PATH.relative_to(ROOT).as_posix()}`. "
             "Build it from the project root with:")
    st.code("python pipeline.py", language="bash")
    st.stop()

from dashboard import common  # noqa: E402

try:
    common.init_filters()
    d = common.defaults()
except DatabaseLockedError as exc:
    st.error(str(exc))
    st.stop()

# Filter values live in plain session keys; widgets use "w_" keys that are refreshed
# from them on every run, so values survive page switches and the reset button.
for name in ("date_range", "categories", "min_support"):
    st.session_state["w_" + name] = st.session_state[name]


def _sync(name: str) -> None:
    st.session_state[name] = st.session_state["w_" + name]


with st.sidebar:
    st.header("Filters")
    st.date_input("Order date range", key="w_date_range", on_change=_sync, args=("date_range",),
                  min_value=d["start_date"], max_value=d["end_date"])
    st.multiselect("Product category", options=d["categories"], key="w_categories",
                   on_change=_sync, args=("categories",))
    st.number_input("Minimum eligible purchases for comparison (support)", min_value=1,
                    max_value=100000, step=10, key="w_min_support", on_change=_sync, args=("min_support",),
                    help="Groups below this are kept but labelled 'low support'. Display rule only.")
    st.button("Reset filters", on_click=common.reset_filters)
    st.caption("Synthetic practice dataset · counts recomputed for every filter.")

pages = [
    st.Page("views/1_returns_overview.py", title="Returns Overview", default=True),
    st.Page("views/2_reasons_and_patterns.py", title="Reasons and Patterns"),
    st.Page("views/3_investigation_priorities.py", title="Investigation Priorities"),
]
st.navigation(pages).run()
