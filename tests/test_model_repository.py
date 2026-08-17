"""
Test suite for the versioned ModelRepository
"""

import json
import os

import pytest

from model_repository import ModelRepository


class _DummyModel:
    """Stand-in for a sklearn model (joblib persistence is tested via the
    real detector tests; here we verify repository bookkeeping)."""

    def __init__(self, name="dummy"):
        self.name = name

    def predict(self, x):
        return [-1] * len(x)


def _make_repo(tmp_path) -> ModelRepository:
    return ModelRepository(str(tmp_path / 'models'))


def test_save_and_load_roundtrip(tmp_path):
    repo = _make_repo(tmp_path)
    card = {'version': 1, 'trained_at': '2026-01-01T00:00:00+00:00', 'n_samples': 100}

    repo.save(1, _DummyModel('m1'), None, card)

    payload = repo.load(1)
    assert payload is not None
    assert payload['model'].name == 'm1'
    assert payload['card'] == card


def test_version_management(tmp_path):
    repo = _make_repo(tmp_path)
    assert repo.current_version() is None
    assert repo.next_version() == 1
    assert repo.list_versions() == []

    repo.save(1, _DummyModel(), None, {'version': 1})
    repo.save(2, _DummyModel(), None, {'version': 2})

    assert repo.list_versions() == [1, 2]
    assert repo.next_version() == 3
    assert repo.current_version() is None  # not set until set_current

    repo.set_current(2)
    assert repo.current_version() == 2


def test_load_missing_version(tmp_path):
    repo = _make_repo(tmp_path)
    assert repo.load(99) is None


def test_card_file_is_valid_json(tmp_path):
    repo = _make_repo(tmp_path)
    repo.save(5, _DummyModel(), None, {'version': 5, 'baseline': {'cpu_usage': {'mean': 50.0}}})

    with open(repo._card_path(5), 'r', encoding='utf-8') as f:
        card = json.load(f)
    assert card['version'] == 5
    assert card['baseline']['cpu_usage']['mean'] == 50.0
