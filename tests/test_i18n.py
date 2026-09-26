import unittest
from i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, TRANSLATIONS, Localizer


class TestLocalizer(unittest.TestCase):
    def test_catalog_keys_parity(self) -> None:
        """Проверяет полное совпадение набора ключей во всех поддерживаемых языках."""
        base_keys = set(TRANSLATIONS[DEFAULT_LANGUAGE].keys())
        self.assertGreater(len(base_keys), 0)
        for lang in SUPPORTED_LANGUAGES:
            self.assertIn(lang, TRANSLATIONS)
            self.assertEqual(
                set(TRANSLATIONS[lang].keys()),
                base_keys,
                f"Несовпадение ключей локализации для языка '{lang}'",
            )

    def test_language_switching_and_fallback(self) -> None:
        """Проверяет переключение языка и безопасный фоллбэк при неизвестном коде языка/ключа."""
        loc = Localizer("ru")
        self.assertEqual(loc.language, "ru")
        self.assertEqual(loc("gun_label"), "ОРУДИЕ")

        loc.set_language("EN")
        self.assertEqual(loc.language, "en")
        self.assertEqual(loc("gun_label"), "MORTAR")

        # Неизвестный язык должен безопасно откатываться к DEFAULT_LANGUAGE ('ru')
        loc.set_language("de")
        self.assertEqual(loc.language, DEFAULT_LANGUAGE)
        self.assertEqual(loc("gun_label"), "ОРУДИЕ")

        # Неизвестный ключ должен возвращать сам ключ без выброса исключения
        self.assertEqual(loc("non_existent_key"), "non_existent_key")

    def test_string_formatting(self) -> None:
        """Проверяет подстановку именованных параметров в шаблоны локализации."""
        loc = Localizer("en")
        formatted = loc("status_gun_saved", x=80.25, y=38.5)
        self.assertEqual(formatted, "Mortar saved: X=80.25, Y=38.50")


if __name__ == "__main__":
    unittest.main()
