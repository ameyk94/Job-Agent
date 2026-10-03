"""OpenRouter chat-model factory and Opik mode switch. Fully offline."""

from __future__ import annotations

import sys
import types

import pytest

from job_scout import tracing
from job_scout.config import get_settings
from job_scout.llm import get_chat_model


@pytest.fixture(autouse=True)
def _reset_tracing(monkeypatch):
    get_chat_model.cache_clear()
    monkeypatch.setattr(tracing, "_CONFIGURED", False)
    monkeypatch.setattr(tracing, "_FAILED", False)


def test_chat_model_uses_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    model = get_chat_model("anthropic/claude-3.5-haiku")
    assert model.model_name == "anthropic/claude-3.5-haiku"
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.openai_api_key.get_secret_value() == "sk-or-test"


def test_has_opik_per_mode(monkeypatch):
    monkeypatch.setenv("OPIK_ENABLED", "true")
    monkeypatch.setenv("OPIK_MODE", "local")
    assert not get_settings().has_opik  # no URL yet
    get_settings.cache_clear()
    monkeypatch.setenv("OPIK_URL_OVERRIDE", "http://hermes:5173/api")
    assert get_settings().has_opik
    get_settings.cache_clear()
    monkeypatch.setenv("OPIK_MODE", "cloud")
    assert not get_settings().has_opik  # cloud needs a key
    get_settings.cache_clear()
    monkeypatch.setenv("OPIK_API_KEY", "k")
    assert get_settings().has_opik


def _fake_opik(monkeypatch, configure):
    mod = types.ModuleType("opik")
    mod.configure = configure
    monkeypatch.setitem(sys.modules, "opik", mod)


def test_local_mode_configures_url(monkeypatch):
    monkeypatch.setenv("OPIK_ENABLED", "true")
    monkeypatch.setenv("OPIK_URL_OVERRIDE", "http://hermes:5173/api")
    calls = []
    _fake_opik(monkeypatch, lambda **kw: calls.append(kw))
    assert tracing.configure_opik() is True
    assert calls[0]["use_local"] is True and calls[0]["url"] == "http://hermes:5173/api"


def test_unreachable_opik_degrades_to_no_tracing(monkeypatch):
    monkeypatch.setenv("OPIK_ENABLED", "true")
    monkeypatch.setenv("OPIK_URL_OVERRIDE", "http://hermes:5173/api")
    attempts = []

    def boom(**kw):
        attempts.append(kw)
        raise ConnectionError("unreachable")

    _fake_opik(monkeypatch, boom)
    assert tracing.configure_opik() is False
    assert tracing.configure_opik() is False
    assert len(attempts) == 1  # no retry storm
    assert tracing.get_tracer("t", []) is None


def test_attach_cv_off_by_default(monkeypatch, tmp_path):
    class Tracer:
        def created_traces(self):
            raise AssertionError("must not be called when TRACE_ATTACH_CV=false")

    tracing.attach_cv(Tracer(), tmp_path / "cv.pdf")
