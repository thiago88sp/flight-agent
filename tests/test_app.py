from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def load():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def texts(at):
    return " ".join(m.value for c in at.chat_message for m in c.markdown)


def test_form_single_city_accepts_names():
    at = load()
    at.sidebar.button[0].click().run()          # defaults: "São Paulo" -> "Lisbon"
    assert not at.exception, at.exception
    t = texts(at)
    assert "São Paulo (GRU)" in t and "Lisbon (LIS)" in t and "Found" in t
    assert len(at.dataframe) == 1                # full table inside the expander


def test_form_by_region():
    at = load()
    at.sidebar.radio[0].set_value("Region").run()
    at.sidebar.slider[0].set_value(0)
    at.sidebar.button[0].click().run()
    assert not at.exception, at.exception
    t = texts(at)
    assert "Europe (11 destinations)" in t and "Other destinations" in t


def test_chat_by_region(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")     # the "parsed by" note is developer info
    at = load()
    at.chat_input[0].set_value("GRU to any city in Europe on 10/12, 10 days").run()
    assert not at.exception, at.exception
    assert "Europe" in texts(at)
    notes = " ".join(c.value for m in at.chat_message for c in m.caption)
    assert "parsed by: rules" in notes


def test_chat_still_understands_portuguese():
    at = load()
    at.chat_input[0].set_value("GRU para qualquer cidade da Europa em 10/12, 10 dias").run()
    assert not at.exception, at.exception
    assert "Europe (11 destinations)" in texts(at)


def test_example_button_runs_search_and_disappears():
    at = load()
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert "Found" in texts(at)
    at.run()
    assert not [b for b in at.button if b.label.startswith("São Paulo to")]


def test_chat_incomplete_request_shows_error_without_crashing():
    at = load()
    at.chat_input[0].set_value("I want to travel").run()
    assert not at.exception, at.exception
    assert len(at.error) == 1
    assert len(at.session_state.history) == 2    # question + error answer


def test_create_watch_from_the_ui():
    from flight_agent import watch
    at = load()
    at.sidebar.button[0].click().run()
    create = [b for b in at.button if b.label == "Create watch"]
    create[0].click().run()
    assert not at.exception, at.exception
    items = watch.load_watches()
    assert len(items) == 1 and items[0]["query"]["dests"] == ["LIS"]
    assert any("Watching" in s.value for s in at.success)
    assert "Price watches (1)" in " ".join(e.label for e in at.sidebar.expander)


def test_consumer_view_hides_developer_details():
    at = load()
    at.chat_input[0].set_value("GRU to Lisbon on 10/12, 10 days").run()
    assert not at.exception, at.exception
    notes = " ".join(c.value for m in at.chat_message for c in m.caption)
    assert "parsed by" not in notes
    labels = " ".join(e.label for e in at.sidebar.expander)
    assert "How it works" not in labels and "Developer info" not in labels
    assert not at.sidebar.code                   # no WATCHES JSON


def test_dev_mode_shows_developer_info(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    at = load()
    assert "Developer info" in " ".join(e.label for e in at.sidebar.expander)
