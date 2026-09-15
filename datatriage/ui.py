"""Reusable Streamlit views; engine functions remain independently testable."""
from dataclasses import replace
import hashlib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from .models import Action, Settings
from .cleaning import ACTION_INFO, GLOBAL_ACTIONS, clean
from .detectors import DATE_FORMATS
from .profiling import column_profile, numeric_values
from .reporting import analyze, report_dict, json_bytes, csv_bytes, xlsx_bytes

TEAL = "#137C78"


def table(df: pd.DataFrame, limit: int = 200):
    # Stringify mixed object columns only in the view; do not alter engine data.
    view = df.head(limit).copy()
    for col in view:
        if view[col].dtype == object:
            view[col] = view[col].map(lambda v: None if pd.isna(v) else str(v))
    st.dataframe(view, hide_index=True, width="stretch")
    if len(df) > limit:
        st.caption(f"Showing first {limit:,} of {len(df):,} rows.")


def chart(fig, key: str):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=12, r=12, t=25, b=15), height=300, font=dict(color="#192D43"))
    st.plotly_chart(fig, use_container_width=True, key=key)


def score_text(score):
    return "—" if score is None else f"{score:.1f}"


def overview_view(df, analysis):
    stats = analysis["overview"]
    for column, label, value in zip(st.columns(5), ["Rows", "Columns", "Missing cells", "Duplicate rows", "DataTriage score"],
                                   [f'{stats["rows"]:,}', stats["columns"], f'{stats["missing_cells"]:,}', stats["duplicate_rows"], score_text(analysis["score"]["overall"])]):
        column.metric(label, value)
    st.caption(f'Missing: {stats["missing_percentage"]:.1f}% · In-memory size: {stats["memory_bytes"] / 1024:.1f} KB · Score is a diagnostic heuristic, not a certification.')
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Quality components")
        values = analysis["score"]["components"]
        if analysis["score"]["overall"] is not None:
            fig = px.bar(x=list(values.values()), y=list(values), orientation="h", labels={"x": "Score / 100", "y": ""}, color_discrete_sequence=[TEAL])
            fig.update_xaxes(range=[0, 100])
            chart(fig, "components")
        else:
            st.info("No cells to score. Empty datasets have no quality score.")
    with right:
        st.subheader("Missing values by column")
        missing = df.isna().sum().sort_values(ascending=False).head(20)
        if missing.sum():
            chart(px.bar(x=missing.index, y=missing.values, labels={"x": "", "y": "Missing cells"}, color_discrete_sequence=["#E6A048"]), "missing")
            st.caption("Up to 20 columns with the most missing values.")
        else:
            st.success("No missing cells detected.")
    with st.expander("Column types"):
        table(pd.DataFrame([{"Suggested type": k, "Columns": v} for k, v in stats["types"].items()]))
        st.caption("Numeric-like CSV text is a suggested type. Values are converted only by an explicit cleaning action.")
    st.subheader("Source preview")
    table(df)


def issues_view(df, issues):
    st.subheader("Investigate the findings")
    st.caption("Counts refer to cells unless labeled rows/columns. Findings can overlap; severity text is always shown.")
    if not issues:
        st.success("No issues detected under the current rules.")
        return
    left, middle, right = st.columns(3)
    severities = left.multiselect("Severity", ["HIGH", "MEDIUM", "LOW", "INFO"])
    kinds = middle.multiselect("Issue type", sorted({i.kind for i in issues}))
    cols = right.multiselect("Column filter", list(df.columns))
    selected = [i for i in issues if (not severities or i.severity in severities) and (not kinds or i.kind in kinds) and (not cols or i.column in cols)]
    counts = pd.Series([i.severity for i in selected]).value_counts()
    if len(counts):
        chart(px.bar(x=counts.index, y=counts.values, labels={"x": "Severity", "y": "Findings"}, color_discrete_sequence=[TEAL]), "severity")
    st.write(f"**{len(selected)} findings**")
    for idx, issue in enumerate(selected):
        with st.expander(f"{issue.severity} · {issue.kind.replace('_', ' ')} · {issue.column or 'Dataset'} · {issue.affected_count:,} {issue.unit}"):
            st.write(issue.explanation)
            st.caption(f"{issue.percentage:.1f}% affected · {issue.suggested_action}")
            if issue.rows:
                st.caption("First 100 affected source rows (positions shown below are 1-based, excluding header).")
                sample = df.iloc[list(issue.rows[:100])].copy()
                # A separate position table avoids clashing with an uploaded column name.
                st.write("Row positions:", ", ".join(str(x + 1) for x in issue.rows[:100]))
                table(sample, 100)


