"""Download, install, and launch the separately released App package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from shared.update_service import GitHubReleaseService, ReleaseInfo, UpdateCheckError, version_tuple


APP_ARCHIVE_NAME = "GTA5RP-Helper-App-Windows.zip"
APP_EXECUTABLE_NAME = "GTA5RP-Helper-App.exe"
ProgressCallback = Callable[[int, int], None]


class AppManager:
    def __init__(self, repository: str) -> None:
        self.release_service = GitHubReleaseService(repository)
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.app_root = local_app_data / "GTA5RP_Helper" / "App"
        self.versions_dir = self.app_root / "versions"
        self.state_path = self.app_root / "active.json"

    def installed_executable(self) -> Path | None:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            version = str(state["version"])
            directory_name = ".".join(str(part) for part in version_tuple(version))
        except (OSError, KeyError, TypeError, json.JSONDecodeError, UpdateCheckError):
            return None
        executable = self.versions_dir / directory_name / APP_EXECUTABLE_NAME
        return executable if executable.is_file() else None

    def ensure_latest(self, progress: ProgressCallback | None = None) -> tuple[Path, str]:
        release = self.release_service.latest_release()
        installed = self.installed_executable()
        if installed is not None:
            current_version = json.loads(self.state_path.read_text(encoding="utf-8"))["version"]
            if version_tuple(release.version) <= version_tuple(str(current_version)):
                return installed, f"Запускается App {current_version}. Обновлений нет."

        asset = next((item for item in release.assets if item.name == APP_ARCHIVE_NAME), None)
        if asset is None:
            raise UpdateCheckError(
                f"В релизе {release.version} отсутствует файл {APP_ARCHIVE_NAME}."
            )
        executable = self._install_release(release, asset.download_url, asset.digest, progress)
        return executable, f"App {release.version} скачан и установлен."

    def _install_release(
        self,
        release: ReleaseInfo,
        download_url: str,
        expected_digest: str | None,
        progress: ProgressCallback | None,
    ) -> Path:
        version = ".".join(str(part) for part in version_tuple(release.version))
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        archive_path: Path | None = None
        staging_dir: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="app-update-", suffix=".zip", dir=self.app_root, delete=False
            ) as archive:
                archive_path = Path(archive.name)
                self._download(download_url, archive, expected_digest, progress)

            staging_dir = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.versions_dir))
            self._extract_archive(archive_path, staging_dir)
            executable = staging_dir / APP_EXECUTABLE_NAME
            if not executable.is_file():
                raise UpdateCheckError(
                    f"В архиве не найден {APP_EXECUTABLE_NAME}. Соберите App в формате PyInstaller onedir."
                )

            destination = self.versions_dir / version
            if destination.exists():
                shutil.rmtree(destination)
            staging_dir.replace(destination)
            staging_dir = None

            state_temp = self.state_path.with_suffix(".tmp")
            state_temp.write_text(json.dumps({"version": release.version}), encoding="utf-8")
            os.replace(state_temp, self.state_path)
            return destination / APP_EXECUTABLE_NAME
        finally:
            if archive_path is not None:
                archive_path.unlink(missing_ok=True)
            if staging_dir is not None and staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    @staticmethod
    def _download(
        download_url: str,
        target,
        expected_digest: str | None,
        progress: ProgressCallback | None,
    ) -> None:
        request = Request(
            download_url,
            headers={"User-Agent": "GTA5RP-Helper-Launcher", "Accept": "application/octet-stream"},
        )
        digest = hashlib.sha256()
        downloaded = 0
        try:
            with urlopen(request, timeout=30) as response:
                total = int(response.headers.get("Content-Length", "0"))
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    if progress is not None:
                        progress(downloaded, total)
        except Exception as error:
            raise UpdateCheckError(f"Не удалось скачать App с GitHub: {error}") from error

        if expected_digest and expected_digest.startswith("sha256:"):
            expected = expected_digest.removeprefix("sha256:").lower()
            if digest.hexdigest().lower() != expected:
                raise UpdateCheckError("Контрольная сумма App не совпала; скачанный архив удалён.")

    @staticmethod
    def _extract_archive(archive_path: Path, destination: Path) -> None:
        root = destination.resolve()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for item in archive.infolist():
                    output_path = (destination / item.filename).resolve()
                    if not output_path.is_relative_to(root):
                        raise UpdateCheckError("Архив App содержит недопустимый путь.")
                    if item.is_dir():
                        output_path.mkdir(parents=True, exist_ok=True)
                        continue
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, output_path.open("wb") as target:
                        shutil.copyfileobj(source, target)
        except (zipfile.BadZipFile, OSError) as error:
            raise UpdateCheckError(f"Не удалось распаковать архив App: {error}") from error

    @staticmethod
    def launch(executable: Path) -> None:
        subprocess.Popen([str(executable)], cwd=executable.parent, close_fds=True)
