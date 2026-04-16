# 🖱️ Mouse Auto Clicker

A lightweight, high-speed Windows mouse auto-clicker with a clean GUI.  
Built with Python + Tkinter, using the native **Windows `SendInput` API** for maximum click throughput (~1000 clicks/sec at 1 ms interval).

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Mode 1** – Current position | F6 clicks wherever your cursor is at the moment |
| **Mode 2** – Fixed position | Press F7 to save a coordinate; F6 always clicks there |
| **Mode 3** – Multi-point | Add multiple points with F7; F6 cycles through them in order |
| Live cursor display | Real-time X / Y coordinates shown in the window |
| Adjustable interval | 1 ms – 60 000 ms, with one-click presets (1 / 5 / 10 / 50 / 100 / 500 ms) |
| CPS readout | Automatically calculates clicks-per-second from the interval |
| Click count | Modes 1 & 2: total clicks. Mode 3: loop count |
| Infinite loop | Checkbox to ignore the count and click until F6 is pressed again |
| Mouse button | Left / Right / Middle |
| Always-on-top | Window stays visible over other apps |
| High-res timer | Uses `winmm.timeBeginPeriod(1)` + busy-wait for sub-ms accuracy |

### Hotkeys

| Key | Action |
|---|---|
| **F6** | Start / Stop clicking |
| **F7** | Mode 2 → save fixed coord · Mode 3 → add a point |

---

## 📋 Requirements

- **Windows 10 / 11** (uses Win32 APIs)
- **Python 3.10+**

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/mouse-auto-clicker.git
cd mouse-auto-clicker

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run (may need to run as Administrator for global hotkeys)
python auto_clicker.py
```

> **Tip – Administrator mode:**  
> The `keyboard` library requires elevated privileges on some systems to capture global hotkeys.  
> Right-click your terminal / shortcut and choose **"Run as administrator"** if F6 / F7 don't respond.

---

## 🖥️ Screenshot

<img width="972" height="683" alt="image" src="https://github.com/user-attachments/assets/beb101c9-d02e-4515-92cb-f61295f0246c" />

---

## 📁 Project Structure

```
mouse-auto-clicker/
├── auto_clicker.py   # Main application (single file, no extra assets)
├── requirements.txt  # Python dependencies
├── .gitignore
└── README.md
```

---

## 🔧 How It Works

1. **SendInput API** – Clicks are injected directly into the Windows input stream via `user32.SendInput()`, bypassing any intermediate library overhead.
2. **High-resolution timer** – `winmm.timeBeginPeriod(1)` raises the system timer granularity to 1 ms. For intervals below 2 ms a busy-wait loop using `time.perf_counter()` provides sub-millisecond accuracy.
3. **Batched UI updates** – The click counter is refreshed every 20 clicks to keep the GUI thread unblocked at high rates.
4. **Daemon threads** – The clicking loop and cursor tracker run on daemon threads and exit cleanly when the window is closed.

---

## 📝 License

MIT © AutoClicker Project
