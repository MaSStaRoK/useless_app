# GTA5RP Helper

Проект состоит из двух Windows-приложений:

- **Launcher** — стабильное небольшое приложение, которое проверяет GitHub Releases, скачивает свежий App и запускает его.
- **App** — основное приложение с инструментами. Оно обновляется чаще и устанавливается в `%LOCALAPPDATA%\GTA5RP_Helper\App`.

Launcher получает последнюю стабильную версию App из публичного GitHub-репозитория. Каждый App-релиз должен содержать архив `GTA5RP-Helper-App-Windows.zip`. Launcher проверяет SHA-256, если GitHub предоставляет digest, распаковывает архив и запускает `GTA5RP-Helper-App.exe`. Старые версии App сохраняются, поэтому при проблемах с сетью можно запустить уже установленную версию.

## Настройка GitHub

Укажи публичный репозиторий в `config.json`:

```json
{
  "github_repository": "your-name/GTA5RP-Helper"
}
```

В App-релиз прикрепляй архив с точным именем `GTA5RP-Helper-App-Windows.zip`. Внутри архива `GTA5RP-Helper-App.exe` должен находиться в корне вместе с остальными файлами PyInstaller onedir-сборки.

Версия App задаётся тегом релиза, например `v0.1.1`. Launcher использует `/releases/latest`, поэтому для автоматической установки подходят стабильные релизы без пометки prerelease.

## Запуск из исходников

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py          # основное приложение
python launcher_main.py # Launcher
```

## Сборка App

Выполни из корня проекта в PowerShell:

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name GTA5RP-Helper-App `
  --add-data "data;data" `
  main.py
Compress-Archive -Path "dist\GTA5RP-Helper-App\*" `
  -DestinationPath "dist\GTA5RP-Helper-App-Windows.zip" -Force
```

Загрузи `dist\GTA5RP-Helper-App-Windows.zip` как asset нового GitHub Release. После публикации Launcher обнаружит релиз и обновит App при следующем запуске.

## Сборка Launcher

Собери Launcher отдельно и распространяй его реже:

```powershell
pyinstaller --noconfirm --clean --windowed --name GTA5RP-Helper-Launcher `
  --add-data "config.json;." `
  launcher_main.py
Copy-Item "config.json" "dist\GTA5RP-Helper-Launcher\config.json" -Force
```

Распространяй всю папку `dist\GTA5RP-Helper-Launcher`. `config.json` должен лежать рядом с Launcher, чтобы репозиторий можно было менять без пересборки.

## Структура

- `launcher_main.py` — точка входа Launcher.
- `launcher/app_manager.py` — скачивание, проверка и установка App.
- `launcher/update_window.py` — окно Launcher.
- `main.py` — отдельная точка входа основного App.
- `app/` — окно App и инструменты.
- `shared/update_service.py` — чтение последнего GitHub Release.
