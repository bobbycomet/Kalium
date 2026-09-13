"""Application configuration and managed prefix tracking."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


def get_home() -> Path:
    return Path.home()


def normalize_path_for_steam(path: str) -> str:
    """Map /var/home/... to /home/... for pressure-vessel compatibility."""
    if path.startswith("/var/home/"):
        return "/home/" + path[len("/var/home/") :]
    return path


class ManagerType(str, Enum):
    MO2 = "MO2"
    PLUGIN = "Plugin"

    def display_name(self) -> str:
        return self.value


@dataclass
class AppConfig:
    selected_proton: Optional[str] = None
    first_run_completed: bool = False
    data_path: str = field(default_factory=lambda: str(get_home() / "Kalium"))
    steam_migration_shown: bool = False
    cache_location: str = ""
    selected_steam_account: str = ""
    custom_steam_path: str = ""
    # Nexus API key for collections / authenticated downloads (optional)
    nexus_api_key: str = ""

    @staticmethod
    def config_dir() -> Path:
        return get_home() / ".config" / "kalium"

    @staticmethod
    def config_path() -> Path:
        return AppConfig.config_dir() / "config.json"

    @staticmethod
    def default_cache_dir() -> Path:
        return get_home() / ".cache" / "kalium"

    @staticmethod
    def tmp_path() -> Path:
        return AppConfig.default_cache_dir() / "tmp"

    @staticmethod
    def bin_path() -> Path:
        return AppConfig.config_dir() / "bin"

    def cache_dir(self) -> Path:
        if self.cache_location:
            return Path(self.cache_location)
        return AppConfig.default_cache_dir()

    def get_data_path(self) -> Path:
        return Path(self.data_path)

    def get_prefixes_path(self) -> Path:
        return self.get_data_path() / "Prefixes"

    @classmethod
    def load(cls) -> "AppConfig":
        path = cls.config_path()
        # Migrate from legacy NaK config if present
        legacy = get_home() / ".config" / "nak" / "config.json"
        if not path.exists() and legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                cfg = cls._from_dict(data)
                cfg.save()
                return cfg
            except Exception:
                pass
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls._from_dict(data)
            except Exception:
                pass
        return cls()

    @classmethod
    def _from_dict(cls, data: dict) -> "AppConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def save(self) -> None:
        path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def ensure_dirs(self) -> None:
        for d in (self.config_dir(), self.bin_path(), self.tmp_path(), self.cache_dir()):
            d.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(d, 0o700)
            except OSError:
                pass


@dataclass
class ManagedPrefix:
    app_id: int
    name: str
    prefix_path: str
    install_path: str
    manager_type: str
    library_path: str
    created: str = ""
    proton_config_name: Optional[str] = None


class ManagedPrefixes:
    @staticmethod
    def _path() -> Path:
        return AppConfig.config_dir() / "managed_prefixes.json"

    @classmethod
    def load(cls) -> list[ManagedPrefix]:
        path = cls._path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = []
            for item in data.get("prefixes", []):
                result.append(
                    ManagedPrefix(
                        app_id=int(item["app_id"]),
                        name=item.get("name", ""),
                        prefix_path=item.get("prefix_path", ""),
                        install_path=item.get("install_path", ""),
                        manager_type=item.get("manager_type", "MO2"),
                        library_path=item.get("library_path", ""),
                        created=item.get("created", ""),
                        proton_config_name=item.get("proton_config_name"),
                    )
                )
            return result
        except Exception:
            return []

    @classmethod
    def save(cls, prefixes: list[ManagedPrefix]) -> None:
        path = cls._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "prefixes": [
                {
                    "app_id": p.app_id,
                    "name": p.name,
                    "prefix_path": p.prefix_path,
                    "install_path": p.install_path,
                    "manager_type": p.manager_type,
                    "library_path": p.library_path,
                    "created": p.created,
                    "proton_config_name": p.proton_config_name,
                }
                for p in prefixes
            ]
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def register(
        cls,
        app_id: int,
        name: str,
        prefix_path: str,
        install_path: str,
        manager_type: ManagerType | str,
        library_path: str,
        proton_config_name: Optional[str] = None,
    ) -> None:
        prefixes = [p for p in cls.load() if p.app_id != app_id]
        mt = manager_type.value if isinstance(manager_type, ManagerType) else str(manager_type)
        prefixes.append(
            ManagedPrefix(
                app_id=app_id,
                name=name,
                prefix_path=prefix_path,
                install_path=install_path,
                manager_type=mt,
                library_path=library_path,
                created=datetime.now(timezone.utc).isoformat(),
                proton_config_name=proton_config_name,
            )
        )
        cls.save(prefixes)

    @classmethod
    def unregister(cls, app_id: int) -> None:
        cls.save([p for p in cls.load() if p.app_id != app_id])

    @classmethod
    def update_proton(cls, app_id: int, proton_config_name: str) -> None:
        prefixes = cls.load()
        for p in prefixes:
            if p.app_id == app_id:
                p.proton_config_name = proton_config_name
                break
        cls.save(prefixes)

    @classmethod
    def delete_prefix(cls, app_id: int) -> None:
        prefixes = cls.load()
        target = next((p for p in prefixes if p.app_id == app_id), None)
        if not target:
            raise ValueError("Prefix not found")
        pfx = Path(target.prefix_path)
        if pfx.is_symlink():
            raise ValueError("Refusing to delete symlink prefix")
        appid_folder = pfx.parent
        if appid_folder.is_symlink():
            raise ValueError("Refusing to delete symlink parent")
        if appid_folder.exists():
            shutil.rmtree(appid_folder, ignore_errors=True)
        cls.unregister(app_id)
