# -*- coding: utf-8 -*-
"""
URL Auditor Pro
Open-source URL health checker with Selenium-based dual-browser verification.
Developed by Sudhir Jangra
"""

import sys
import os
import re
import time
import logging
import webbrowser
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import WebDriverException, TimeoutException

# ── Logging setup ──────────────────────────────────────────────────────────────

def _get_base_dir() -> str:
    """Directory that contains the frozen EXE or the running script."""
    return (os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)))


def _get_log_base() -> str:
    return _get_base_dir()


def _get_icon_path() -> str:
    """Locate logo.ico: check PyInstaller _MEIPASS bundle first, then base dir."""
    if getattr(sys, "frozen", False):
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            p = os.path.join(mei, "logo.ico")
            if os.path.exists(p):
                return p
    p = os.path.join(_get_base_dir(), "logo.ico")
    return p if os.path.exists(p) else ""


def _app_icon():
    path = _get_icon_path()
    return QIcon(path) if path else QIcon()


def _init_logger() -> logging.Logger:
    base = _get_log_base()
    ts   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(base, f"url_auditor_{ts}.log")

    logger = logging.getLogger("url_auditor")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # suppress urllib3 / selenium noise from root logger

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)
    return logger


log = _init_logger()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QTextEdit, QFileDialog,
    QMessageBox, QProgressBar, QTabWidget, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QGroupBox, QStatusBar, QAbstractItemView
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QTimer, QUrl, QMimeData
)
from PyQt6.QtGui import (
    QFont, QColor, QDesktopServices, QAction, QDragEnterEvent, QDropEvent,
    QIcon, QPixmap
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Constants ──────────────────────────────────────────────────────────────────

APP_NAME    = "URL Auditor Pro"
APP_VERSION = "1.1.1"
DEVELOPER   = "Sudhir Jangra"

SOFT_TIMEOUT = 20
HARD_TIMEOUT = 60

CONFIG_FILENAME = "url_auditor_config.xml"

_DEFAULT_BAD_TITLES = [
    "404", "page not found", "access to the website is blocked",
    "privacy error", "Attention Required! | Cloudflare",
    "service unavailable", "500", "502", "internal server error",
    "bad gateway", "temporarily unavailable", "site can't be reached",
    "domain expired", "under maintenance", "403 forbidden",
    "access denied", "iis windows server", "default page",
    "just another wordpress site",
]

_DEFAULT_CF_SIGNS = [
    "checking your browser", "please stand by", "verify you are human",
    "cf-browser-verification", "just a moment...",
    "enable javascript and cookies to continue",
    "incapsula incident id",
]

_DEFAULT_SKIP_DOMAINS: list[str] = []

# Regex: bare HTTP status codes or codes in common title patterns
_HTTP_ERROR_RE = re.compile(
    r'\b(4[0-9]{2}|5[0-9]{2})\b'
    r'|(?:error|http|status)[^\w]?\s*\d{3}'
    r'|\d{3}\s+(?:error|not found|forbidden|unauthorized|bad request|'
    r'bad gateway|service unavailable|internal server|gateway timeout|'
    r'too many requests|request timeout|gone|conflict|method not allowed)',
    re.IGNORECASE
)


# ── Themes ─────────────────────────────────────────────────────────────────────

THEMES = {
    "Dark Pro": {
        "bg_primary":    "#1a1d23",
        "bg_secondary":  "#21262d",
        "bg_card":       "#2d333b",
        "bg_hover":      "#363c45",
        "accent":        "#58a6ff",
        "accent_hover":  "#79b8ff",
        "success":       "#3fb950",
        "danger":        "#f85149",
        "warning":       "#d29922",
        "purple":        "#bc8cff",
        "text_primary":  "#e6edf3",
        "text_secondary":"#8b949e",
        "text_muted":    "#484f58",
        "border":        "#30363d",
        "border_focus":  "#58a6ff",
        "row_active":    "#1f3a2a",
        "row_inactive":  "#3a1f1f",
        "row_skip":      "#2a1f3a",
        "row_alt":       "#252b33",
        "scrollbar":     "#484f58",
    },
    "Light Clean": {
        "bg_primary":    "#f6f8fa",
        "bg_secondary":  "#ffffff",
        "bg_card":       "#ffffff",
        "bg_hover":      "#f0f3f6",
        "accent":        "#0969da",
        "accent_hover":  "#0550ae",
        "success":       "#1a7f37",
        "danger":        "#cf222e",
        "warning":       "#9a6700",
        "purple":        "#8250df",
        "text_primary":  "#1f2328",
        "text_secondary":"#57606a",
        "text_muted":    "#8c959f",
        "border":        "#d0d7de",
        "border_focus":  "#0969da",
        "row_active":    "#dafbe1",
        "row_inactive":  "#ffebe9",
        "row_skip":      "#fbefff",
        "row_alt":       "#f6f8fa",
        "scrollbar":     "#d0d7de",
    },
    "Midnight Blue": {
        "bg_primary":    "#0d1117",
        "bg_secondary":  "#161b22",
        "bg_card":       "#1c2128",
        "bg_hover":      "#262c36",
        "accent":        "#388bfd",
        "accent_hover":  "#58a6ff",
        "success":       "#2ea043",
        "danger":        "#da3633",
        "warning":       "#bb8009",
        "purple":        "#a371f7",
        "text_primary":  "#cdd9e5",
        "text_secondary":"#768390",
        "text_muted":    "#444c56",
        "border":        "#373e47",
        "border_focus":  "#388bfd",
        "row_active":    "#122318",
        "row_inactive":  "#2c1115",
        "row_skip":      "#1e1128",
        "row_alt":       "#1a1f26",
        "scrollbar":     "#444c56",
    },
    "Solarized": {
        "bg_primary":    "#002b36",
        "bg_secondary":  "#073642",
        "bg_card":       "#073642",
        "bg_hover":      "#0d4557",
        "accent":        "#268bd2",
        "accent_hover":  "#2aa198",
        "success":       "#859900",
        "danger":        "#dc322f",
        "warning":       "#b58900",
        "purple":        "#6c71c4",
        "text_primary":  "#839496",
        "text_secondary":"#657b83",
        "text_muted":    "#586e75",
        "border":        "#0d4557",
        "border_focus":  "#268bd2",
        "row_active":    "#0f2d1a",
        "row_inactive":  "#2d110f",
        "row_skip":      "#1a0f2d",
        "row_alt":       "#063545",
        "scrollbar":     "#586e75",
    },
}

CURRENT_THEME = "Dark Pro"


def T() -> dict:
    return THEMES[CURRENT_THEME]


# ── Stylesheet builder ────────────────────────────────────────────────────────

def build_stylesheet(theme: dict) -> str:
    t = theme
    return f"""
    QMainWindow, QWidget {{
        background-color: {t['bg_primary']};
        color: {t['text_primary']};
        font-family: 'Segoe UI', 'SF Pro Text', system-ui, sans-serif;
        font-size: 13px;
    }}
    QTabWidget::pane {{
        border: 1px solid {t['border']};
        background-color: {t['bg_secondary']};
        border-radius: 6px;
    }}
    QTabBar::tab {{
        background: {t['bg_card']};
        color: {t['text_secondary']};
        padding: 8px 20px;
        border: 1px solid {t['border']};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {t['bg_secondary']};
        color: {t['text_primary']};
        border-bottom: 2px solid {t['accent']};
    }}
    QTabBar::tab:hover:!selected {{
        background: {t['bg_hover']};
        color: {t['text_primary']};
    }}
    QPushButton {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        padding: 7px 16px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {t['bg_hover']};
        border-color: {t['border_focus']};
    }}
    QPushButton:pressed {{
        background-color: {t['border']};
    }}
    QPushButton:disabled {{
        color: {t['text_muted']};
        border-color: {t['border']};
    }}
    QPushButton#btn_start {{
        background-color: {t['success']};
        color: #ffffff;
        border: none;
        font-weight: 600;
    }}
    QPushButton#btn_start:hover {{
        background-color: {t['accent_hover']};
    }}
    QPushButton#btn_start:disabled {{
        background-color: {t['text_muted']};
        color: #cccccc;
    }}
    QPushButton#btn_pause {{
        background-color: {t['warning']};
        color: #ffffff;
        border: none;
        font-weight: 600;
    }}
    QPushButton#btn_export {{
        background-color: {t['accent']};
        color: #ffffff;
        border: none;
        font-weight: 600;
    }}
    QPushButton#btn_export:disabled {{
        background-color: {t['text_muted']};
        color: #cccccc;
    }}
    QComboBox {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        padding: 6px 10px;
        border-radius: 5px;
        selection-background-color: {t['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox:focus {{
        border-color: {t['border_focus']};
    }}
    QComboBox QAbstractItemView {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        selection-background-color: {t['accent']};
    }}
    QTextEdit {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 5px;
        padding: 6px 10px;
        selection-background-color: {t['accent']};
    }}
    QTextEdit:focus {{
        border-color: {t['border_focus']};
    }}
    QCheckBox {{
        color: {t['text_primary']};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid {t['border']};
        border-radius: 3px;
        background-color: {t['bg_card']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {t['accent']};
        border-color: {t['accent']};
    }}
    QProgressBar {{
        background-color: {t['bg_card']};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {t['accent']}, stop:1 {t['success']});
        border-radius: 4px;
    }}
    QTableWidget {{
        background-color: {t['bg_secondary']};
        gridline-color: {t['border']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        selection-background-color: {t['accent']};
        selection-color: #ffffff;
        alternate-background-color: {t['row_alt']};
    }}
    QTableWidget::item {{
        padding: 6px 8px;
        border: none;
    }}
    QTableWidget::item:hover {{
        background-color: {t['bg_hover']};
    }}
    QHeaderView::section {{
        background-color: {t['bg_card']};
        color: {t['text_secondary']};
        border: none;
        border-bottom: 2px solid {t['border']};
        border-right: 1px solid {t['border']};
        padding: 8px 10px;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    QScrollBar:vertical {{
        background: {t['bg_card']};
        width: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['scrollbar']};
        border-radius: 5px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t['text_secondary']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {t['bg_card']};
        height: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t['scrollbar']};
        border-radius: 5px;
        min-width: 20px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {t['text_secondary']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QStatusBar {{
        background-color: {t['bg_secondary']};
        color: {t['text_secondary']};
        border-top: 1px solid {t['border']};
        font-size: 12px;
    }}
    QGroupBox {{
        border: 1px solid {t['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 8px;
        font-weight: 600;
        color: {t['text_primary']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {t['accent']};
        font-size: 12px;
    }}
    QLabel#heading {{
        font-size: 15px;
        font-weight: 700;
        color: {t['text_primary']};
    }}
    QLabel#subtext {{
        font-size: 11px;
        color: {t['text_secondary']};
    }}
    QLabel#dev_credit {{
        font-size: 11px;
        color: {t['accent']};
    }}
    QFrame#card {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 10px;
    }}
    QFrame#separator {{
        background-color: {t['border']};
        max-height: 1px;
        min-height: 1px;
    }}
    QFrame#drop_zone {{
        background-color: {t['bg_card']};
        border: 2px dashed {t['border_focus']};
        border-radius: 8px;
    }}
    QFrame#drop_zone_hover {{
        background-color: {t['bg_hover']};
        border: 2px dashed {t['success']};
        border-radius: 8px;
    }}
    """


# ── Config helpers ─────────────────────────────────────────────────────────────

def get_config_path() -> str:
    return os.path.join(_get_base_dir(), CONFIG_FILENAME)


def load_config() -> tuple[list, list, list, str, str]:
    """Returns (skip_domains, bad_titles, cf_signs, url_column, status_column)."""
    path = get_config_path()
    if not os.path.exists(path):
        save_config(_DEFAULT_SKIP_DOMAINS, _DEFAULT_BAD_TITLES, _DEFAULT_CF_SIGNS, "", "")
        return (list(_DEFAULT_SKIP_DOMAINS), list(_DEFAULT_BAD_TITLES),
                list(_DEFAULT_CF_SIGNS), "", "")
    try:
        root = ET.parse(path).getroot()

        def read_list(tag, child):
            node = root.find(tag)
            if node is None:
                return []
            return [c.text.strip() for c in node.findall(child) if c.text and c.text.strip()]

        def read_text(tag) -> str:
            node = root.find(tag)
            return (node.text or "").strip() if node is not None else ""

        skip = read_list("skip_domains", "domain") or list(_DEFAULT_SKIP_DOMAINS)
        bad  = read_list("bad_titles",   "title")  or list(_DEFAULT_BAD_TITLES)
        cf   = read_list("cf_signs",     "sign")   or list(_DEFAULT_CF_SIGNS)
        url_col    = read_text("url_column")
        status_col = read_text("status_column")
        return skip, bad, cf, url_col, status_col
    except Exception as e:
        print(f"Config load error: {e}")
        return (list(_DEFAULT_SKIP_DOMAINS), list(_DEFAULT_BAD_TITLES),
                list(_DEFAULT_CF_SIGNS), "", "")


def save_config(skip_domains: list, bad_titles: list, cf_signs: list,
                url_col: str = "", status_col: str = ""):
    root = ET.Element("url_auditor_config")

    def write_list(parent_tag, child_tag, items):
        parent = ET.SubElement(root, parent_tag)
        for item in items:
            ET.SubElement(parent, child_tag).text = item

    write_list("skip_domains", "domain", skip_domains)
    write_list("bad_titles",   "title",  bad_titles)
    write_list("cf_signs",     "sign",   cf_signs)

    if url_col:
        ET.SubElement(root, "url_column").text = url_col
    if status_col:
        ET.SubElement(root, "status_column").text = status_col

    ET.indent(root, space="    ")
    try:
        ET.ElementTree(root).write(get_config_path(), encoding="utf-8", xml_declaration=True)
    except Exception as e:
        print(f"Config save error: {e}")


# ── URL helpers ────────────────────────────────────────────────────────────────

def sanitize_input_url(value) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip()
    return "" if not s or s.lower() == "nan" else s


def normalize_url_key(raw_url: str) -> str:
    url = sanitize_input_url(raw_url)
    if not url:
        return ""
    if not urlparse(url).scheme:
        url = f"https://{url}"
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = (parsed.path or "").strip().rstrip("/").lower()
    return f"{host}{path}"


def full_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return raw
    if not urlparse(raw).scheme:
        return f"https://{raw}"
    return raw


def check_skip_domain(url: str, skip_list: list) -> bool:
    if not isinstance(url, str):
        return False
    return any(d.lower() in url.lower() for d in skip_list if d.strip())


def is_bad_title(title: str, bad_list: list) -> tuple[bool, str]:
    if not title:
        return False, ""
    tl = title.lower()
    for bad in bad_list:
        if bad.lower() in tl:
            return True, bad
    return False, ""


def is_http_error_title(title: str) -> tuple[bool, str]:
    """Detect HTTP error codes (4xx/5xx) in page titles."""
    if not title:
        return False, ""
    m = _HTTP_ERROR_RE.search(title)
    if m:
        return True, f"HTTP error in title: '{m.group()}'"
    return False, ""


# ── Selenium helpers ───────────────────────────────────────────────────────────

def get_driver_base() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _chrome_opts(headless: bool) -> ChromeOptions:
    opts = ChromeOptions()
    opts.page_load_strategy = "eager"
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--log-level=3")
    return opts


def setup_chrome(headless: bool = True):
    opts = _chrome_opts(headless)
    local_name = "chromedriver.exe" if os.name == "nt" else "chromedriver"
    local_path = os.path.join(get_driver_base(), local_name)

    # 1) Try local chromedriver next to the exe/script
    if os.path.exists(local_path):
        try:
            svc = ChromeService(executable_path=local_path)
            driver = webdriver.Chrome(service=svc, options=opts)
            log.info("Chrome started via local driver: %s", local_path)
            return driver
        except Exception as e:
            log.warning("Local chromedriver failed (%s): %s", local_path, e)

    # 2) Try Selenium Manager (built into Selenium 4.6+, auto-downloads matching driver)
    try:
        driver = webdriver.Chrome(options=opts)
        log.info("Chrome started via Selenium Manager (auto-matched driver)")
        return driver
    except Exception as e:
        log.warning("Selenium Manager Chrome failed: %s", e)

    # 3) Try webdriver-manager as last resort
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        svc = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=svc, options=opts)
        log.info("Chrome started via webdriver-manager")
        return driver
    except Exception as e:
        log.error("All Chrome driver strategies failed: %s", e)
        return None


