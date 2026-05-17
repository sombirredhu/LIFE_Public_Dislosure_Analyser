from src import config


def test_config_health_report_shape():
    report = config.config_health_report()
    assert isinstance(report, dict)
    assert "errors" in report
    assert "warnings" in report
    assert isinstance(report["errors"], list)
    assert isinstance(report["warnings"], list)

