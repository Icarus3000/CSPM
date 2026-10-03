"""Behavioral safety gates for process-local experimental engine selection.

These checks do not create windows or initialize WebEngine/GPU rendering.
"""
import importlib.util
import logging
from pathlib import Path

import pytest
import shiboken6
from PySide6.QtCore import QObject


MODULE_PATH = Path(__file__).resolve().parents[1] / "src/python/backend/transition_experiment.py"
SPEC = importlib.util.spec_from_file_location("cleanroom_selector_under_test", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
TransitionExperiment = MODULE.TransitionExperiment


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    monkeypatch.delenv("CSPM_EXPERIMENTAL_TRANSITION", raising=False)
    monkeypatch.delenv("CSPM_EXPERIMENTAL_REDUCED_MOTION", raising=False)


def test_production_is_default_without_persisted_settings():
    selector = TransitionExperiment()
    assert selector.engine == "production"
    assert selector.reducedMotion is False


@pytest.mark.parametrize("engine", sorted(TransitionExperiment.ENGINES))
def test_explicit_environment_selects_each_registered_engine(monkeypatch, engine):
    monkeypatch.setenv("CSPM_EXPERIMENTAL_TRANSITION", engine)
    assert TransitionExperiment().engine == engine


def test_unknown_environment_falls_back_without_echoing_untrusted_value(monkeypatch, caplog):
    untrusted_value = "private-token-never-print-this"
    monkeypatch.setenv("CSPM_EXPERIMENTAL_TRANSITION", untrusted_value)
    with caplog.at_level(logging.WARNING):
        selector = TransitionExperiment()
    assert selector.engine == "production"
    assert "using production" in caplog.text
    assert untrusted_value not in caplog.text


def test_active_registered_owner_blocks_switch_until_input_release():
    selector = TransitionExperiment()
    owner = QObject()
    owner.setProperty("professionalWindowTransitionActive", True)
    selector.registerWindow(owner)
    notifications = []
    selector.engineChanged.connect(lambda: notifications.append(selector.engine))
    assert selector.setEngine("single-clock") is False
    assert selector.engine == "production"
    assert notifications == []
    owner.setProperty("professionalWindowTransitionActive", False)
    assert selector.setEngine("single-clock") is True
    assert selector.engine == "single-clock"
    assert notifications == ["single-clock"]


def test_destroyed_owner_does_not_block_future_explicit_selection():
    selector = TransitionExperiment()
    owner = QObject()
    owner.setProperty("professionalWindowTransitionActive", True)
    selector.registerWindow(owner)
    shiboken6.delete(owner)
    assert selector.setEngine("single-clock") is True


def test_invalid_selection_is_rejected_without_changing_or_notifying():
    selector = TransitionExperiment()
    notifications = []
    selector.engineChanged.connect(lambda: notifications.append(selector.engine))
    assert selector.setEngine("invalid-engine") is False
    assert selector.engine == "production"
    assert notifications == []


def test_unchanged_selection_does_not_notify():
    selector = TransitionExperiment()
    notifications = []
    selector.engineChanged.connect(lambda: notifications.append(selector.engine))
    assert selector.setEngine("production") is True
    assert notifications == []


@pytest.mark.parametrize("value, expected", [("1", True), ("0", False), ("true", False)])
def test_reduced_motion_is_explicit_and_process_local(monkeypatch, value, expected):
    monkeypatch.setenv("CSPM_EXPERIMENTAL_REDUCED_MOTION", value)
    assert TransitionExperiment().reducedMotion is expected


def test_diagnostic_clock_is_monotonic():
    selector = TransitionExperiment()
    timestamps = [selector.monotonicMs() for _ in range(20)]
    assert timestamps[0] >= 0
    assert timestamps == sorted(timestamps)