def setup_firefox(headless: bool = True):
    opts = FirefoxOptions()
    opts.page_load_strategy = "eager"
    if headless:
        opts.add_argument("--headless")
    local = "geckodriver.exe" if os.name == "nt" else "geckodriver"
    dp = os.path.join(get_driver_base(), local)
    if not os.path.exists(dp):
        log.info("geckodriver not found at %s, skipping Firefox", dp)
        return None
    try:
        svc = FirefoxService(executable_path=dp)
        driver = webdriver.Firefox(service=svc, options=opts)
        log.info("Firefox started via local driver: %s", dp)
        return driver
    except Exception as e:
        log.warning("Firefox init error: %s", e)
        return None


# Browser-generated error page markers (never real content)
_BROWSER_ERROR_URLS = (
    "about:neterror", "chrome-error://", "data:text/html",
)
_BROWSER_ERROR_TITLES = (
    "problem loading page", "server not found", "unable to connect",
    "connection timed out", "address not found", "network error",
    "page not available", "err_", "site can't be reached",
)


def _is_browser_error_page(current_url: str, title: str) -> bool:
    """Return True if the browser landed on its own built-in error page."""
    cu = (current_url or "").lower()
    tl = (title or "").lower()
    if any(cu.startswith(p) for p in _BROWSER_ERROR_URLS):
        return True
    if any(p in tl for p in _BROWSER_ERROR_TITLES):
        return True
    return False


