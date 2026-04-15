#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mouse Auto Clicker v1.1
========================
Features:
  - Mode 1: Click at current mouse position
  - Mode 2: Click at a fixed saved position (F7 to save)
  - Mode 3: Multi-point clicking (F7 to add points, clicks in order)
  - F6  : Start / Stop clicking
  - F7  : Save coordinate (behaviour depends on mode)
  - Real-time X/Y coordinate display
  - Adjustable interval (ms), click count, mouse button
  - Infinite loop option
  - High-speed clicking via Windows SendInput API (~1000 cps @ 1 ms)

Requirements:
  pip install keyboard pillow

Author : AutoClicker Project
License: MIT
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import ctypes
import ctypes.wintypes
import keyboard

# ── Windows API constants ──────────────────────────────────────────────────────
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_ABSOLUTE   = 0x8000

user32 = ctypes.windll.user32
winmm  = ctypes.windll.winmm       # Windows multimedia timer


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _get_mouse_pos() -> tuple[int, int]:
    """Return current cursor position via Win32 API."""
    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


# Pre-define SendInput structures once (avoids repeated class creation in loop)
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   ctypes.c_ulong),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]
    _anonymous_ = ("_u",)
    _fields_    = [("type", ctypes.c_ulong), ("_u", _U)]

_INPUT_MOUSE = 0
_SW = user32.GetSystemMetrics(0)   # screen width  (cached)
_SH = user32.GetSystemMetrics(1)   # screen height (cached)


def _mouse_click_at(x: int, y: int, button: str = "left") -> None:
    """
    Perform a mouse click at (x, y) using SendInput – the fastest
    method available on Windows, bypassing pyautogui overhead.
    """
    ax = int(x * 65535 / (_SW - 1))
    ay = int(y * 65535 / (_SH - 1))

    if button == "left":
        df = MOUSEEVENTF_LEFTDOWN  | MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        uf = MOUSEEVENTF_LEFTUP    | MOUSEEVENTF_ABSOLUTE
    elif button == "right":
        df = MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        uf = MOUSEEVENTF_RIGHTUP   | MOUSEEVENTF_ABSOLUTE
    else:  # middle
        df = MOUSEEVENTF_MIDDLEDOWN | MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        uf = MOUSEEVENTF_MIDDLEUP   | MOUSEEVENTF_ABSOLUTE

    def _mk(flags: int, dx: int = 0, dy: int = 0) -> _INPUT:
        inp = _INPUT()
        inp.type       = _INPUT_MOUSE
        inp.mi.dx      = dx
        inp.mi.dy      = dy
        inp.mi.mouseData  = 0
        inp.mi.dwFlags    = flags
        inp.mi.time       = 0
        inp.mi.dwExtraInfo = None
        return inp

    inputs = (_INPUT * 2)(_mk(df, ax, ay), _mk(uf, ax, ay))
    user32.SendInput(2, inputs, ctypes.sizeof(_INPUT))


def _high_res_sleep(ms: float) -> None:
    """
    High-resolution sleep.
    - ms < 2  : busy-wait with perf_counter (sub-ms accuracy)
    - ms >= 2 : time.sleep() with 1-ms timer resolution (timeBeginPeriod)
    """
    if ms <= 0:
        return
    if ms < 2:
        deadline = time.perf_counter() + ms / 1000.0
        while time.perf_counter() < deadline:
            pass
    else:
        time.sleep(ms / 1000.0)


# ── Main Application ───────────────────────────────────────────────────────────

