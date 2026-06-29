"""The live SDK adapter (`SdkLettaClient`) against a stubbed ``letta_client``.

CI runs offline, so this stubs ``letta_client.Letta`` into ``sys.modules``. The
stub mirrors the signature verified against letta-client 1.12.1: archives.list
(by name) / create (-> object with .id) / delete, and
archives.passages.create(archive_id, text=, metadata=). The adapter resolves the
opaque archive_id from the container name, which the stub exercises.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from rac_connectors.letta.client import MissingCredentialsError, SdkLettaClient


class _Archive:
    def __init__(self, archive_id: str, name: str) -> None:
        self.id = archive_id
        self.name = name


class _Passages:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    def create(self, archive_id: str, **kwargs: Any) -> None:
        self.created.append({"archive_id": archive_id, **kwargs})


class _Archives:
    def __init__(self) -> None:
        self._by_name: dict[str, _Archive] = {}
        self.deleted: list[str] = []
        self.passages = _Passages()
        self._counter = 0

    def list(self, *, name: str) -> list[_Archive]:
        return [a for a in self._by_name.values() if a.name == name]

    def create(self, *, name: str) -> _Archive:
        self._counter += 1
        archive = _Archive(f"arch-{self._counter}", name)
        self._by_name[name] = archive
        return archive

    def delete(self, archive_id: str) -> None:
        self.deleted.append(archive_id)
        self._by_name = {n: a for n, a in self._by_name.items() if a.id != archive_id}


class _StubLetta:
    last: _StubLetta | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.archives = _Archives()
        _StubLetta.last = self


@pytest.fixture
def stub_letta(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("letta_client")
    module.Letta = _StubLetta  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "letta_client", module)
    _StubLetta.last = None


def test_clear_creates_archive_and_add_uses_its_id(stub_letta: None) -> None:
    client = SdkLettaClient(api_key="k")
    client.clear_container(container="rac")
    client.add(text="body", container="rac", metadata={"lore_id": "RAC-1"})

    archives = _StubLetta.last.archives
    passage = archives.passages.created[0]
    # The passage was written to the freshly-created archive's id.
    assert passage["archive_id"] == "arch-1"
    assert passage["text"] == "body"
    assert passage["metadata"] == {"lore_id": "RAC-1"}


def test_clear_deletes_existing_archive_of_same_name(stub_letta: None) -> None:
    client = SdkLettaClient(api_key="k")
    client.clear_container(container="rac")  # creates arch-1
    client.clear_container(container="rac")  # must delete arch-1, create arch-2
    archives = _StubLetta.last.archives
    assert "arch-1" in archives.deleted
    assert client._archive_ids["rac"] == "arch-2"


def test_api_key_passed_to_client(stub_letta: None) -> None:
    client = SdkLettaClient(api_key="k-123")
    client.clear_container(container="rac")
    assert _StubLetta.last.kwargs == {"api_key": "k-123"}


def test_base_url_only_is_allowed(
    monkeypatch: pytest.MonkeyPatch, stub_letta: None
) -> None:
    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    client = SdkLettaClient(base_url="http://localhost:8283")
    client.clear_container(container="rac")
    assert _StubLetta.last.kwargs == {"base_url": "http://localhost:8283"}


def test_missing_credentials_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    monkeypatch.delenv("LETTA_BASE_URL", raising=False)
    with pytest.raises(MissingCredentialsError):
        SdkLettaClient()