def explorer_view(df, analysis, settings):
    if not len(df.columns):
        st.info("There are no columns to explore.")
        return
    col = st.selectbox("Explore column", list(df.columns))
    profile = column_profile(df[col])
    st.caption(f"Suggested type: {profile['type']} · Unique: {profile['unique']:,} · Missing: {profile['missing_percentage']:.1f}%")
    left, right = st.columns(2)
    with left:
        table(pd.DataFrame([{"Statistic": k.replace("_", " "), "Value": "—" if v is None else str(v)} for k, v in profile.items() if k != "common_values"]))
    with right:
        if profile["type"] == "numeric":
            nums = numeric_values(df[col]).replace([np.inf, -np.inf], np.nan).dropna()
            sampled = nums.sample(min(5000, len(nums)), random_state=42)
            if len(sampled):
                chart(px.histogram(x=sampled, nbins=35, labels={"x": col, "y": "Count"}, color_discrete_sequence=[TEAL]), "numeric")
                # Explicit fences instead of Plotly's default boxplot multiplier.
                q1, q3 = nums.quantile([.25, .75])
                st.caption(f"IQR fences ({settings.iqr_multiplier:g}×): {q1 - settings.iqr_multiplier * (q3 - q1):g} to {q3 + settings.iqr_multiplier * (q3 - q1):g}. Detection requires at least 4 finite values.")
                if len(nums) > 5000:
                    st.caption("Chart samples 5,000 rows deterministically; all core metrics use every row.")
            st.info("Outlier does not necessarily mean incorrect data.")
        elif "common_values" in profile:
            table(pd.DataFrame(profile["common_values"]))
    for issue in analysis["issues"]:
        if issue.column == col:
            st.write(f"**{issue.severity} · {issue.kind}** — {issue.affected_count} affected. {issue.explanation}")


def cleaning_view(original, settings):
    st.subheader("Build a cleaning plan")
    st.caption("Every plan starts from the original upload. Actions run in the listed order. Preview first, then apply explicitly.")
    with st.form("action_form"):
        left, right = st.columns(2)
        kind = left.selectbox("Action", list(ACTION_INFO), format_func=lambda k: ACTION_INFO[k][0])
        col = right.selectbox("Target column (ignored for dataset actions)", list(original.columns) or [None])
        # Show all parameter controls in a form; their applicability is explicit.
        value = st.text_input("Custom text (only for custom filling)", value="Unknown")
        date_format = st.selectbox("Date format (only for datetime conversion)", list(DATE_FORMATS))
        multiplier = st.slider("IQR multiplier (only for outlier removal)", .5, 5.0, settings.iqr_multiplier, .1)
        if st.form_submit_button("Add action"):
            param = value if kind == "fill_custom" else DATE_FORMATS[date_format] if kind == "to_datetime" else multiplier if kind == "remove_outliers" else None
            st.session_state.plan.append(Action(kind, None if kind in GLOBAL_ACTIONS else col, param))
            st.session_state.pop("preview", None)
            st.session_state.pop("applied", None)
    plan = st.session_state.plan
    if not plan:
        st.info("No actions selected. Your source data is unchanged.")
        return
    table(pd.DataFrame([{"Step": n + 1, "Action": ACTION_INFO[a.kind][0], "Column": a.column or "Dataset", "Parameter": str(a.value or ""), "Risk": ACTION_INFO[a.kind][1], "Explanation": ACTION_INFO[a.kind][2]} for n, a in enumerate(plan)]))
    if st.button("Clear plan and applied result"):
        st.session_state.plan = []
        st.session_state.pop("preview", None)
        st.session_state.pop("applied", None)
        st.rerun()
    if st.button("Preview changes", type="primary"):
        try:
            result = clean(original, plan)
            filtered = replace(settings, rules=tuple(r for r in settings.rules if r.column in result.frame))
            for key in list(st.session_state):
                if key.startswith("accept_"):
                    del st.session_state[key]
            st.session_state.preview = (result, analyze(result.frame.reset_index(drop=True), filtered))
            st.session_state.pop("applied", None)
        except ValueError as exc:
            st.error(str(exc))
            st.session_state.pop("preview", None)
    if "preview" not in st.session_state:
        return
    result, after = st.session_state.preview
    before = analyze(original, settings)
    st.subheader("Before / after")
    comparison = []
    for label, key in [("Rows", "rows"), ("Columns", "columns"), ("Missing cells", "missing_cells"), ("Duplicate rows", "duplicate_rows")]:
        comparison.append({"Metric": label, "Before": str(before["overview"][key]), "After": str(after["overview"][key])})
    comparison.append({"Metric": "DataTriage score", "Before": score_text(before["score"]["overall"]), "After": score_text(after["score"]["overall"])})
    table(pd.DataFrame(comparison))
    st.write(f"**{result.rows_removed:,} rows removed · {result.columns_removed} columns removed · {result.cells_modified:,} surviving cells modified**")
    st.caption("Modified cells count distinct surviving cells with different values. Dtype-only changes and removed cells are excluded; per-step counts can overlap.")
    st.subheader("Transformation log")
    table(pd.DataFrame(result.log))
    left, right = st.columns(2)
    with left:
        st.markdown("**Original**")
        table(original, 50)
    with right:
        st.markdown("**Preview**")
        table(result.frame, 50)
    high_risk = any(ACTION_INFO[a.kind][1] == "HIGH" for a in plan)
    if high_risk:
        st.warning("This plan includes HIGH-risk actions. Conversion can replace invalid values with missing; removal discards data from the exported copy.")
    signature = hashlib.sha256(repr(plan).encode()).hexdigest()[:16]
    acknowledged = st.checkbox("I reviewed this preview and accept the selected transformations.", key="accept_" + signature)
    if st.button("Apply previewed plan", disabled=not acknowledged, type="primary"):
        st.session_state.applied = result
        st.success("Plan applied to a separate copy. Open Report to download it.")
    if "applied" in st.session_state:
        st.info("An applied result is ready in Report. Changing the source, rules or plan invalidates it.")