def selenium_check(url: str, driver, cf_signs: list, bad_titles: list) -> tuple[str, str, str]:
    if driver is None:
        return "Error", "", "Driver not initialized"
    driver.set_page_load_timeout(30)
    try:
        driver.get(url)
    except TimeoutException:
        pass
    except Exception as e:
        log.warning("selenium_check connection failed for %s: %s", url, e)
        return "Inactive", "", f"Connection failed: {str(e)[:60]}"

    start = time.time()
    title = page_source = ""

    while time.time() - start < HARD_TIMEOUT:
        try:
            title       = driver.title.strip() if driver.title else ""
            page_source = driver.page_source.lower() if driver.page_source else ""
            ready_state = driver.execute_script("return document.readyState")

            if any(x.lower() in page_source for x in cf_signs):
                return "Active", title, "WAF / Security Check Detected"

            if ready_state == "complete":
                break
            if time.time() - start > SOFT_TIMEOUT and title:
                break
        except WebDriverException:
            pass
        time.sleep(1)

    time.sleep(2)
    try:
        title        = driver.title.strip() if driver.title else ""
        page_source  = driver.page_source.lower() if driver.page_source else ""
        current_url  = driver.current_url or ""
    except Exception:
        current_url = ""

    # Browser built-in error page (Firefox "Problem loading page", Chrome "ERR_*")
    # These are never user content — always a connection failure
    if _is_browser_error_page(current_url, title):
        return "Inactive", title, "Browser error page (connection/DNS failure)"

    dns_errors = ["err_connection", "dns_probe", "this site can't be reached",
                  "server not found", "took too long to respond"]
    if any(e in page_source for e in dns_errors):
        return "Inactive", title, "DNS / Connection Error"

    # HTTP error codes in title (e.g. "403 Forbidden", "500 Internal Server Error")
    http_bad, http_reason = is_http_error_title(title)
    if http_bad:
        return "Inactive", title, http_reason

    bad, matched = is_bad_title(title, bad_titles)
    if bad:
        return "Inactive", title, f"Bad Title: '{matched}'"

    if not title:
        # JS-heavy pages may still be rendering — wait once more then recheck
        time.sleep(3)
        try:
            title       = driver.title.strip() if driver.title else ""
            page_source = driver.page_source.lower() if driver.page_source else ""
            current_url = driver.current_url or ""
        except Exception:
            pass

        if _is_browser_error_page(current_url, title):
            return "Inactive", title, "Browser error page (connection/DNS failure)"

        if title:
            # Got a title after extra wait — re-run bad-title checks
            http_bad, http_reason = is_http_error_title(title)
            if http_bad:
                return "Inactive", title, http_reason
            bad, matched = is_bad_title(title, bad_titles)
            if bad:
                return "Inactive", title, f"Bad Title: '{matched}'"
            elapsed = time.time() - start
            return "Active", title, f"OK — Delayed ({round(elapsed, 1)}s)"

        try:
            body = driver.find_element("tag name", "body").text.strip()
            if len(body) < 30:
                return "Inactive", "", "Empty page body"
        except Exception:
            return "Inactive", "", "No readable body content"

    elapsed = time.time() - start
    if elapsed < SOFT_TIMEOUT:
        return "Active", title, f"OK ({round(elapsed, 1)}s)"
    return "Active", title, f"OK — Slow ({round(elapsed, 1)}s)"


