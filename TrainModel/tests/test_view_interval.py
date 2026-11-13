"""The Train Model redraws less when the harness found software rendering."""

from train_model import module_process
from utils.render_check import LOW_FRAME_RATE_ENV


def test_full_rate_by_default(monkeypatch):
    monkeypatch.delenv(LOW_FRAME_RATE_ENV, raising=False)
    assert module_process.view_interval_s() == 0.05


def test_lower_rate_when_flagged(monkeypatch):
    monkeypatch.setenv(LOW_FRAME_RATE_ENV, "1")
    assert module_process.view_interval_s() == 0.25
    assert module_process.view_interval_s() > module_process.FULL_VIEW_INTERVAL_S
