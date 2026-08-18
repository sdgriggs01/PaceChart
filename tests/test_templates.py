"""Tests for pacechart.templates. Every test injects storage_path=tmp_path/...
so nothing here touches the real %APPDATA%."""

from pathlib import Path

import pytest

from pacechart import templates


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "templates.json"


def test_list_templates_empty_when_no_file_exists(storage_path: Path):
    assert templates.list_templates(storage_path) == []


def test_save_then_load_round_trips(storage_path: Path):
    keys = {("Easy", "Mile"), ("Threshold", "1000m")}

    templates.save_template("Race Week", keys, storage_path)

    assert templates.load_template("Race Week", storage_path) == keys


def test_save_persists_to_disk_as_json(storage_path: Path):
    templates.save_template("Race Week", {("Easy", "Mile")}, storage_path)
    assert storage_path.exists()
    assert storage_path.read_text(encoding="utf-8").strip().startswith("{")


def test_list_templates_returns_sorted_names(storage_path: Path):
    templates.save_template("Zeta", {("Easy", "Mile")}, storage_path)
    templates.save_template("Alpha", {("Easy", "Mile")}, storage_path)

    assert templates.list_templates(storage_path) == ["Alpha", "Zeta"]


def test_save_overwrites_existing_template_of_the_same_name(storage_path: Path):
    templates.save_template("Race Week", {("Easy", "Mile")}, storage_path)
    templates.save_template("Race Week", {("Threshold", "400m")}, storage_path)

    assert templates.load_template("Race Week", storage_path) == {("Threshold", "400m")}


def test_save_does_not_disturb_other_templates(storage_path: Path):
    templates.save_template("A", {("Easy", "Mile")}, storage_path)
    templates.save_template("B", {("Threshold", "400m")}, storage_path)

    assert templates.load_template("A", storage_path) == {("Easy", "Mile")}
    assert templates.load_template("B", storage_path) == {("Threshold", "400m")}


def test_load_missing_template_raises_key_error(storage_path: Path):
    with pytest.raises(KeyError):
        templates.load_template("Nope", storage_path)


def test_save_rejects_empty_name(storage_path: Path):
    with pytest.raises(ValueError):
        templates.save_template("   ", {("Easy", "Mile")}, storage_path)


def test_delete_template_removes_it(storage_path: Path):
    templates.save_template("Race Week", {("Easy", "Mile")}, storage_path)

    templates.delete_template("Race Week", storage_path)

    assert templates.list_templates(storage_path) == []


def test_delete_missing_template_raises_key_error(storage_path: Path):
    with pytest.raises(KeyError):
        templates.delete_template("Nope", storage_path)


def test_delete_does_not_disturb_other_templates(storage_path: Path):
    templates.save_template("A", {("Easy", "Mile")}, storage_path)
    templates.save_template("B", {("Threshold", "400m")}, storage_path)

    templates.delete_template("A", storage_path)

    assert templates.list_templates(storage_path) == ["B"]


def test_default_storage_path_is_under_appdata_pacechart(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = templates.default_storage_path()
    assert path == tmp_path / "PaceChart" / "templates.json"
