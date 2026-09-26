import ctypes
import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional
from PIL import Image, ImageTk

from ballistics import MIN_RANGE_M, MAX_RANGE_M, calculate_ballistics
from i18n import DEFAULT_LANGUAGE, Localizer
from ocr_scanner_lite import LiteCoordinateScanner, LiteScanResult

# Включаем Per-Monitor DPI Awareness для точного совпадения физических пикселей экрана
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_resource_path(relative_path: str) -> Path:
    """Возвращает путь к ресурсу как при обычном запуске, так и внутри PyInstaller .exe."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path


CONFIG_PATH = Path(os.path.expanduser("~")) / ".wardogs_artillery_overlay_lite.json"

DEFAULT_CONFIG = {
    "pos_x": 40,
    "pos_y": 40,
    "opacity": 0.88,
    "capture_size": 320,
    "show_preview": True,
    "lang": DEFAULT_LANGUAGE,
    "hotkey_gun": "F1",
    "hotkey_target": "F2",
    "hotkey_edit": "F3",
    "hotkey_hide": "F4",
}

# Полная таблица виртуальных кодов клавиш Win32 (VK_*) для назначения и опроса как в играх
VK_MAP: dict[str, int] = {
    **{f"F{i}": 0x70 + (i - 1) for i in range(1, 13)},
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): ord(str(d)) for d in range(0, 10)},
    "NUM0": 0x60,
    "NUM1": 0x61,
    "NUM2": 0x62,
    "NUM3": 0x63,
    "NUM4": 0x64,
    "NUM5": 0x65,
    "NUM6": 0x66,
    "NUM7": 0x67,
    "NUM8": 0x68,
    "NUM9": 0x69,
    "NUM*": 0x6A,
    "NUM+": 0x6B,
    "NUM-": 0x6D,
    "NUM.": 0x6E,
    "NUM/": 0x6F,
    "INS": 0x2D,
    "DEL": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PGUP": 0x21,
    "PGDN": 0x22,
    "TILDE": 0xC0,
    "TAB": 0x09,
    "CAPS": 0x14,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "ALT": 0x12,
    "SPACE": 0x20,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
    "MMB": 0x04,      # Средняя кнопка мыши (колесо)
    "MOUSE4": 0x05,   # Боковая кнопка мыши Назад
    "MOUSE5": 0x06,   # Боковая кнопка мыши Вперёд
}

VK_ESCAPE = 0x1B

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


class LiteArtilleryOverlay:
    def __init__(self) -> None:
        self.config = self._load_config()
        self.i18n = Localizer(self.config.get("lang", DEFAULT_LANGUAGE))
        self.scanner = LiteCoordinateScanner()
        self.result_queue: queue.Queue[tuple[str, LiteScanResult]] = queue.Queue()
        self._scan_lock = threading.Lock()

        self.gun_x: Optional[float] = None
        self.gun_y: Optional[float] = None
        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None

        self.is_edit_mode = False
        self.is_hidden = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._photo_ref: Optional[ImageTk.PhotoImage] = None
        self._logo_ref: Optional[ImageTk.PhotoImage] = None

        # Состояние бинда клавиш (какой слот сейчас ждёт нажатия клавиши)
        self._rebinding_slot: Optional[str] = None
        self._hk_buttons: dict[str, tk.Button] = {}
        self._hk_slot_labels: dict[str, tk.Label] = {}
        self._vk_prev_down: dict[int, bool] = {}

        self.root = tk.Tk()
        self._init_window()
        self._build_ui()

        self.root.update_idletasks()
        self._apply_click_through(True)

        # Инициализируем базовое состояние всех клавиш
        for vk in list(VK_MAP.values()) + [VK_ESCAPE]:
            self._vk_prev_down[vk] = bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

        self.root.after(25, self._poll_loop)

    def _tr(self, key: str, **kwargs: object) -> str:
        return self.i18n.get(key, **kwargs)

    def _load_config(self) -> dict:
        cfg = DEFAULT_CONFIG.copy()
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update(data)
            except Exception:
                pass
        return cfg

    def _save_config(self) -> None:
        try:
            self.config["pos_x"] = self.root.winfo_x()
            self.config["pos_y"] = self.root.winfo_y()
            CONFIG_PATH.write_text(
                json.dumps(self.config, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def _init_window(self) -> None:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Wardogs.MortarCalculator.1"
            )
        except Exception:
            pass

        self.root.title("Wardogs Mortar Calculator")
        ico_path = get_resource_path("icon.ico")
        if ico_path.exists():
            try:
                self.root.iconbitmap(default=str(ico_path))
                self.root.iconbitmap(str(ico_path))
            except Exception:
                pass

        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", float(self.config.get("opacity", 0.88)))
        self.root.configure(bg="#0b0f19", highlightthickness=1, highlightbackground="#334155")
        self.root.geometry(f"+{int(self.config['pos_x'])}+{int(self.config['pos_y'])}")

        if ico_path.exists():
            try:
                hwnd = self._get_hwnd()
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x00000010
                WM_SETICON = 0x0080
                hicon_big = ctypes.windll.user32.LoadImageW(
                    0, str(ico_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE
                )
                hicon_small = ctypes.windll.user32.LoadImageW(
                    0, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
                )
                if hicon_big:
                    ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_big)
                if hicon_small:
                    ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)
            except Exception:
                pass

    def _get_hwnd(self) -> int:
        return ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()

    def _apply_click_through(self, click_through: bool) -> None:
        hwnd = self._get_hwnd()
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if click_through:
            new_style = ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            new_style = (ex_style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

    def _build_ui(self) -> None:
        self.main_frame = tk.Frame(self.root, bg="#0b0f19", padx=10, pady=8)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(self.main_frame, bg="#0b0f19")
        header.pack(fill=tk.X, pady=(0, 6))

        logo_path = get_resource_path("logo.png")
        if logo_path.exists():
            try:
                logo_img = Image.open(logo_path).resize((16, 16), Image.Resampling.LANCZOS)
                self._logo_ref = ImageTk.PhotoImage(logo_img)
                lbl_logo = tk.Label(header, image=self._logo_ref, bg="#0b0f19", bd=0)
                lbl_logo.pack(side=tk.LEFT, padx=(0, 5))
            except Exception:
                pass

        self.lbl_mode = tk.Label(
            header,
            text=self._tr("mode_combat"),
            bg="#0b0f19",
            fg="#34d399",
            font=("Segoe UI", 8, "bold"),
        )
        self.lbl_mode.pack(side=tk.LEFT)

        self.btn_close = tk.Button(
            header,
            text="×",
            bg="#451a1a",
            fg="#f87171",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            bd=0,
            padx=5,
            pady=0,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            command=self._quit,
        )

        self.lbl_hints = tk.Label(
            header,
            text=f"[{self.config['hotkey_edit']}] {self._tr('hint_setup')}  [{self.config['hotkey_hide']}] {self._tr('hint_hide')}",
            bg="#0b0f19",
            fg="#94a3b8",
            font=("Segoe UI", 8),
        )
        self.lbl_hints.pack(side=tk.RIGHT, padx=(0, 4))

        # Блок главных показателей (АЗИМУТ | ПРИЦЕЛ | ДИСТАНЦИЯ)
        metrics_box = tk.Frame(
            self.main_frame,
            bg="#111827",
            highlightthickness=1,
            highlightbackground="#1e293b",
            padx=8,
            pady=5,
        )
        metrics_box.pack(fill=tk.X, pady=(0, 6))

        self.lbl_col_az = tk.Label(
            metrics_box, text=self._tr("col_azimuth"), bg="#111827", fg="#64748b", font=("Segoe UI", 7, "bold")
        )
        self.lbl_col_az.grid(row=0, column=0, sticky="w")

        self.lbl_col_el = tk.Label(
            metrics_box, text=self._tr("col_elevation"), bg="#111827", fg="#64748b", font=("Segoe UI", 7, "bold")
        )
        self.lbl_col_el.grid(row=0, column=1, sticky="w", padx=(12, 0))

        self.lbl_col_dist = tk.Label(
            metrics_box, text=self._tr("col_distance"), bg="#111827", fg="#64748b", font=("Segoe UI", 7, "bold")
        )
        self.lbl_col_dist.grid(row=0, column=2, sticky="w", padx=(12, 0))

        self.lbl_azimuth = tk.Label(
            metrics_box,
            text="---.-°",
            bg="#111827",
            fg="#38bdf8",
            font=("Consolas", 15, "bold"),
        )
        self.lbl_azimuth.grid(row=1, column=0, sticky="w")

        self.lbl_mil = tk.Label(
            metrics_box,
            text="--- mil",
            bg="#111827",
            fg="#fbbf24",
            font=("Consolas", 15, "bold"),
        )
        self.lbl_mil.grid(row=1, column=1, sticky="w", padx=(12, 0))

        self.lbl_dist = tk.Label(
            metrics_box,
            text=f"--- {self._tr('unit_m')}",
            bg="#111827",
            fg="#f8fafc",
            font=("Consolas", 15, "bold"),
        )
        self.lbl_dist.grid(row=1, column=2, sticky="w", padx=(12, 0))

        # Координаты орудия и цели + мини-превью распознавания
        mid_frame = tk.Frame(self.main_frame, bg="#0b0f19")
        mid_frame.pack(fill=tk.X)

        coords_frame = tk.Frame(mid_frame, bg="#0b0f19")
        coords_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_gun_title = tk.Label(
            coords_frame,
            text=f"{self._tr('gun_label')} [{self.config['hotkey_gun']}]",
            bg="#0b0f19",
            fg="#94a3b8",
            font=("Segoe UI", 8, "bold"),
        )
        self.lbl_gun_title.grid(row=0, column=0, sticky="w", pady=2)

        self.ent_gun_x = self._make_coord_entry(coords_frame, "X: ---")
        self.ent_gun_x.grid(row=0, column=1, padx=(6, 3), pady=2)
        self.ent_gun_y = self._make_coord_entry(coords_frame, "Y: ---")
        self.ent_gun_y.grid(row=0, column=2, padx=3, pady=2)

        self.lbl_target_title = tk.Label(
            coords_frame,
            text=f"{self._tr('target_label')} [{self.config['hotkey_target']}]",
            bg="#0b0f19",
            fg="#94a3b8",
            font=("Segoe UI", 8, "bold"),
        )
        self.lbl_target_title.grid(row=1, column=0, sticky="w", pady=2)

        self.ent_target_x = self._make_coord_entry(coords_frame, "X: ---")
        self.ent_target_x.grid(row=1, column=1, padx=(6, 3), pady=2)
        self.ent_target_y = self._make_coord_entry(coords_frame, "Y: ---")
        self.ent_target_y.grid(row=1, column=2, padx=3, pady=2)

        # Мини-превью распознавания
        self.preview_lbl = tk.Label(
            mid_frame,
            text=self._tr("preview_placeholder"),
            bg="#111827",
            fg="#475569",
            font=("Segoe UI", 7),
            width=8,
            height=3,
            highlightthickness=1,
            highlightbackground="#1e293b",
        )
        if self.config.get("show_preview", True):
            self.preview_lbl.pack(side=tk.RIGHT, padx=(6, 0))

        # Статус-строка
        self.lbl_status = tk.Label(
            self.main_frame,
            text=self._tr("status_idle").format(
                gun=self.config["hotkey_gun"], target=self.config["hotkey_target"]
            ),
            bg="#0b0f19",
            fg="#64748b",
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.lbl_status.pack(fill=tk.X, pady=(4, 0))

        # Панель настроек
        self.settings_frame = tk.Frame(
            self.main_frame,
            bg="#111827",
            highlightthickness=1,
            highlightbackground="#1e293b",
            padx=8,
            pady=6,
        )

        # Выбор языка (RU / EN)
        lang_row = tk.Frame(self.settings_frame, bg="#111827")
        lang_row.pack(fill=tk.X, pady=(0, 3))
        self.lbl_lang_title = tk.Label(
            lang_row, text=self._tr("lbl_language"), bg="#111827", fg="#cbd5e1", font=("Segoe UI", 8)
        )
        self.lbl_lang_title.pack(side=tk.LEFT)

        self.btn_lang_en = tk.Button(
            lang_row,
            text="EN",
            width=4,
            bd=0,
            font=("Consolas", 8, "bold"),
            cursor="hand2",
            command=lambda: self._set_language("en"),
        )
        self.btn_lang_en.pack(side=tk.RIGHT, padx=(3, 0))

        self.btn_lang_ru = tk.Button(
            lang_row,
            text="RU",
            width=4,
            bd=0,
            font=("Consolas", 8, "bold"),
            cursor="hand2",
            command=lambda: self._set_language("ru"),
        )
        self.btn_lang_ru.pack(side=tk.RIGHT)
        self._update_lang_buttons_style()

        # Ползунок прозрачности
        op_row = tk.Frame(self.settings_frame, bg="#111827")
        op_row.pack(fill=tk.X, pady=2)
        self.lbl_op_title = tk.Label(
            op_row, text=self._tr("lbl_opacity"), bg="#111827", fg="#cbd5e1", font=("Segoe UI", 8)
        )
        self.lbl_op_title.pack(side=tk.LEFT)
        self.lbl_op_val = tk.Label(
            op_row,
            text=f"{int(float(self.config['opacity']) * 100)}%",
            bg="#111827",
            fg="#38bdf8",
            font=("Segoe UI", 8, "bold"),
            width=4,
        )
        self.lbl_op_val.pack(side=tk.RIGHT)
        self.scale_opacity = tk.Scale(
            op_row,
            from_=20,
            to=100,
            orient=tk.HORIZONTAL,
            showvalue=False,
            bg="#111827",
            troughcolor="#0b0f19",
            highlightthickness=0,
            bd=0,
            command=self._on_opacity_change,
        )
        self.scale_opacity.set(int(float(self.config["opacity"]) * 100))
        self.scale_opacity.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=6)

        # Ползунок области захвата
        cap_row = tk.Frame(self.settings_frame, bg="#111827")
        cap_row.pack(fill=tk.X, pady=2)
        self.lbl_cap_title = tk.Label(
            cap_row, text=self._tr("lbl_capture"), bg="#111827", fg="#cbd5e1", font=("Segoe UI", 8)
        )
        self.lbl_cap_title.pack(side=tk.LEFT)
        self.lbl_cap_val = tk.Label(
            cap_row,
            text=f"{int(self.config['capture_size'])}px",
            bg="#111827",
            fg="#38bdf8",
            font=("Segoe UI", 8, "bold"),
            width=5,
        )
        self.lbl_cap_val.pack(side=tk.RIGHT)
        self.scale_cap = tk.Scale(
            cap_row,
            from_=220,
            to=480,
            resolution=20,
            orient=tk.HORIZONTAL,
            showvalue=False,
            bg="#111827",
            troughcolor="#0b0f19",
            highlightthickness=0,
            bd=0,
            command=self._on_cap_change,
        )
        self.scale_cap.set(int(self.config["capture_size"]))
        self.scale_cap.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=6)

        # Чекбокс превью
        self.var_preview = tk.BooleanVar(value=bool(self.config.get("show_preview", True)))
        self.chk_preview_btn = tk.Checkbutton(
            self.settings_frame,
            text=self._tr("chk_preview"),
            variable=self.var_preview,
            bg="#111827",
            fg="#cbd5e1",
            selectcolor="#0b0f19",
            activebackground="#111827",
            activeforeground="#ffffff",
            font=("Segoe UI", 8),
            command=self._on_toggle_preview,
        )
        self.chk_preview_btn.pack(anchor="w", pady=2)

        # Блок назначения горячих клавиш
        self.lbl_hk_header = tk.Label(
            self.settings_frame,
            text=self._tr("lbl_hotkeys_header"),
            bg="#111827",
            fg="#94a3b8",
            font=("Segoe UI", 7, "bold"),
        )
        self.lbl_hk_header.pack(anchor="w", pady=(4, 2))

        hk_grid = tk.Frame(self.settings_frame, bg="#111827")
        hk_grid.pack(fill=tk.X, pady=(0, 2))

        self._create_game_keybind_slot(hk_grid, "hk_gun", "hotkey_gun", 0, 0)
        self._create_game_keybind_slot(hk_grid, "hk_target", "hotkey_target", 0, 2)
        self._create_game_keybind_slot(hk_grid, "hk_edit", "hotkey_edit", 1, 0)
        self._create_game_keybind_slot(hk_grid, "hk_hide", "hotkey_hide", 1, 2)

        # Перетаскивание окна мышью
        for w in (self.main_frame, header, self.lbl_mode, metrics_box):
            w.bind("<ButtonPress-1>", self._on_drag_start)
            w.bind("<B1-Motion>", self._on_drag_motion)
            w.bind("<ButtonRelease-1>", self._on_drag_end)

    def _update_lang_buttons_style(self) -> None:
        if self.i18n.language == "en":
            self.btn_lang_en.configure(bg="#0284c7", fg="#ffffff")
            self.btn_lang_ru.configure(bg="#1e293b", fg="#94a3b8")
        else:
            self.btn_lang_ru.configure(bg="#0284c7", fg="#ffffff")
            self.btn_lang_en.configure(bg="#1e293b", fg="#94a3b8")

    def _set_language(self, lang: str) -> None:
        active_lang = self.i18n.set_language(lang)
        self.config["lang"] = active_lang
        self._save_config()
        self._update_lang_buttons_style()

        self.lbl_mode.configure(
            text=self._tr("mode_settings") if self.is_edit_mode else self._tr("mode_combat")
        )
        self.lbl_col_az.configure(text=self._tr("col_azimuth"))
        self.lbl_col_el.configure(text=self._tr("col_elevation"))
        self.lbl_col_dist.configure(text=self._tr("col_distance"))

        if self._photo_ref is None:
            self.preview_lbl.configure(text=self._tr("preview_placeholder"))

        self.lbl_lang_title.configure(text=self._tr("lbl_language"))
        self.lbl_op_title.configure(text=self._tr("lbl_opacity"))
        self.lbl_cap_title.configure(text=self._tr("lbl_capture"))
        self.chk_preview_btn.configure(text=self._tr("chk_preview"))
        self.lbl_hk_header.configure(text=self._tr("lbl_hotkeys_header"))

        for tr_key, lbl_widget in self._hk_slot_labels.items():
            lbl_widget.configure(text=self._tr(tr_key))

        self._refresh_hotkey_labels()
        self.lbl_status.configure(
            text=self._tr("status_idle").format(
                gun=self.config["hotkey_gun"], target=self.config["hotkey_target"]
            ),
            fg="#64748b",
        )
        if None in (self.gun_x, self.gun_y, self.target_x, self.target_y):
            self.lbl_dist.configure(text=f"--- {self._tr('unit_m')}")
        else:
            self._recalculate()

    def _create_game_keybind_slot(
        self, parent: tk.Widget, label_tr_key: str, cfg_key: str, row: int, col: int
    ) -> None:
        lbl = tk.Label(
            parent, text=self._tr(label_tr_key), bg="#111827", fg="#cbd5e1", font=("Segoe UI", 8)
        )
        lbl.grid(row=row, column=col, sticky="w", padx=(0 if col == 0 else 10, 4), pady=2)
        self._hk_slot_labels[label_tr_key] = lbl

        cur_val = str(self.config.get(cfg_key, "F1")).upper()
        btn = tk.Button(
            parent,
            text=f"[ {cur_val} ]",
            width=10,
            bg="#1e293b",
            fg="#38bdf8",
            activebackground="#334155",
            activeforeground="#fbbf24",
            bd=0,
            highlightthickness=1,
            highlightbackground="#334155",
            font=("Consolas", 8, "bold"),
            cursor="hand2",
            command=lambda k=cfg_key: self._start_rebinding(k),
        )
        btn.grid(row=row, column=col + 1, sticky="ew", pady=2)
        self._hk_buttons[cfg_key] = btn

    def _start_rebinding(self, cfg_key: str) -> None:
        if self._rebinding_slot is not None and self._rebinding_slot in self._hk_buttons:
            prev_val = str(self.config.get(self._rebinding_slot, "")).upper()
            self._hk_buttons[self._rebinding_slot].configure(
                text=f"[ {prev_val} ]",
                bg="#1e293b",
                fg="#38bdf8",
                highlightbackground="#334155",
            )

        self._rebinding_slot = cfg_key
        btn = self._hk_buttons[cfg_key]
        btn.configure(
            text="[ ... ]",
            bg="#422006",
            fg="#fbbf24",
            highlightbackground="#fbbf24",
        )
        self.lbl_status.configure(
            text=self._tr("status_rebind_wait"),
            fg="#fbbf24",
        )

    def _finish_rebinding(self, new_key_name: Optional[str]) -> None:
        if self._rebinding_slot is None:
            return

        slot = self._rebinding_slot
        self._rebinding_slot = None
        btn = self._hk_buttons.get(slot)

        if new_key_name is not None:
            self.config[slot] = new_key_name
            self._save_config()
            self._refresh_hotkey_labels()
            self.lbl_status.configure(
                text=self._tr("status_rebind_ok").format(key=new_key_name), fg="#34d399"
            )
        else:
            self.lbl_status.configure(text=self._tr("status_rebind_cancel"), fg="#94a3b8")

        if btn is not None:
            final_val = str(self.config.get(slot, "")).upper()
            btn.configure(
                text=f"[ {final_val} ]",
                bg="#1e293b",
                fg="#38bdf8",
                highlightbackground="#334155",
            )

    def _refresh_hotkey_labels(self) -> None:
        self.lbl_gun_title.configure(text=f"{self._tr('gun_label')} [{self.config['hotkey_gun']}]")
        self.lbl_target_title.configure(text=f"{self._tr('target_label')} [{self.config['hotkey_target']}]")
        self.lbl_hints.configure(
            text=f"[{self.config['hotkey_edit']}] {self._tr('hint_setup')}  [{self.config['hotkey_hide']}] {self._tr('hint_hide')}"
        )

    def _make_coord_entry(self, parent: tk.Widget, default_text: str) -> tk.Entry:
        ent = tk.Entry(
            parent,
            width=9,
            bg="#111827",
            fg="#e2e8f0",
            readonlybackground="#111827",
            insertbackground="#38bdf8",
            bd=0,
            highlightthickness=1,
            highlightbackground="#1e293b",
            highlightcolor="#38bdf8",
            font=("Consolas", 9, "bold"),
        )
        ent.insert(0, default_text)
        ent.configure(state="readonly")
        ent.bind("<Return>", lambda e: self._apply_manual_coords())
        ent.bind("<FocusOut>", lambda e: self._apply_manual_coords())
        return ent

    def _set_entry_text(self, entry: tk.Entry, text: str) -> None:
        prev_state = str(entry.cget("state"))
        entry.configure(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, text)
        entry.configure(state=prev_state)

    def _on_opacity_change(self, val_str: str) -> None:
        val = int(float(val_str))
        self.config["opacity"] = round(val / 100.0, 2)
        self.lbl_op_val.configure(text=f"{val}%")
        self.root.wm_attributes("-alpha", self.config["opacity"])
        self._save_config()

    def _on_cap_change(self, val_str: str) -> None:
        val = int(float(val_str))
        self.config["capture_size"] = val
        self.lbl_cap_val.configure(text=f"{val}px")
        self._save_config()

    def _on_toggle_preview(self) -> None:
        show = bool(self.var_preview.get())
        self.config["show_preview"] = show
        if show:
            self.preview_lbl.pack(side=tk.RIGHT, padx=(6, 0))
        else:
            self.preview_lbl.pack_forget()
        self._save_config()

    def _apply_manual_coords(self) -> None:
        def parse_ent(ent: tk.Entry) -> Optional[float]:
            raw = ent.get().upper().replace("X:", "").replace("Y:", "").replace("-", "").replace(",", ".").strip()
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        gx = parse_ent(self.ent_gun_x)
        gy = parse_ent(self.ent_gun_y)
        tx = parse_ent(self.ent_target_x)
        ty = parse_ent(self.ent_target_y)

        if gx is not None:
            self.gun_x = gx
            self._set_entry_text(self.ent_gun_x, f"X:{gx:.2f}")
        if gy is not None:
            self.gun_y = gy
            self._set_entry_text(self.ent_gun_y, f"Y:{gy:.2f}")
        if tx is not None:
            self.target_x = tx
            self._set_entry_text(self.ent_target_x, f"X:{tx:.2f}")
        if ty is not None:
            self.target_y = ty
            self._set_entry_text(self.ent_target_y, f"Y:{ty:.2f}")

        self._recalculate()

    def _toggle_edit_mode(self) -> None:
        if self.is_hidden:
            self._toggle_visibility()

        if self._rebinding_slot is not None:
            self._finish_rebinding(None)

        self.is_edit_mode = not self.is_edit_mode
        new_state = "normal" if self.is_edit_mode else "readonly"
        for ent in (self.ent_gun_x, self.ent_gun_y, self.ent_target_x, self.ent_target_y):
            ent.configure(state=new_state)

        if self.is_edit_mode:
            self.lbl_mode.configure(text=self._tr("mode_settings"), fg="#38bdf8")
            self.root.configure(highlightbackground="#38bdf8")
            self.btn_close.pack(side=tk.RIGHT, padx=(4, 0))
            self.settings_frame.pack(fill=tk.X, pady=(6, 0))
            self._apply_click_through(False)
        else:
            self._apply_manual_coords()
            self.lbl_mode.configure(text=self._tr("mode_combat"), fg="#34d399")
            self.root.configure(highlightbackground="#334155")
            self.btn_close.pack_forget()
            self.settings_frame.pack_forget()
            self._apply_click_through(True)
            self._save_config()

    def _toggle_visibility(self) -> None:
        self.is_hidden = not self.is_hidden
        if self.is_hidden:
            self.root.withdraw()
        else:
            self.root.deiconify()
            self.root.wm_attributes("-topmost", True)
            self._apply_click_through(not self.is_edit_mode)

    def _start_scan_async(self, role: str) -> None:
        if self._scan_lock.locked():
            return
        cap_size = int(self.config.get("capture_size", 320))
        self.lbl_status.configure(
            text=self._tr("status_scanning_gun" if role == "gun" else "status_scanning_target"),
            fg="#38bdf8",
        )

        def worker() -> None:
            with self._scan_lock:
                try:
                    res = self.scanner.scan_around_cursor(capture_size=cap_size)
                except Exception as exc:
                    res = LiteScanResult(
                        success=False,
                        x=None,
                        y=None,
                        preview_image=Image.new("RGB", (64, 52), (17, 24, 39)),
                        raw_texts=[],
                        error_msg=str(exc),
                    )
                self.result_queue.put((role, res))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_scan_result(self, role: str, res: LiteScanResult) -> None:
        if res.preview_image is not None:
            thumb = res.preview_image.resize((64, 48), Image.Resampling.BILINEAR)
            self._photo_ref = ImageTk.PhotoImage(thumb)
            self.preview_lbl.configure(image=self._photo_ref, text="", width=64, height=48)

        if not res.success or res.x is None or res.y is None:
            self.lbl_status.configure(
                text=self._tr("status_ocr_fail"), fg="#f87171"
            )
            return

        if role == "gun":
            self.gun_x, self.gun_y = res.x, res.y
            self._set_entry_text(self.ent_gun_x, f"X:{res.x:.2f}")
            self._set_entry_text(self.ent_gun_y, f"Y:{res.y:.2f}")
            self.lbl_status.configure(
                text=self._tr("status_gun_saved").format(x=res.x, y=res.y), fg="#34d399"
            )
        else:
            self.target_x, self.target_y = res.x, res.y
            self._set_entry_text(self.ent_target_x, f"X:{res.x:.2f}")
            self._set_entry_text(self.ent_target_y, f"Y:{res.y:.2f}")
            self.lbl_status.configure(
                text=self._tr("status_target_saved").format(x=res.x, y=res.y), fg="#38bdf8"
            )

        self._recalculate()

    def _recalculate(self) -> None:
        if None in (self.gun_x, self.gun_y, self.target_x, self.target_y):
            return
        res = calculate_ballistics(self.gun_x, self.gun_y, self.target_x, self.target_y)
        unit = self._tr("unit_m")
        self.lbl_azimuth.configure(text=f"{res.azimuth_deg:05.1f}°")
        self.lbl_dist.configure(text=f"{int(res.distance_m)} {unit}")

        if res.range_status == "OK" and res.elevation_mil is not None:
            self.lbl_mil.configure(
                text=f"{int(res.elevation_mil)} mil", fg="#fbbf24", font=("Consolas", 15, "bold")
            )
        elif res.range_status == "TOO_CLOSE":
            self.lbl_mil.configure(
                text=f"<{int(MIN_RANGE_M)}{unit}!", fg="#f87171", font=("Consolas", 13, "bold")
            )
        else:
            self.lbl_mil.configure(
                text=f">{int(MAX_RANGE_M)}{unit}!", fg="#f87171", font=("Consolas", 13, "bold")
            )

    def _poll_loop(self) -> None:
        # Проверяем очередь результатов OCR
        try:
            while True:
                role, res = self.result_queue.get_nowait()
                self._handle_scan_result(role, res)
        except queue.Empty:
            pass

        # Считываем фронты нажатия всех клавиш через GetAsyncKeyState
        newly_pressed: list[str] = []

        esc_down = bool(ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
        esc_edge = esc_down and not self._vk_prev_down.get(VK_ESCAPE, False)
        self._vk_prev_down[VK_ESCAPE] = esc_down

        for key_name, vk in VK_MAP.items():
            is_down = bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
            was_down = self._vk_prev_down.get(vk, False)
            if is_down and not was_down:
                newly_pressed.append(key_name)
            self._vk_prev_down[vk] = is_down

        # Если сейчас активен режим назначения клавиши
        if self._rebinding_slot is not None:
            if esc_edge:
                self._finish_rebinding(None)
            elif newly_pressed:
                self._finish_rebinding(newly_pressed[0])
            self.root.after(25, self._poll_loop)
            return

        # Иначе проверяем срабатывание рабочих горячих клавиш
        if newly_pressed:
            pressed_set = set(newly_pressed)
            if str(self.config.get("hotkey_gun", "F1")).upper() in pressed_set:
                self._start_scan_async("gun")
            elif str(self.config.get("hotkey_target", "F2")).upper() in pressed_set:
                self._start_scan_async("target")
            elif str(self.config.get("hotkey_edit", "F3")).upper() in pressed_set:
                self._toggle_edit_mode()
            elif str(self.config.get("hotkey_hide", "F4")).upper() in pressed_set:
                self._toggle_visibility()

        self.root.after(25, self._poll_loop)

    def _on_drag_start(self, event) -> None:
        if self.is_edit_mode:
            self._drag_start_x = event.x_root - self.root.winfo_x()
            self._drag_start_y = event.y_root - self.root.winfo_y()

    def _on_drag_motion(self, event) -> None:
        if self.is_edit_mode:
            nx = event.x_root - self._drag_start_x
            ny = event.y_root - self._drag_start_y
            self.root.geometry(f"+{nx}+{ny}")

    def _on_drag_end(self, event) -> None:
        if self.is_edit_mode:
            self._save_config()

    def _quit(self) -> None:
        self._save_config()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    app = LiteArtilleryOverlay()
    app.run()
