"""Read the latest App release and its downloadable Windows package from GitHub."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class UpdateCheckError(RuntimeError):
    """Raised when release information cannot be retrieved or parsed."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    digest: str | None = None


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    url: str
    notes: str
    assets: tuple[ReleaseAsset, ...]


def version_tuple(value: str) -> tuple[int, ...]:
    normalized = value.strip().removeprefix("v").removeprefix("V")
    if not re.fullmatch(r"\d+(?:\.\d+)*", normalized):
        raise UpdateCheckError(f"Не удалось разобрать номер версии: {value!r}")
    return tuple(int(part) for part in normalized.split("."))


class GitHubReleaseService:
    """Read the latest stable release from a public GitHub repository."""

    def __init__(self, repository: str) -> None:
        self.repository = repository.strip().strip("/")

    def latest_release(self) -> ReleaseInfo:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise UpdateCheckError(
                "Укажите публичный GitHub-репозиторий в config.json в формате owner/repo."
            )

        request = Request(
            f"https://api.github.com/repos/{self.repository}/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "GTA5RP-Helper-Launcher",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as error:
            if error.code == 404:
                raise UpdateCheckError("В репозитории пока нет опубликованного стабильного релиза.") from error
            raise UpdateCheckError(f"GitHub вернул HTTP {error.code} при проверке обновлений.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise UpdateCheckError(f"Не удалось связаться с GitHub: {error}") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise UpdateCheckError("GitHub вернул ответ, который Launcher не смог прочитать.") from error

        tag = payload.get("tag_name")
        release_url = payload.get("html_url")
        if not isinstance(tag, str) or not isinstance(release_url, str):
            raise UpdateCheckError("В ответе GitHub отсутствуют tag_name или html_url.")
        version_tuple(tag)

        assets: list[ReleaseAsset] = []
        for asset in payload.get("assets", []):
            if not isinstance(asset, dict):
                continue
            name = asset.get("name")
            download_url = asset.get("browser_download_url")
            digest = asset.get("digest")
            if isinstance(name, str) and isinstance(download_url, str):
                assets.append(
                    ReleaseAsset(name, download_url, digest if isinstance(digest, str) else None)
                )

        notes = payload.get("body")
        return ReleaseInfo(
            tag,
            release_url,
            notes if isinstance(notes, str) else "",
            tuple(assets),
        )
