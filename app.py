"""Streamlit composition and session-scoped state for DataTriage."""
import hashlib
from pathlib import Path
import streamlit as st
from datatriage.models import Settings, Rule
from datatriage.loading import load_data, sheet_names
from datatriage.detectors import DATE_FORMATS
from datatriage.reporting import analyze
from datatriage.ui import overview_view, issues_view, explorer_view, cleaning_view, report_view, methodology_view

ROOT = Path(__file__).parent
st.set_page_config(page_title="DataTriage · Data quality", page_icon="🔎", layout="wide")
st.markdown("""<style>
.block-container {padding-top:3.7rem; max-width:1440px;}
h1 {letter-spacing:-.045em;}
[data-testid="stMetric"] {background:white; border:1px solid #DFE7EF; border-radius:12px; padding:16px;}
[data-testid="stMetricValue"] {font-size:1.8rem;}
[data-testid="stSidebar"] {border-right:1px solid #DFE7EF;}
.stButton button, .stDownloadButton button {border-radius:8px;}
</style>""", unsafe_allow_html=True)

st.title("DataTriage")
st.markdown("### Data quality analyzer & safe cleaning assistant")
st.caption("Inspect CSV and Excel datasets, understand quality problems and preview cleaning actions before applying them.")

with st.sidebar:
    st.markdown("## Your dataset")
    source = st.selectbox("Data source", ["Dirty customer demo", "Clean inventory demo", "Excel workbook demo", "Upload a file"])
    st.caption("Demo files are synthetic demonstration datasets.")
    data, filename, sheet, delimiter = None, "", None, "Auto"
    if source == "Upload a file":
        uploaded = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"], help="10 MB · 50,000 rows · 200 columns · 2 million cells")
        if uploaded is not None:
            data, filename = uploaded.getvalue(), uploaded.name
    else:
        filename = {"Dirty customer demo": "demo_customers.csv", "Clean inventory demo": "demo_inventory.csv", "Excel workbook demo": "demo_workbook.xlsx"}[source]
        data = (ROOT / "demo_data" / filename).read_bytes()
    try:
        if data is not None and filename.lower().endswith(".xlsx"):
            sheet = st.selectbox("Excel sheet", sheet_names(data))
        elif data is not None:
            delimiter = st.selectbox("CSV delimiter", ["Auto", ",", ";", "\t", "|"], format_func=lambda x: "Tab" if x == "\t" else x)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.caption("Files are processed locally by the running application.")

if data is None:
    st.info("Upload a CSV or XLSX file, or choose a synthetic demo in the sidebar.")
    methodology_view()
    st.stop()

source_key = hashlib.sha256(data + repr((filename, sheet, delimiter)).encode()).hexdigest()
if st.session_state.get("source_key") != source_key:
    try:
        loaded = load_data(data, filename, sheet, delimiter)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    for key in list(st.session_state):
        if key.startswith(("accept_", "rule_", "analysis", "preview", "applied")):
            del st.session_state[key]
    st.session_state.update(source_key=source_key, loaded=loaded, plan=[], rules=[])

loaded = st.session_state.loaded
df = loaded.frame
with st.sidebar:
    st.divider()
    st.markdown("## Analysis settings")
    multiplier = st.slider("Outlier sensitivity (IQR multiplier)", .5, 5.0, 1.5, .1)
    st.caption("Lower values flag more points. Outliers are not automatically removed.")
    demo_rules = st.checkbox("Use demo validation rules", value=source != "Upload a file", disabled=source == "Upload a file",
                             help="Customer demo: ISO joined date, age 0–120, unique customer_id. Inventory: quantity ≥ 0.")
    base_rules = []
    if demo_rules and source != "Upload a file":
        if "joined" in df:
            base_rules = [Rule("joined", "date"), Rule("age", "range", minimum=0, maximum=120), Rule("customer_id", "identifier")]
        elif "quantity" in df:
            base_rules = [Rule("quantity", "range", minimum=0)]
    with st.expander("Add a validation rule"):
        with st.form("rule_form"):
            col = st.selectbox("Rule column", list(df.columns), key="rule_column")
            kind = st.selectbox("Rule type", ["numeric", "date", "identifier", "range"], key="rule_kind")
            fmt = st.selectbox("Expected date format", list(DATE_FORMATS), key="rule_format")
            lo = st.number_input("Range minimum", value=0.0, key="rule_min")
            hi = st.number_input("Range maximum", value=120.0, key="rule_max")
            if st.form_submit_button("Add rule"):
                rule = Rule(col, kind, DATE_FORMATS[fmt], lo if kind == "range" else None, hi if kind == "range" else None)
                if kind == "range" and lo > hi:
                    st.error("Minimum cannot exceed maximum.")
                elif rule not in st.session_state.rules:
                    st.session_state.rules.append(rule)
        if st.button("Clear added rules"):
            st.session_state.rules = []
        for rule in st.session_state.rules:
            st.caption(f"{rule.column}: {rule.kind}" + (f" ({rule.date_format})" if rule.kind == "date" else ""))
    settings = Settings(multiplier, rules=tuple(base_rules + st.session_state.rules))
    if base_rules:
        st.caption("Demo rules: " + "; ".join(f"{r.column}: {r.kind}" for r in base_rules))

analysis_key = source_key + repr(settings)
if st.session_state.get("analysis_key") != analysis_key:
    try:
        st.session_state.analysis = analyze(df, settings, loaded.notes)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.session_state.analysis_key = analysis_key
    st.session_state.pop("preview", None)
    st.session_state.pop("applied", None)
    for key in list(st.session_state):
        if key.startswith("accept_"):
            del st.session_state[key]
analysis = st.session_state.analysis

st.caption(f"{filename}" + (f" / {sheet}" if sheet else "") + " · Original dataset")
with st.expander("Import notes"):
    for note in loaded.notes:
        st.write(note)
page = st.radio("Workspace", ["Overview", "Issues", "Column Explorer", "Cleaning", "Report", "Methodology"], horizontal=True, label_visibility="collapsed")
st.divider()
if page == "Overview":
    overview_view(df, analysis)
elif page == "Issues":
    issues_view(df, analysis["issues"])
elif page == "Column Explorer":
    explorer_view(df, analysis, settings)
elif page == "Cleaning":
    cleaning_view(df, settings)
elif page == "Report":
    report_view(df, settings, loaded.notes)
else:
    methodology_view()