class AutoClickerApp:

    # Interval presets (ms) shown as quick buttons
    PRESETS = [("1ms", 1), ("5ms", 5), ("10ms", 10),
               ("50ms", 50), ("100ms", 100), ("500ms", 500)]

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Mouse Auto Clicker v1.1")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)   # always on top

        # ── State ──
        self.running      = False
        self.click_thread: threading.Thread | None = None

        # Real-time cursor coords
        self.mouse_x = tk.IntVar(value=0)
        self.mouse_y = tk.IntVar(value=0)

        # Mode: 1=current pos  2=fixed pos  3=multi-point
        self.mode = tk.IntVar(value=1)

        # Fixed coordinate (mode 2)
        self.fixed_x = tk.IntVar(value=0)
        self.fixed_y = tk.IntVar(value=0)

        # Multi-point list (mode 3)
        self.multi_points: list[tuple[int, int]] = []

        # Click parameters
        self.click_interval_ms = tk.IntVar(value=50)
        self.click_count       = tk.IntVar(value=100)
        self.click_button      = tk.StringVar(value="left")
        self.infinite          = tk.BooleanVar(value=False)

        # Stats
        self.total_clicks = tk.IntVar(value=0)
        self.status_text  = tk.StringVar(value="Ready")

        self._build_ui()
        self._bind_hotkeys()
        self._start_mouse_tracker()

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        PAD = {"padx": 8, "pady": 4}

        # Title bar
        title_bar = tk.Frame(self.root, bg="#2c3e50", height=40)
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="🖱️  Mouse Auto Clicker  v1.1",
                 font=("Segoe UI", 13, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=12, pady=6)

        main = tk.Frame(self.root, padx=10, pady=6)
        main.pack(fill="both", expand=True)

        # ── Real-time cursor coords ──
        coord_frame = ttk.LabelFrame(main, text=" 🖱️ Live Cursor Position ", padding=6)
        coord_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **PAD)

        tk.Label(coord_frame, text="X:").grid(row=0, column=0, sticky="w")
        tk.Label(coord_frame, textvariable=self.mouse_x, width=6,
                 font=("Consolas", 12, "bold"), fg="#e74c3c").grid(row=0, column=1, sticky="w")
        tk.Label(coord_frame, text="     Y:").grid(row=0, column=2, sticky="w")
        tk.Label(coord_frame, textvariable=self.mouse_y, width=6,
                 font=("Consolas", 12, "bold"), fg="#2980b9").grid(row=0, column=3, sticky="w")

        # ── Mode selection ──
        mode_frame = ttk.LabelFrame(main, text=" ⚙️ Click Mode ", padding=6)
        mode_frame.grid(row=1, column=0, columnspan=2, sticky="ew", **PAD)
        for text, val in [
            ("Mode 1 – Current position", 1),
            ("Mode 2 – Fixed position",   2),
            ("Mode 3 – Multi-point",      3),
        ]:
            ttk.Radiobutton(mode_frame, text=text, variable=self.mode,
                            value=val, command=self._on_mode_change).pack(anchor="w")

        # ── Fixed coord panel (mode 2) ──
        self.fixed_frame = ttk.LabelFrame(
            main, text=" 📍 Fixed Coordinate (Mode 2) ", padding=6)
        self.fixed_frame.grid(row=2, column=0, columnspan=2, sticky="ew", **PAD)
        tk.Label(self.fixed_frame, text="X:").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.fixed_frame, textvariable=self.fixed_x,
                  width=8).grid(row=0, column=1, padx=4)
        tk.Label(self.fixed_frame, text="Y:").grid(row=0, column=2, sticky="w")
        ttk.Entry(self.fixed_frame, textvariable=self.fixed_y,
                  width=8).grid(row=0, column=3, padx=4)
        ttk.Button(self.fixed_frame, text="Save Current (F7)",
                   command=self._save_fixed_coord).grid(row=0, column=4, padx=6)

        # ── Multi-point panel (mode 3) ──
        self.multi_frame = ttk.LabelFrame(
            main, text=" 📌 Multi-point List (Mode 3) ", padding=6)
        self.multi_frame.grid(row=3, column=0, columnspan=2, sticky="ew", **PAD)

        list_wrap = tk.Frame(self.multi_frame)
        list_wrap.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(list_wrap, orient="vertical")
        self.points_listbox = tk.Listbox(
            list_wrap, height=5, width=36,
            yscrollcommand=sb.set, font=("Consolas", 10))
        sb.config(command=self.points_listbox.yview)
        self.points_listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        btn_row = tk.Frame(self.multi_frame)
        btn_row.pack(fill="x", pady=4)
        for txt, cmd in [
            ("Add (F7)",    self._add_multi_point),
            ("Delete",      self._delete_selected_point),
            ("Clear All",   self._clear_all_points),
            ("↑ Up",        self._move_point_up),
            ("↓ Down",      self._move_point_down),
        ]:
            ttk.Button(btn_row, text=txt, command=cmd).pack(side="left", padx=3)

        # ── Click parameters ──
        param_frame = ttk.LabelFrame(main, text=" 🔧 Click Parameters ", padding=6)
        param_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **PAD)

        # Interval (ms)
        tk.Label(param_frame, text="Interval (ms):").grid(row=0, column=0, sticky="w")
        iv_spin = ttk.Spinbox(
            param_frame, from_=1, to=60000, increment=10,
            textvariable=self.click_interval_ms, width=7,
            command=self._update_freq_label)
        iv_spin.grid(row=0, column=1, padx=4, sticky="w")
        iv_spin.bind("<KeyRelease>", lambda _e: self._update_freq_label())

        self.freq_label = tk.Label(
            param_frame, text="≈ 20.0 cps", fg="#27ae60",
            font=("Segoe UI", 9, "bold"))
        self.freq_label.grid(row=0, column=2, padx=8, sticky="w")

        # Preset buttons
        preset_row = tk.Frame(param_frame)
        preset_row.grid(row=0, column=3, padx=6, sticky="w")
        for label, ms in self.PRESETS:
            ttk.Button(preset_row, text=label, width=5,
                       command=lambda v=ms: self._set_interval(v)).pack(side="left", padx=1)

        # Count / loops
        self.count_label = tk.Label(param_frame, text="Click count:")
        self.count_label.grid(row=1, column=0, sticky="w", pady=4)
        ttk.Spinbox(param_frame, from_=1, to=9_999_999,
                    textvariable=self.click_count,
                    width=7).grid(row=1, column=1, padx=4, sticky="w")
        ttk.Checkbutton(param_frame, text="Infinite loop",
                        variable=self.infinite).grid(row=1, column=2, padx=8)

        # Mouse button
        tk.Label(param_frame, text="Mouse button:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(param_frame, textvariable=self.click_button,
                     values=["left", "right", "middle"],
                     width=8, state="readonly").grid(row=2, column=1, padx=4, sticky="w")

        # ── Control buttons ──
        ctrl = tk.Frame(main)
        ctrl.grid(row=5, column=0, columnspan=2, pady=8)
        self.start_btn = ttk.Button(
            ctrl, text="▶  Start  (F6)",
            command=self.toggle_clicking, width=20)
        self.start_btn.pack(side="left", padx=6)
        ttk.Button(ctrl, text="✖  Exit",
                   command=self._on_exit, width=10).pack(side="left", padx=6)

        # ── Status bar ──
        sbar = tk.Frame(self.root, bg="#ecf0f1", height=28)
        sbar.pack(fill="x", side="bottom")
        tk.Label(sbar, text="Status:", bg="#ecf0f1").pack(side="left", padx=6)
        self.status_label = tk.Label(
            sbar, textvariable=self.status_text,
            fg="#27ae60", bg="#ecf0f1", font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side="left")
        tk.Label(sbar, text=" | Clicks:", bg="#ecf0f1").pack(side="left", padx=(16, 0))
        tk.Label(sbar, textvariable=self.total_clicks,
                 fg="#e74c3c", bg="#ecf0f1",
                 font=("Consolas", 9, "bold")).pack(side="left")
        tk.Label(sbar, text="  F6=Start/Stop  F7=Save Coord",
                 bg="#ecf0f1", fg="#7f8c8d").pack(side="right", padx=8)

        self._on_mode_change()
        self._update_freq_label()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_interval(self, ms: int) -> None:
        self.click_interval_ms.set(ms)
        self._update_freq_label()

    def _update_freq_label(self, *_) -> None:
        try:
            ms = int(self.click_interval_ms.get())
            if ms > 0:
                self.freq_label.config(text=f"≈ {1000 / ms:.1f} cps")
        except (ValueError, tk.TclError):
            pass

    def _on_mode_change(self) -> None:
        m = self.mode.get()
        (self.fixed_frame.grid if m == 2 else self.fixed_frame.grid_remove)()
        (self.multi_frame.grid if m == 3 else self.multi_frame.grid_remove)()
        self.count_label.config(text="Loop count:" if m == 3 else "Click count:")

    def _set_status(self, text: str, color: str = "#27ae60") -> None:
        self.status_text.set(text)
        self.status_label.config(fg=color)

    # Coordinate management ────────────────────────────────────────────────────

    def _save_fixed_coord(self) -> None:
        x, y = _get_mouse_pos()
        self.fixed_x.set(x)
        self.fixed_y.set(y)
        self._set_status(f"Fixed coord saved: ({x}, {y})", "#8e44ad")

    def _add_multi_point(self) -> None:
        x, y = _get_mouse_pos()
        self.multi_points.append((x, y))
        n = len(self.multi_points)
        self.points_listbox.insert(tk.END, f"  #{n:02d}   X: {x:5d}   Y: {y:5d}")
        self._set_status(f"Point #{n} added: ({x}, {y})", "#8e44ad")

    def _delete_selected_point(self) -> None:
        sel = self.points_listbox.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a point to delete.")
            return
        idx = sel[0]
        self.points_listbox.delete(idx)
        del self.multi_points[idx]
        self._refresh_listbox()

    def _clear_all_points(self) -> None:
        if self.multi_points and messagebox.askyesno("Confirm", "Clear all saved points?"):
            self.multi_points.clear()
            self.points_listbox.delete(0, tk.END)

    def _move_point_up(self) -> None:
        sel = self.points_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.multi_points[i - 1], self.multi_points[i] = \
            self.multi_points[i], self.multi_points[i - 1]
        self._refresh_listbox()
        self.points_listbox.selection_set(i - 1)

    def _move_point_down(self) -> None:
        sel = self.points_listbox.curselection()
        if not sel or sel[0] >= len(self.multi_points) - 1:
            return
        i = sel[0]
        self.multi_points[i], self.multi_points[i + 1] = \
            self.multi_points[i + 1], self.multi_points[i]
        self._refresh_listbox()
        self.points_listbox.selection_set(i + 1)

    def _refresh_listbox(self) -> None:
        self.points_listbox.delete(0, tk.END)
        for i, (x, y) in enumerate(self.multi_points):
            self.points_listbox.insert(tk.END, f"  #{i + 1:02d}   X: {x:5d}   Y: {y:5d}")

    # ── Hotkeys ────────────────────────────────────────────────────────────────

    def _bind_hotkeys(self) -> None:
        keyboard.add_hotkey("f6", lambda: self.root.after(0, self.toggle_clicking),
                            suppress=False)
        keyboard.add_hotkey("f7", self._hotkey_f7, suppress=False)

    def _hotkey_f7(self) -> None:
        m = self.mode.get()
        if m == 2:
            self.root.after(0, self._save_fixed_coord)
        elif m == 3:
            self.root.after(0, self._add_multi_point)
        else:
            self.root.after(0, lambda: self._set_status(
                "F7 is not used in Mode 1.", "#e67e22"))

    # ── Mouse tracker thread ───────────────────────────────────────────────────

    def _start_mouse_tracker(self) -> None:
        def _track():
            while True:
                try:
                    x, y = _get_mouse_pos()
                    self.mouse_x.set(x)
                    self.mouse_y.set(y)
                except Exception:
                    pass
                time.sleep(0.02)          # ~50 fps refresh
        threading.Thread(target=_track, daemon=True).start()

    # ── Click control ──────────────────────────────────────────────────────────

    def toggle_clicking(self) -> None:
        if self.running:
            self._stop_clicking()
        else:
            self._start_clicking()

    def _start_clicking(self) -> None:
        m = self.mode.get()
        if m == 3 and not self.multi_points:
            messagebox.showwarning("Warning",
                                   "Please add at least one point with F7 first.")
            return
        self.running = True
        self.total_clicks.set(0)
        self._set_status("Clicking…", "#e74c3c")
        self.start_btn.config(text="⏹  Stop  (F6)")
        self.click_thread = threading.Thread(
            target=self._click_loop, daemon=True)
        self.click_thread.start()

    def _stop_clicking(self) -> None:
        self.running = False
        self._set_status(
            f"Stopped – {self.total_clicks.get()} clicks total.", "#27ae60")
        self.start_btn.config(text="▶  Start  (F6)")

    def _click_loop(self) -> None:
        m = self.mode.get()
        try:
            ms = max(1, int(self.click_interval_ms.get()))
        except ValueError:
            ms = 50

        btn      = self.click_button.get()
        infinite = self.infinite.get()
        try:
            count = int(self.click_count.get())
        except ValueError:
            count = 100

        winmm.timeBeginPeriod(1)
        try:
            if m == 1:
                self._loop_current(ms, btn, count, infinite)
            elif m == 2:
                self._loop_fixed(ms, btn, count, infinite)
            else:
                self._loop_multi(ms, btn, count, infinite)
        finally:
            winmm.timeEndPeriod(1)

        if self.running:
            self.root.after(0, self._stop_clicking)

    def _update_count(self, n: int) -> None:
        """Thread-safe counter update (batched every 20 clicks)."""
        if n % 20 == 0:
            self.root.after(0, lambda v=n: self.total_clicks.set(v))

    def _loop_current(self, ms, btn, count, infinite) -> None:
        clicked = 0
        while self.running and (infinite or clicked < count):
            x, y = _get_mouse_pos()
            _mouse_click_at(x, y, btn)
            clicked += 1
            self._update_count(clicked)
            _high_res_sleep(ms)
        self.root.after(0, lambda v=clicked: self.total_clicks.set(v))

    def _loop_fixed(self, ms, btn, count, infinite) -> None:
        fx, fy  = self.fixed_x.get(), self.fixed_y.get()
        clicked = 0
        while self.running and (infinite or clicked < count):
            _mouse_click_at(fx, fy, btn)
            clicked += 1
            self._update_count(clicked)
            _high_res_sleep(ms)
        self.root.after(0, lambda v=clicked: self.total_clicks.set(v))

    def _loop_multi(self, ms, btn, count, infinite) -> None:
        points  = list(self.multi_points)
        loops   = 0
        clicked = 0
        while self.running and (infinite or loops < count):
            for x, y in points:
                if not self.running:
                    break
                _mouse_click_at(x, y, btn)
                clicked += 1
                self._update_count(clicked)
                _high_res_sleep(ms)
            loops += 1
        self.root.after(0, lambda v=clicked: self.total_clicks.set(v))

    # ── Exit ───────────────────────────────────────────────────────────────────

    def _on_exit(self) -> None:
        self.running = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.root.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    winmm.timeBeginPeriod(1)      # raise timer resolution globally

    root = tk.Tk()
    root.configure(bg="#f0f0f0")

    # Dynamic window icon (no external file needed)
    try:
        from PIL import Image, ImageDraw, ImageTk
        img  = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 30, 30], fill=(52, 152, 219, 255),
                     outline=(41, 128, 185, 255), width=2)
        draw.ellipse([12, 2, 20, 14], fill=(255, 255, 255, 200))
        root.iconphoto(True, ImageTk.PhotoImage(img))
    except Exception:
        pass

    app = AutoClickerApp(root)
    root.protocol("WM_DELETE_WINDOW", app._on_exit)
    root.mainloop()

    winmm.timeEndPeriod(1)


if __name__ == "__main__":
    main()
