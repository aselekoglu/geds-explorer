from __future__ import annotations

from geds_crawler import cli
from test_ui_queries import _create_snapshot


class FakeServer:
    def __init__(self):
        self.server_address = ("0.0.0.0", 8765)
        self.served = False
        self.closed = False

    def serve_forever(self):
        self.served = True

    def server_close(self):
        self.closed = True


def test_ui_command_uses_loopback_default_and_serves(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "snapshot.sqlite"
    _create_snapshot(db_path)
    fake = FakeServer()
    called = {}

    def fake_create_server(path, host, port):
        called.update(path=path, host=host, port=port)
        return fake

    monkeypatch.setattr(cli, "create_server", fake_create_server)

    result = cli.main(["ui", "--db", str(db_path)])

    assert result == 0
    assert called == {"path": db_path, "host": "127.0.0.1", "port": 8765}
    assert fake.served
    assert fake.closed
    assert "http://127.0.0.1:8765" in capsys.readouterr().out


def test_ui_command_reports_missing_database(tmp_path, capsys):
    missing = tmp_path / "missing.sqlite"

    result = cli.main(["ui", "--db", str(missing)])

    assert result == 2
    assert "Database not found:" in capsys.readouterr().err
