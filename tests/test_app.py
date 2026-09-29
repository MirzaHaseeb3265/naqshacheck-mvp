from streamlit.testing.v1 import AppTest


def test_app_loads_and_runs_default_check():
    app = AppTest.from_file("app.py").run(timeout=20)
    assert not app.exception
    assert app.title[0].value == "Building plan preflight"
    app.tabs[2].button[0].click().run(timeout=20)
    assert not app.exception
    assert len(app.metric) == 3