def dual_check(url: str, drv_chrome, drv_firefox, cf_signs: list,
               bad_titles: list, use_ff: bool) -> dict:
    sc, tc, mc = selenium_check(url, drv_chrome, cf_signs, bad_titles)

    if sc == "Active":
        return {"status": "Active", "title": tc, "notes": mc,
                "verified": "Chrome", "method": "Chrome"}

    # Only run Firefox fallback when Chrome reported Inactive (not driver Error)
    if sc == "Inactive" and use_ff and drv_firefox:
        log.info("   Chrome→Inactive, re-checking with Firefox: %s", url)
        sf, tf, mf = selenium_check(url, drv_firefox, cf_signs, bad_titles)
        if sf == "Active":
            return {"status": "Active", "title": tf,
                    "notes": f"Chrome: {mc} | Firefox: Active",
                    "verified": "Firefox override", "method": "Firefox"}
        # Both Inactive — trust the more descriptive reason
        combined_notes = f"Chrome: {mc} | Firefox: {mf}"
        return {"status": "Inactive", "title": tf or tc,
                "notes": combined_notes,
                "verified": "Both browsers confirmed", "method": "Chrome + Firefox"}

    # Chrome Error (driver crash) or Firefox disabled
    return {"status": sc if sc == "Inactive" else "Inactive",
            "title": tc, "notes": mc,
            "verified": "Chrome only", "method": "Chrome"}


def determine_status_change(old, new) -> str:
    if pd.isna(old) or str(old).strip() in ("", "nan"):
        return "New"
    o, n = str(old).strip().lower(), str(new).strip().lower()
    if o == n:
        return "Unchanged"
    if "active" in o and "active" not in n:
        return "↓ Downgrade"
    if "active" not in o and "active" in n:
        return "↑ Upgrade"
    return "Changed"


# ── Drag-and-drop file zone ────────────────────────────────────────────────────

