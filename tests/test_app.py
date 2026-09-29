from streamlit.testing.v1 import AppTest


def test_app_loads_and_runs_default_check():
    app = AppTest.from_file("app.py").run(timeout=20)
    assert not app.exception
    assert app.title[0].value == "Building plan preflight"
    app.tabs[2].button[0].click().run(timeout=20)
    assert not app.exception
    assert len(app.metric) == 3


def test_app_can_select_10_marla_rule_pack():
    app = AppTest.from_file("app.py").run(timeout=20)
    plot_select = next(item for item in app.selectbox if item.label == "Plot class *")
    plot_select.select("10_marla_residential").run(timeout=20)
    assert not app.exception
