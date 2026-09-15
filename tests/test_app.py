from streamlit.testing.v1 import AppTest


def app():
    return AppTest.from_file("app.py", default_timeout=30).run()


def test_default_demo_and_all_views():
    at = app()
    assert not at.exception
    assert at.metric[0].value == "62"
    for page in ["Issues", "Column Explorer", "Cleaning", "Report", "Methodology", "Overview"]:
        at.radio[0].set_value(page).run()
        assert not at.exception, page


def test_clean_demo_score():
    at = app()
    at.selectbox[0].select("Clean inventory demo").run()
    assert not at.exception
    assert at.metric[-1].value == "100.0"


def test_preview_apply_and_settings_invalidate():
    at = app()
    at.radio[0].set_value("Cleaning").run()
    # Forms are selected by their visible labels to avoid sidebar ordering.
    next(s for s in at.selectbox if s.label == "Action").set_value("remove_duplicates")
    next(b for b in at.button if b.label == "Add action").click().run()
    next(b for b in at.button if b.label == "Preview changes").click().run()
    assert not at.exception
    assert at.session_state["preview"][0].rows_removed == 2
    accept = next(c for c in at.checkbox if c.label.startswith("I reviewed"))
    accept.check().run()
    next(b for b in at.button if b.label == "Apply previewed plan").click().run()
    assert len(at.session_state["applied"].frame) == 60
    next(s for s in at.slider if s.label.startswith("Outlier sensitivity")).set_value(2.0).run()
    assert "applied" not in at.session_state
    assert "preview" not in at.session_state
    assert not at.exception


def test_excel_sheets_and_source_reset():
    at = app()
    at.selectbox[0].select("Excel workbook demo").run()
    assert not at.exception
    next(s for s in at.selectbox if s.label == "Excel sheet").select("Inventory").run()
    assert not at.exception
    assert at.metric[0].value == "20"


def test_new_preview_requires_new_acknowledgement():
    at = app()
    at.radio[0].set_value("Cleaning").run()
    next(b for b in at.button if b.label == "Add action").click().run()
    next(b for b in at.button if b.label == "Preview changes").click().run()
    next(c for c in at.checkbox if c.label.startswith("I reviewed")).check().run()
    assert not next(b for b in at.button if b.label == "Apply previewed plan").disabled
    next(b for b in at.button if b.label == "Preview changes").click().run()
    assert next(b for b in at.button if b.label == "Apply previewed plan").disabled
    assert not at.exception