class DropZone(QFrame):
    """Clickable drag-and-drop zone for Excel/CSV files."""

    file_dropped = pyqtSignal(str)

    _EXTS = {".xlsx", ".xls", ".csv"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop_zone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        self.icon_lbl = QLabel("⬆")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(18)
        self.icon_lbl.setFont(f)

        self.text_lbl = QLabel("Drop Excel / CSV here\nor click to browse")
        self.text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_lbl.setObjectName("subtext")

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.text_lbl)

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Dataset", "",
            "Excel / CSV Files (*.xlsx *.xls *.csv)")
        if path:
            self.file_dropped.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(self._valid(u.toLocalFile()) for u in urls):
                self.setObjectName("drop_zone_hover")
                self.setStyleSheet(self.styleSheet())
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setObjectName("drop_zone")
        self.setStyleSheet(self.styleSheet())

    def dropEvent(self, event: QDropEvent):
        self.setObjectName("drop_zone")
        self.setStyleSheet(self.styleSheet())
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self._valid(path):
                self.file_dropped.emit(path)
                break
        event.acceptProposedAction()

    def _valid(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in self._exts

    # re-define using class var properly
    def _valid(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in self._EXTS


# ── Metric Card widget ─────────────────────────────────────────────────────────

class MetricCard(QFrame):
    def __init__(self, label: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        self.val_label = QLabel(value)
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont()
        f.setPointSize(22)
        f.setWeight(QFont.Weight.Bold)
        self.val_label.setFont(f)
        self.val_label.setStyleSheet(f"color: {color}; border: none;")

        self.desc_label = QLabel(label)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setObjectName("subtext")

        layout.addWidget(self.val_label)
        layout.addWidget(self.desc_label)

    def set_value(self, v: str):
        self.val_label.setText(v)


# ── Audit worker thread ────────────────────────────────────────────────────────

class AuditWorker(QThread):
    progress     = pyqtSignal(int, int)
    status_msg   = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    finished     = pyqtSignal()
    error        = pyqtSignal(str)

    def __init__(self, urls: list, skip_domains: list, bad_titles: list,
                 cf_signs: list, headless: bool, use_ff: bool):
        super().__init__()
        self.urls         = urls
        self.skip_domains = skip_domains
        self.bad_titles   = bad_titles
        self.cf_signs     = cf_signs
        self.headless     = headless
        self.use_ff       = use_ff
        self._paused      = False
        self._stop        = False

    def pause(self):  self._paused = True
    def resume(self): self._paused = False
    def stop(self):   self._stop = True; self._paused = False

    def run(self):
        self.status_msg.emit("Initializing Chrome driver...")
        drv_chrome  = setup_chrome(headless=self.headless)
        drv_firefox = None

        if not drv_chrome:
            msg = (
                "Chrome WebDriver failed to start.\n\n"
                "Most likely cause: chromedriver.exe version does not match\n"
                "your installed Chrome version.\n\n"
                "Fix:\n"
                "  1. Check your Chrome version at chrome://version\n"
                "  2. Download the matching chromedriver from:\n"
                "     https://googlechromelabs.github.io/chrome-for-testing/\n"
                "  3. Replace chromedriver.exe in the same folder as this app.\n\n"
                "Details saved to: url_auditor_errors.log\n"
                "(in the same folder as this app)"
            )
            log.error("Chrome WebDriver could not start — all strategies exhausted")
            self.error.emit(msg)
            self.finished.emit()
            return

        if self.use_ff:
            self.status_msg.emit("Initializing Firefox driver...")
            drv_firefox = setup_firefox(headless=self.headless)

        total = len(self.urls)
        try:
            for i, (norm_key, raw_url) in enumerate(self.urls):
                if self._stop:
                    break
                while self._paused:
                    if self._stop:
                        break
                    time.sleep(0.3)
                if self._stop:
                    break

                url = full_url(raw_url)
                self.status_msg.emit(
                    f"[{i+1}/{total}]  {url[:80]}{'...' if len(url) > 80 else ''}")
                self.progress.emit(i + 1, total)

                log.info("── [%d/%d] %s", i + 1, total, url)

                t0 = time.time()
                if check_skip_domain(url, self.skip_domains):
                    res = {
                        "norm_key": norm_key, "url": raw_url,
                        "status": "Skipped", "title": "—",
                        "notes": "Domain in skip list",
                        "method": "Skip Rule", "verified": "N/A",
                        "skipped": True, "time_s": 0.0,
                    }
                    log.info("   SKIPPED — domain in skip list")
                else:
                    r = dual_check(url, drv_chrome, drv_firefox,
                                   self.cf_signs, self.bad_titles, self.use_ff)
                    res = {
                        "norm_key": norm_key, "url": raw_url,
                        "skipped": False,
                        "time_s": round(time.time() - t0, 2),
                        **r,
                    }
                    log.info("   STATUS: %s | METHOD: %s | NOTES: %s",
                             res["status"], res.get("method", ""), res.get("notes", ""))
                log.info("")  # blank line between entries
                self.result_ready.emit(res)

            self.status_msg.emit(
                "Audit complete." if not self._stop else "Audit stopped by user.")
        finally:
            try:
                if drv_chrome:  drv_chrome.quit()
                if drv_firefox: drv_firefox.quit()
            except Exception:
                pass
            self.finished.emit()


# ── Main window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    TABLE_COLS = ["#", "URL", "Status", "Title", "Method", "Verified", "Time (s)"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}  —  by {DEVELOPER}")
        self.resize(1400, 860)
        self.setMinimumSize(900, 600)
        icon = _app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.df           = None
        self.unique_urls  = []
        self.results_dict = {}
        self.worker: AuditWorker | None = None

        self.skip_domains, self.bad_titles, self.cf_signs, \
            self._saved_url_col, self._saved_status_col = load_config()

        # Debounce timer for auto-saving rules (fires 1.5s after last keystroke)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1500)
        self._autosave_timer.timeout.connect(self._do_autosave)

        self._setup_menu()
        self._build_ui()
        self._apply_theme()
        self._auto_load_input()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _setup_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        act_open = QAction("&Open File…", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_file_dialog)
        file_menu.addAction(act_open)

        act_export = QAction("&Export Report…", self)
        act_export.setShortcut("Ctrl+S")
        act_export.triggered.connect(self._export_results)
        file_menu.addAction(act_export)

        file_menu.addSeparator()
        act_quit = QAction("&Quit", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        theme_menu = mb.addMenu("&Theme")
        for name in THEMES:
            act = QAction(name, self)
            act.triggered.connect(lambda checked, n=name: self._switch_theme(n))
            theme_menu.addAction(act)

        help_menu = mb.addMenu("&Help")
        act_about = QAction("&About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        act_gh = QAction("View on &GitHub", self)
        act_gh.triggered.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/sudhirjangra/url-auditor-pro")))
        help_menu.addAction(act_gh)

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_sidebar()
        main_layout.addWidget(self.sidebar, 0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 0)
        content_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        content_layout.addWidget(self.tabs)
        main_layout.addWidget(content, 1)

        self._build_dashboard_tab()
        self._build_rules_tab()
        self._build_about_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — drop or open a file to begin.")

    def _build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("card")
        self.sidebar.setFixedWidth(290)
        self.sidebar.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(10)

        title = QLabel(f"⚡  {APP_NAME}")
        title.setObjectName("heading")
        layout.addWidget(title)

        ver_lbl = QLabel(f"v{APP_VERSION}  —  Open Source URL Checker")
        ver_lbl.setObjectName("subtext")
        layout.addWidget(ver_lbl)
        layout.addWidget(self._sep())

        # File drop zone
        grp_file = QGroupBox("Dataset")
        grp_file_layout = QVBoxLayout(grp_file)
        grp_file_layout.setSpacing(6)

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._load_file)
        grp_file_layout.addWidget(self.drop_zone)

        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setObjectName("subtext")
        self.lbl_file.setWordWrap(True)
        grp_file_layout.addWidget(self.lbl_file)

        lbl_url = QLabel("URL Column")
        lbl_url.setObjectName("subtext")
        grp_file_layout.addWidget(lbl_url)
        self.combo_url = QComboBox()
        self.combo_url.addItem("(None)")
        self.combo_url.currentTextChanged.connect(self._on_url_col_change)
        self.combo_url.currentTextChanged.connect(self._schedule_autosave)
        grp_file_layout.addWidget(self.combo_url)

        lbl_status = QLabel("Previous Status Column  (optional)")
        lbl_status.setObjectName("subtext")
        grp_file_layout.addWidget(lbl_status)
        self.combo_status = QComboBox()
        self.combo_status.addItem("(None)")
        self.combo_status.currentTextChanged.connect(self._schedule_autosave)
        grp_file_layout.addWidget(self.combo_status)

        layout.addWidget(grp_file)

        # Skip domains — auto-saves on change
        grp_skip = QGroupBox("Skip Domains  (comma-separated)")
        grp_skip_layout = QVBoxLayout(grp_skip)
        self.txt_skip = QTextEdit()
        self.txt_skip.setPlaceholderText("e.g.  fgov.be, go.cr, gob.do")
        self.txt_skip.setFixedHeight(70)
        self.txt_skip.setText(", ".join(self.skip_domains))
        self.txt_skip.textChanged.connect(self._schedule_autosave)
        grp_skip_layout.addWidget(self.txt_skip)
        layout.addWidget(grp_skip)

        # Browser options
        grp_browser = QGroupBox("Browser Options")
        grp_browser_layout = QVBoxLayout(grp_browser)
        grp_browser_layout.setSpacing(6)

        self.chk_headless = QCheckBox("Headless Mode  (hidden browser)")
        self.chk_headless.setChecked(True)
        grp_browser_layout.addWidget(self.chk_headless)

        self.chk_firefox = QCheckBox("Enable Firefox  (dual-browser verify)")
        self.chk_firefox.setChecked(True)
        grp_browser_layout.addWidget(self.chk_firefox)

        layout.addWidget(grp_browser)

        layout.addStretch()
        layout.addWidget(self._sep())

        dev_lbl = QLabel(f"Developed by  {DEVELOPER}")
        dev_lbl.setObjectName("dev_credit")
        layout.addWidget(dev_lbl)

        note = QLabel(f"Config: {CONFIG_FILENAME}  (auto-saved)")
        note.setObjectName("subtext")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(8)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        self.btn_start = QPushButton("▶  Start Audit")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._start_audit)
        ctrl.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_pause.setObjectName("btn_pause")
        self.btn_pause.setMinimumHeight(36)
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_pause.setEnabled(False)
        ctrl.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹  Stop")
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop_audit)
        self.btn_stop.setEnabled(False)
        ctrl.addWidget(self.btn_stop)

        self.btn_export = QPushButton("⬇  Export Excel Report")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setMinimumHeight(36)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self._export_results)
        self.btn_export.setEnabled(False)
        ctrl.addWidget(self.btn_export)

        layout.addLayout(ctrl)

        metrics_frame = QFrame()
        metrics_frame.setObjectName("card")
        metrics_layout = QHBoxLayout(metrics_frame)
        metrics_layout.setSpacing(1)
        metrics_layout.setContentsMargins(4, 4, 4, 4)

        t = T()
        self.m_checked  = MetricCard("Checked",  "0 / 0", t["text_primary"])
        self.m_active   = MetricCard("Active",   "0",      t["success"])
        self.m_inactive = MetricCard("Inactive", "0",      t["danger"])
        self.m_skipped  = MetricCard("Skipped",  "0",      t["purple"])

        for m in (self.m_checked, self.m_active, self.m_inactive, self.m_skipped):
            metrics_layout.addWidget(m, 1)
        layout.addWidget(metrics_frame)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready — load a file and click Start Audit.")
        self.lbl_status.setObjectName("subtext")
        layout.addWidget(self.lbl_status)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.TABLE_COLS))
        self.table.setHorizontalHeaderLabels(self.TABLE_COLS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        # Col 0=#, 1=URL, 2=Status, 3=Title, 4=Method, 5=Verified, 6=Time(s)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 360)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 260)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(5, 160)
        self.table.setColumnWidth(6, 80)

        self.table.cellDoubleClicked.connect(self._on_cell_double_click)
        self.table.setToolTip("Double-click URL to open in browser")
        layout.addWidget(self.table, 1)

        self.tabs.addTab(tab, "  Dashboard  ")

    def _build_rules_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(10)

        banner = QFrame()
        banner.setObjectName("card")
        banner_layout = QVBoxLayout(banner)
        info = QLabel(
            "Edit detection rules below. Changes auto-save to xml after 1.5 seconds.\n"
            "Rules apply on the next audit run.")
        info.setObjectName("subtext")
        info.setWordWrap(True)
        banner_layout.addWidget(info)
        layout.addWidget(banner)

        grp_bad = QGroupBox(
            "Inactive Title Keywords  —  marked Inactive when page title contains any of these")
        grp_bad_layout = QVBoxLayout(grp_bad)
        self.txt_bad_titles = QTextEdit()
        self.txt_bad_titles.setText(", ".join(self.bad_titles))
        self.txt_bad_titles.setFixedHeight(120)
        self.txt_bad_titles.textChanged.connect(self._schedule_autosave)
        grp_bad_layout.addWidget(self.txt_bad_titles)
        layout.addWidget(grp_bad)

        grp_waf = QGroupBox(
            "WAF / Security Check Keywords  —  marked Active (WAF) when page HTML contains any of these")
        grp_waf_layout = QVBoxLayout(grp_waf)
        self.txt_cf = QTextEdit()
        self.txt_cf.setText(", ".join(self.cf_signs))
        self.txt_cf.setFixedHeight(120)
        self.txt_cf.textChanged.connect(self._schedule_autosave)
        grp_waf_layout.addWidget(self.txt_cf)
        layout.addWidget(grp_waf)

        layout.addStretch()

        self.lbl_autosave = QLabel("")
        self.lbl_autosave.setObjectName("subtext")
        self.lbl_autosave.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.lbl_autosave)

        self.tabs.addTab(tab, "  Rules  ")

    def _build_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)
        layout.addStretch()

        title = QLabel(f"⚡  {APP_NAME}")
        f = QFont()
        f.setPointSize(24)
        f.setWeight(QFont.Weight.Bold)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        ver = QLabel(f"Version {APP_VERSION}")
        ver.setObjectName("subtext")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        dev = QLabel(f"Developed by  {DEVELOPER}")
        dev.setObjectName("dev_credit")
        dev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        df = QFont()
        df.setPointSize(13)
        df.setWeight(QFont.Weight.Bold)
        dev.setFont(df)
        layout.addWidget(dev)

        layout.addWidget(self._sep())

        desc = QLabel(
            "Open-source URL health checker with Selenium-based dual-browser verification.\n\n"
            "• Checks URLs from Excel/CSV files using Chrome and optionally Firefox\n"
            "• Detects inactive pages via title keywords, HTTP error codes, DNS errors\n"
            "• Identifies WAF / Cloudflare challenges\n"
            "• Drag-and-drop file loading\n"
            "• Auto-saves detection rules to XML config\n"
            "• Exports detailed Excel reports with status change tracking\n\n"
            "Requires chromedriver.exe (and optionally geckodriver.exe)\n"
            "in the same folder as this application."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_gh = QPushButton("View on GitHub")
        btn_gh.setObjectName("btn_export")
        btn_gh.setFixedWidth(220)
        btn_gh.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/sudhirjangra/url-auditor-pro")))
        layout.addWidget(btn_gh, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        self.tabs.addTab(tab, "  About  ")

    def _sep(self) -> QFrame:
        s = QFrame()
        s.setObjectName("separator")
        s.setFrameShape(QFrame.Shape.HLine)
        return s

    # ── Auto-load ─────────────────────────────────────────────────────────────

    def _auto_load_input(self):
        """If input.xlsx exists next to the EXE/script, load it silently."""
        candidate = os.path.join(_get_base_dir(), "input.xlsx")
        if os.path.exists(candidate):
            self._load_file(candidate)
            self.status_bar.showMessage(
                f"Auto-loaded: input.xlsx  ({len(self.df):,} rows)")

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        self.setStyleSheet(build_stylesheet(T()))
        self._refresh_metric_colors()

    def _refresh_metric_colors(self):
        t = T()
        self.m_checked.val_label.setStyleSheet(
            f"color: {t['text_primary']}; border: none;")
        self.m_active.val_label.setStyleSheet(
            f"color: {t['success']}; border: none;")
        self.m_inactive.val_label.setStyleSheet(
            f"color: {t['danger']}; border: none;")
        self.m_skipped.val_label.setStyleSheet(
            f"color: {t['purple']}; border: none;")

    def _switch_theme(self, name: str):
        global CURRENT_THEME
        CURRENT_THEME = name
        self._apply_theme()
        self._recolor_table()

    # ── File loading ──────────────────────────────────────────────────────────

    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Dataset", "",
            "Excel / CSV Files (*.xlsx *.xls *.csv)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            self.df = (pd.read_csv(path) if path.endswith(".csv")
                       else pd.read_excel(path))
            fname = os.path.basename(path)
            self.lbl_file.setText(f"✓  {fname}  ({len(self.df):,} rows)")
            self.lbl_file.setStyleSheet(f"color: {T()['success']};")

            cols = list(self.df.columns)
            self.combo_url.clear()
            self.combo_url.addItems(cols)
            self.combo_status.clear()
            self.combo_status.addItem("(None)")
            self.combo_status.addItems(cols)

            # restore previously saved column selections
            if self._saved_url_col and self._saved_url_col in cols:
                self.combo_url.setCurrentText(self._saved_url_col)
            if self._saved_status_col and self._saved_status_col in cols:
                self.combo_status.setCurrentText(self._saved_status_col)

            self._prepare_urls()
            self.status_bar.showMessage(f"Loaded: {fname}  ({len(self.df):,} rows)")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Failed to load:\n{e}")

    def _on_url_col_change(self, _):
        if self.df is not None:
            self._prepare_urls()

    def _prepare_urls(self):
        if self.df is None:
            return
        col = self.combo_url.currentText()
        if not col or col == "(None)" or col not in self.df.columns:
            return

        self.df["_raw_url"]  = self.df[col].apply(sanitize_input_url)
        self.df["_norm_key"] = self.df["_raw_url"].apply(normalize_url_key)

        seen = set()
        self.unique_urls = []
        for _, row in self.df.iterrows():
            k = row["_norm_key"]
            if k and k not in seen:
                seen.add(k)
                self.unique_urls.append((k, row["_raw_url"]))

        n = len(self.unique_urls)
        self.m_checked.set_value(f"0 / {n}")
        self.status_bar.showMessage(f"Column '{col}'  —  {n:,} unique URLs ready.")

    # ── Auto-save rules ───────────────────────────────────────────────────────

    def _schedule_autosave(self):
        self._autosave_timer.start()

    def _do_autosave(self):
        self.skip_domains = [x.strip() for x in self.txt_skip.toPlainText().split(",") if x.strip()]
        self.bad_titles   = [x.strip() for x in self.txt_bad_titles.toPlainText().split(",") if x.strip()]
        self.cf_signs     = [x.strip() for x in self.txt_cf.toPlainText().split(",") if x.strip()]
        url_col    = self.combo_url.currentText()
        status_col = self.combo_status.currentText()
        save_config(self.skip_domains, self.bad_titles, self.cf_signs,
                    url_col if url_col != "(None)" else "",
                    status_col if status_col != "(None)" else "")
        self.lbl_autosave.setText(
            f"Auto-saved  {datetime.now().strftime('%H:%M:%S')}")
        self.status_bar.showMessage(
            f"Config auto-saved to {CONFIG_FILENAME}", 3000)

    # ── Audit control ─────────────────────────────────────────────────────────

    def _start_audit(self):
        if self.df is None:
            QMessageBox.warning(self, "No Data", "Load a dataset file first.")
            return
        col = self.combo_url.currentText()
        if not col or col == "(None)" or col not in self.df.columns:
            QMessageBox.warning(self, "No Column", "Select a valid URL column.")
            return
        if not self.unique_urls:
            QMessageBox.warning(self, "No URLs",
                                "No valid URLs found in the selected column.")
            return
        if self.worker and self.worker.isRunning():
            return

        # Sync latest rule text in case autosave timer hasn't fired yet
        self.skip_domains = [x.strip() for x in self.txt_skip.toPlainText().split(",") if x.strip()]
        self.bad_titles   = [x.strip() for x in self.txt_bad_titles.toPlainText().split(",") if x.strip()]
        self.cf_signs     = [x.strip() for x in self.txt_cf.toPlainText().split(",") if x.strip()]

        self.results_dict = {}
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.unique_urls))
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_export.setEnabled(False)
        self.tabs.setCurrentIndex(0)

        self.worker = AuditWorker(
            urls=self.unique_urls,
            skip_domains=self.skip_domains,
            bad_titles=self.bad_titles,
            cf_signs=self.cf_signs,
            headless=self.chk_headless.isChecked(),
            use_ff=self.chk_firefox.isChecked(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.status_msg.connect(self._on_status)
        self.worker.result_ready.connect(self._on_result)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _toggle_pause(self):
        if not self.worker:
            return
        if self.worker._paused:
            self.worker.resume()
            self.btn_pause.setText("⏸  Pause")
            self.status_bar.showMessage("Audit resumed.")
        else:
            self.worker.pause()
            self.btn_pause.setText("▶  Resume")
            self.status_bar.showMessage("Audit paused.")

    def _stop_audit(self):
        if self.worker:
            self.worker.stop()
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

    # ── Worker signals ────────────────────────────────────────────────────────

    def _on_progress(self, done: int, total: int):
        self.progress_bar.setValue(done)
        self.m_checked.set_value(f"{done} / {total}")

    def _on_status(self, msg: str):
        self.lbl_status.setText(msg)
        self.status_bar.showMessage(msg)

    def _on_result(self, res: dict):
        self.results_dict[res["norm_key"]] = res
        self._add_table_row(res)
        self._update_metrics()

    def _on_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("⏸  Pause")
        self.btn_stop.setEnabled(False)
        self.table.setSortingEnabled(True)
        if self.results_dict:
            self.btn_export.setEnabled(True)
        self.status_bar.showMessage(
            f"Audit complete. {len(self.results_dict):,} URLs processed.")

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "Driver Error", msg)
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

    # ── Table helpers ─────────────────────────────────────────────────────────

    def _add_table_row(self, res: dict):
        t = T()
        # Insert at top so newest result appears first (descending order)
        self.table.insertRow(0)

        # Update existing # indices (shift all down by 1)
        for r in range(1, self.table.rowCount()):
            idx_item = self.table.item(r, 0)
            if idx_item:
                try:
                    idx_item.setText(str(int(idx_item.text()) + 1))
                except ValueError:
                    pass

        status  = res.get("status", "")
        skipped = res.get("skipped", False)

        if status == "Active":
            bg = QColor(t["row_active"])
            sc = QColor(t["success"])
        elif skipped or status == "Skipped":
            bg = QColor(t["row_skip"])
            sc = QColor(t["purple"])
        else:
            bg = QColor(t["row_inactive"])
            sc = QColor(t["danger"])

        # Cols: 0=#, 1=URL, 2=Status, 3=Title, 4=Method, 5=Verified, 6=Time(s)
        seq_num = len(self.results_dict)
        values = [
            str(seq_num),
            res.get("url", ""),
            status,
            res.get("title", ""),
            res.get("method", ""),
            res.get("verified", ""),
            str(res.get("time_s", "")),
        ]

        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setBackground(bg)
            if col == 2:  # Status
                item.setForeground(sc)
                f = QFont()
                f.setWeight(QFont.Weight.Bold)
                item.setFont(f)
            elif col == 1:  # URL
                item.setToolTip(f"Double-click to open in browser:  {val}")
                item.setForeground(QColor(t["accent"]))
            elif col == 0:  # #
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(QColor(t["text_secondary"]))
            self.table.setItem(0, col, item)

    def _recolor_table(self):
        t = T()
        for row in range(self.table.rowCount()):
            si = self.table.item(row, 2)  # Status is col 2
            if not si:
                continue
            status = si.text()
            if status == "Active":
                bg = QColor(t["row_active"]); sc = QColor(t["success"])
            elif status == "Skipped":
                bg = QColor(t["row_skip"]);   sc = QColor(t["purple"])
            else:
                bg = QColor(t["row_inactive"]); sc = QColor(t["danger"])
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(bg)
                    if col == 2:  # Status
                        item.setForeground(sc)
                    elif col == 1:  # URL
                        item.setForeground(QColor(t["accent"]))
                    elif col == 0:  # #
                        item.setForeground(QColor(t["text_secondary"]))

    def _update_metrics(self):
        results  = list(self.results_dict.values())
        total    = len(self.unique_urls)
        checked  = len(results)
        active   = sum(1 for r in results if r["status"] == "Active")
        inactive = sum(1 for r in results if r["status"] == "Inactive")
        skipped  = sum(1 for r in results if r.get("skipped"))
        self.m_checked.set_value(f"{checked} / {total}")
        self.m_active.set_value(str(active))
        self.m_inactive.set_value(str(inactive))
        self.m_skipped.set_value(str(skipped))

    def _on_cell_double_click(self, row: int, col: int):
        url_item = self.table.item(row, 1)  # URL is col 1
        if url_item:
            raw = url_item.text().strip()
            if raw:
                QDesktopServices.openUrl(QUrl(full_url(raw)))

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_results(self):
        if not self.results_dict:
            QMessageBox.warning(self, "No Results", "Run an audit first.")
            return

        now       = datetime.now()
        ts_folder = now.strftime("output_%Y-%m-%d_%H-%M-%S")
        out_dir   = os.path.join(_get_base_dir(), ts_folder)
        os.makedirs(out_dir, exist_ok=True)
        filename  = now.strftime("url_audit_report_%d-%m-%Y_%H-%M.xlsx")
        path      = os.path.join(out_dir, filename)

        try:
            out = self.df.copy()
            sc  = self.combo_status.currentText()

            def g(k, f): return self.results_dict.get(k, {}).get(f, "")

            out["New Status"]  = out["_norm_key"].apply(lambda k: g(k, "status"))
            out["Page Title"]  = out["_norm_key"].apply(lambda k: g(k, "title"))
            out["Notes"]       = out["_norm_key"].apply(lambda k: g(k, "notes"))
            out["Verified By"] = out["_norm_key"].apply(lambda k: g(k, "verified"))
            out["Method"]      = out["_norm_key"].apply(lambda k: g(k, "method"))
            out["Time (s)"]    = out["_norm_key"].apply(lambda k: g(k, "time_s"))
            out["Skipped"]     = out["_norm_key"].apply(lambda k: g(k, "skipped"))

            if sc not in ("(None)", ""):
                out["Status Change"] = out.apply(
                    lambda row: determine_status_change(row[sc], row["New Status"]),
                    axis=1)

            out.drop(columns=["_raw_url", "_norm_key"], inplace=True, errors="ignore")

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                out.to_excel(writer, index=False, sheet_name="URL Audit")
                writer.sheets["URL Audit"].freeze_panes = "A2"

            QMessageBox.information(self, "Export Done", f"Report saved:\n{path}")
            self.status_bar.showMessage(f"Exported: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error:\n{e}")

    def _show_about(self):
        self.tabs.setCurrentIndex(2)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()


# ── Entry ──────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setFont(QFont("Segoe UI", 10))
    icon = _app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
