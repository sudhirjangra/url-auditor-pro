# ⚡ URL Auditor Pro

**Open-source URL health checker with Selenium-based dual-browser verification.**

[![Release](https://img.shields.io/github/v/release/sudhirjangra/url-auditor-pro)](https://github.com/sudhirjangra/url-auditor-pro/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

---

## Features

- Load URLs from **Excel (.xlsx, .xls) or CSV** files via drag-and-drop or file picker
- **Dual-browser verification** — Chrome (primary) + optional Firefox override
- Detects inactive pages via:
  - Title keyword matching (configurable)
  - HTTP error codes in page titles (4xx / 5xx)
  - DNS / connection errors
- Identifies **WAF / Cloudflare** challenges
- **Status change tracking** — compare against a previous status column
- Auto-saves detection rules to `url_auditor_config.xml`
- Exports detailed **Excel reports** with timestamps
- Four built-in themes: Dark Pro, Light Clean, Midnight Blue, Solarized

---

## Download

Download the latest **Windows `.exe`** from the [Releases](https://github.com/sudhirjangra/url-auditor-pro/releases) page — no Python installation required.

---

## Requirements (run from source)

- Python 3.10+
- Google Chrome + matching [ChromeDriver](https://chromedriver.chromium.org/downloads)
- *(Optional)* Firefox + matching [GeckoDriver](https://github.com/mozilla/geckodriver/releases)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run

```bash
python url_auditor.py
```

Place `chromedriver.exe` (and optionally `geckodriver.exe`) in the **same folder** as the script or the `.exe`.

---

## Usage

1. **Drop or open** an Excel/CSV file
2. **Select the URL column** from the dropdown
3. *(Optional)* Select a previous status column for change tracking
4. Configure **Browser Options** and **Skip Domains**
5. Click **▶ Start Audit**
6. When complete, click **⬇ Export Excel Report**

---

## Detection Rules

Rules are configurable in the **Rules** tab and auto-saved to `url_auditor_config.xml`:

| Rule | Description |
|------|-------------|
| **Inactive Title Keywords** | Page marked Inactive if title contains any keyword |
| **WAF / Security Check Keywords** | Page marked Active (WAF detected) if HTML contains any keyword |
| **Skip Domains** | Domains bypassed entirely (sidebar) |

---

## Building the `.exe` yourself

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=logo.ico --name="URL Auditor Pro" url_auditor.py
```

The binary will be in `dist/`. Place your WebDriver files alongside it.

---

## License

MIT © [Sudhir Jangra](https://github.com/sudhirjangra)
