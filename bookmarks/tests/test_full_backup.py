import sqlite3
from contextlib import closing
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from django.core.management import call_command

from bookmarks.management.commands.full_backup import Command

FILES = {"assets/a.txt": b"asset", "favicons/f.ico": b"icon", "previews/p.png": b"preview"}
ROWS = [(1, "alpha"), (2, "繁體中文")]


@pytest.fixture
def backup_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    with closing(sqlite3.connect(data / "db.sqlite3")) as db, db:
        db.execute("CREATE TABLE audit_marker (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
        db.executemany("INSERT INTO audit_marker VALUES (?, ?)", ROWS)
    for name, content in FILES.items():
        path = data / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(content)
    return data


def assert_database_contents(path):
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert db.execute("SELECT id, label FROM audit_marker ORDER BY id").fetchall() == ROWS


def assert_archive_contents(destination, expected_files):
    with ZipFile(destination) as archive:
        assert sorted(archive.namelist()) == sorted(["db.sqlite3", *expected_files])
        assert archive.testzip() is None
        for name, content in expected_files.items():
            assert archive.read(name) == content
        restored = destination.with_name("restored.sqlite3")
        restored.write_bytes(archive.read("db.sqlite3"))
    assert_database_contents(restored)


def assert_source_contents(data, expected_files):
    assert_database_contents(data / "db.sqlite3")
    assert {file.relative_to(data).as_posix(): file.read_bytes() for file in data.glob("*/*") if file.is_file()} == expected_files


def test_backup_preserves_database_and_asset_contents(backup_source, tmp_path):
    destination = tmp_path / "backup.zip"
    stdout = StringIO()
    call_command("full_backup", str(destination), stdout=stdout)
    assert f"Backup created at {destination}" in stdout.getvalue()
    assert_archive_contents(destination, FILES)
    assert_source_contents(backup_source, FILES)


def test_backup_handles_missing_and_empty_directories(backup_source, tmp_path):
    (backup_source / "assets/a.txt").unlink()
    (backup_source / "assets").rmdir()
    (backup_source / "favicons/f.ico").unlink()
    expected_files = {"previews/p.png": FILES["previews/p.png"]}
    destination = tmp_path / "backup.zip"
    stdout = StringIO()
    call_command("full_backup", str(destination), stdout=stdout)
    assert "No assets folder found. Skipping..." in stdout.getvalue()
    assert "Backup bookmark favicons..." in stdout.getvalue()
    assert f"Backup created at {destination}" in stdout.getvalue()
    assert_archive_contents(destination, expected_files)
    assert_source_contents(backup_source, expected_files)


def test_backup_reports_database_copy_failure(backup_source, tmp_path):
    destination = tmp_path / "backup.zip"
    stdout = StringIO()
    failure = sqlite3.OperationalError("database copy failed")
    with patch.object(Command, "backup_database", side_effect=failure), pytest.raises(sqlite3.OperationalError) as raised:
        call_command("full_backup", str(destination), stdout=stdout)
    assert raised.value is failure
    assert "Backup created at" not in stdout.getvalue()
    assert_source_contents(backup_source, FILES)


def test_backup_reports_asset_zip_write_failure(backup_source, tmp_path):
    destination = tmp_path / "backup.zip"
    stdout = StringIO()
    failure = OSError("asset zip write failed")
    original_write = ZipFile.write

    def write(archive, filename, arcname):
        if Path(arcname).as_posix() == "assets/a.txt":
            assert archive.getinfo("db.sqlite3").file_size > 0
            raise failure
        return original_write(archive, filename, arcname)

    with patch.object(ZipFile, "write", write), pytest.raises(OSError) as raised:
        call_command("full_backup", str(destination), stdout=stdout)
    assert raised.value is failure
    assert "Backup created at" not in stdout.getvalue()
    assert_source_contents(backup_source, FILES)