def report_view(original, settings, notes):
    result = st.session_state.get("applied")
    st.subheader("Export your results")
    if result is None:
        st.info("Original quality report is available. Preview and apply a cleaning plan to enable cleaned-data downloads.")
    else:
        st.success(f"Applied copy: {len(result.frame):,} rows × {len(result.frame.columns)} columns.")
        safe = st.checkbox("Protect CSV text from spreadsheet formula interpretation", value=True)
        st.caption("When enabled, CSV text/header values starting with =, +, -, or @ (after whitespace) get a leading apostrophe. This export-only change is not counted as cleaning. XLSX always stores strings and integers over 15 digits as literal text. Excel may round other numeric values to its supported precision.")
        left, right = st.columns(2)
        left.download_button("Download cleaned CSV", csv_bytes(result.frame, safe), "datatriage_cleaned.csv", "text/csv")
        try:
            excel = xlsx_bytes(result.frame)
            right.download_button("Download cleaned XLSX", excel, "datatriage_cleaned.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except (ValueError, TypeError) as exc:
            st.warning(f"Excel export is unavailable for these values: {exc}. CSV is still available.")
        st.subheader("Applied transformation log")
        table(pd.DataFrame(result.log))
    report = report_dict(original, result, settings, notes)
    st.download_button("Download quality report (JSON)", json_bytes(report), "datatriage_report.json", "application/json")
    st.caption("Report includes timestamp, rules, scores, issue counts and up to 100 affected row positions per issue. It contains column names and action parameters (including custom replacement text), but no source row values.")
    with st.expander("Report preview"):
        st.json(report, expanded=False)


def methodology_view():
    st.subheader("Explainable by design")
    st.markdown("""
**Files are processed locally by the running application.** There are no external APIs, tracking integrations or permanent dataset storage. If you host the application on another computer, processing happens on that host. Session memory is not encrypted storage.

**DataTriage quality score** is the equally weighted mean of four components, each from 0 to 100:
- **Completeness:** 100 × (1 − missing cells / all cells).
- **Uniqueness:** 100 × (1 − repeated rows after the first / all rows).
- **Validity:** 100 × (1 − distinct invalid cells / all cells). Invalid means infinity or failure of an explicitly configured numeric/date/range rule.
- **Consistency:** 100 × (1 − distinct inconsistent cells / all cells). Whitespace, blank text, capitalization variants, mixed stored types, mixed numeric/text and mixed date shapes contribute.

Overlapping findings within a component count once per cell. Components are averaged before rounding to two decimals. Empty datasets show no score. Outliers, constant columns, duplicate headers/columns and identifier rules remain visible findings but do not directly penalize the score. A high score does not prove business correctness.

**Severity rules:** HIGH for infinity, configured rule failures and columns with at least 20% missing values; LOW for fewer missing values, whitespace and category/date-format variants; MEDIUM for duplicate rows/headers, empty or at least 95%-missing columns, and mixed types; INFO for outliers, constants, matching columns and date/index-shaped hints.

**IQR:** Q3 − Q1, the spread of the middle 50% of finite numeric values. A value outside Q1 − multiplier × IQR to Q3 + multiplier × IQR is flagged. Default multiplier is 1.5; at least 4 finite values are required. With IQR = 0, values different from the quartiles can be flagged. **Outlier does not necessarily mean incorrect data.**

**Dates:** date-shaped text is a hint. Add an explicit format rule to count invalid dates. Day-first and month-first dates are never silently guessed. Native Excel datetime cells are recognized. CSV numeric inference is descriptive only; original text is preserved until explicit conversion.

**Cleaning:** ordered actions operate on a deep copy, starting from the original input. Inspect risk, counts, new missing cells and the before/after preview, then acknowledge and apply. Changes to the source, settings or plan invalidate prior previews and downloads. Clearing a plan restores the untouched source workflow.

**Limits:** 10 MB files, 50,000 rows, 200 columns, 2 million cells; XLSX expanded contents limited to 50 MB. Distribution charts sample at most 5,000 values with a fixed seed; metrics use all cells. Table previews are bounded. XLSX formatting, formulas as executable expressions, merged-cell structure and multiple output sheets are not preserved.

DataTriage cannot know arbitrary business meaning. A missing value can be intentional, a repeated row legitimate, a numeric-looking column an identifier. Cleaning needs human judgment. The score is a diagnostic heuristic, not an industry certification or an AI model.
""")
