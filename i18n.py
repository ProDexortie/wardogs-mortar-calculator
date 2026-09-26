"""
Модуль интернационализации и локализации интерфейса (i18n).

Архитектурное решение для сборки PyInstaller (--onefile):
Словари локализации хранятся в виде скомпилированного Python-модуля (внутри PYZ-архива),
а не во внешних JSON/YAML файлах. Это гарантирует:
1. Нулевую задержку ввода-вывода (Zero Disk I/O) при старте и переключении языка «на лету».
2. Автоматическое включение локалей в граф импортов PyInstaller без риска потери
   ресурсов при отсутствии флагов `--add-data` или очистки временной директории `_MEIPASS`.
3. Отсутствие лишних внешних зависимостей (таких как PyYAML).
"""

from __future__ import annotations
from typing import Any, Final

DEFAULT_LANGUAGE: Final[str] = "ru"
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("ru", "en")

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "ru": {
        "mode_combat": "● БОЕВОЙ",
        "mode_settings": "⚙ НАСТРОЙКА",
        "hint_setup": "Настр.",
        "hint_hide": "Скрыть",
        "col_azimuth": "АЗИМУТ",
        "col_elevation": "ПРИЦЕЛ",
        "col_distance": "ДИСТАНЦИЯ",
        "unit_m": "м",
        "gun_label": "ОРУДИЕ",
        "target_label": "ЦЕЛЬ",
        "preview_placeholder": "OCR\nПРЕВЬЮ",
        "status_idle": "Наведите перекрестие: {gun} — Орудие, {target} — Цель",
        "status_scanning_gun": "Сканирование ОРУДИЯ...",
        "status_scanning_target": "Сканирование ЦЕЛИ...",
        "status_ocr_fail": "Не распознано (X/Y). Наведите точнее на перекрестие.",
        "status_gun_saved": "Орудие записано: X={x:.2f}, Y={y:.2f}",
        "status_target_saved": "Цель записана: X={x:.2f}, Y={y:.2f}",
        "status_rebind_wait": "Нажмите любую клавишу для назначения (ESC — отмена)...",
        "status_rebind_ok": "Назначена клавиша [ {key} ]",
        "status_rebind_cancel": "Назначение клавиши отменено",
        "lbl_language": "Язык интерфейса:",
        "lbl_opacity": "Непрозрачность:",
        "lbl_capture": "Область захвата:",
        "chk_preview": "Показывать мини-превью OCR",
        "lbl_hotkeys_header": "Горячие клавиши (нажмите на ячейку и нажмите клавишу):",
        "hk_gun": "Орудие:",
        "hk_target": "Цель:",
        "hk_edit": "Настр.:",
        "hk_hide": "Скрыть:",
    },
    "en": {
        "mode_combat": "● COMBAT",
        "mode_settings": "⚙ SETTINGS",
        "hint_setup": "Setup",
        "hint_hide": "Hide",
        "col_azimuth": "AZIMUTH",
        "col_elevation": "ELEVATION",
        "col_distance": "DISTANCE",
        "unit_m": "m",
        "gun_label": "MORTAR",
        "target_label": "TARGET",
        "preview_placeholder": "OCR\nPREVIEW",
        "status_idle": "Hover crosshair: {gun} — Mortar, {target} — Target",
        "status_scanning_gun": "Scanning MORTAR...",
        "status_scanning_target": "Scanning TARGET...",
        "status_ocr_fail": "Failed to read (X/Y). Align crosshair clearly.",
        "status_gun_saved": "Mortar saved: X={x:.2f}, Y={y:.2f}",
        "status_target_saved": "Target saved: X={x:.2f}, Y={y:.2f}",
        "status_rebind_wait": "Press any key to bind (ESC to cancel)...",
        "status_rebind_ok": "Bound key [ {key} ]",
        "status_rebind_cancel": "Key binding canceled",
        "lbl_language": "Language:",
        "lbl_opacity": "Opacity:",
        "lbl_capture": "Capture Area:",
        "chk_preview": "Show OCR Mini-Preview",
        "lbl_hotkeys_header": "Hotkeys (click a slot and press any key):",
        "hk_gun": "Mortar:",
        "hk_target": "Target:",
        "hk_edit": "Setup:",
        "hk_hide": "Hide:",
    },
}


class Localizer:
    """
    Сервис локализации пользовательского интерфейса.
    Обеспечивает безопасное получение переведённых строк с каскадным фоллбэком
    (выбранный язык -> язык по умолчанию -> ключ) и форматированием параметров.
    """

    def __init__(self, lang: str = DEFAULT_LANGUAGE) -> None:
        self._lang = self._normalize_lang(lang)

    @staticmethod
    def _normalize_lang(lang: str) -> str:
        normalized = str(lang or DEFAULT_LANGUAGE).strip().lower()
        return normalized if normalized in TRANSLATIONS else DEFAULT_LANGUAGE

    @property
    def language(self) -> str:
        """Текущий активный код языка ('ru' или 'en')."""
        return self._lang

    def set_language(self, lang: str) -> str:
        """Устанавливает активный язык интерфейса и возвращает применённый код языка."""
        self._lang = self._normalize_lang(lang)
        return self._lang

    def get(self, key: str, **kwargs: Any) -> str:
        """
        Возвращает локализованную строку по ключу `key`.
        Если переданы именованные аргументы `kwargs`, выполняет безопасное форматирование.
        """
        catalog = TRANSLATIONS.get(self._lang, TRANSLATIONS[DEFAULT_LANGUAGE])
        template = catalog.get(key)
        if template is None:
            template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)

        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, ValueError, IndexError):
                return template
        return template

    def __call__(self, key: str, **kwargs: Any) -> str:
        """Позволяет вызывать экземпляр локализатора напрямую: `self.i18n('gun_label')`."""
        return self.get(key, **kwargs)
