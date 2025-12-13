# Releasing Nugget

Nugget публикуется в виде **desktop-артефактов PyInstaller** через GitHub Actions (`.github/workflows/build.yml`).

## Быстрый релиз (рекомендуется)

1. Убедитесь, что `main_app.py`, ресурсы (`resources.qrc`) и UI (`qt/mainwindow.ui`) актуальны.
2. Поставьте git tag формата `vX.Y.Z` и отправьте его:
   - `git tag v7.1.0`
   - `git push origin v7.1.0`
3. Workflow `Build Nugget` соберёт артефакты для macOS/Windows/Linux и автоматически создаст GitHub Release с файлами.

## Ручная сборка (локально)

- macOS: `./build_macos.sh`
- Любая ОС: `python compile.py`

## Артефакты релиза

В релиз прикладываются:
- macOS: `Nugget_macOS_arm.zip`, `Nugget_macOS_intel.zip` + `.sha256`
- Windows: `Nugget_Windows.zip` + `.sha256`
- Linux: `Nugget_Linux.tar.xz` + `.sha256` и экспериментальный `Nugget_Linux.AppImage` + `.sha256`

## Code signing / Notarization (macOS)

Сборка поддерживает подпись через переменную окружения:
- `NUGGET_CODESIGN_HASH` — identity hash / название сертификата, подходящее для `--codesign-identity`.

Для CI нужно настроить секреты и шаги импорта сертификата/нотаризации (если включаете):
- сертификат Developer ID Application в `.p12` (base64)
- пароль к `.p12`
- Apple notarization (Apple ID + app-specific password) или App Store Connect API key

Примечание: в текущем CI шаги подписи/нотаризации **не включены автоматически** без секретов — это делается намеренно, чтобы workflow работал в fork’ах и без приватных ключей.

## Lock dependencies

Есть lock-файл `requirements.lock`, генерируемый из `requirements.in`:
- обновление: активируйте venv и выполните `pip-compile --output-file requirements.lock requirements.in`
- инструменты: `pip-tools` (см. `requirements-dev.txt`)

