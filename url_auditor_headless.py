# -*- coding: utf-8 -*-
"""
url_auditor_headless.py — CLI / GitHub Actions automation entry point.

Behaviour (identical backend to GUI version):
  1. Look for input.xlsx in the same directory as this script / frozen EXE.
  2. Read url_column and status_column from url_auditor_config.xml.
  3. Run the full Selenium dual-browser audit (Chrome + optional Firefox).
  4. Save output to  output_YYYY-MM-DD_HH-MM-SS/url_audit_report_DD-MM-YYYY_HH-MM.xlsx
     in the same directory.
  5. Commit-friendly exit codes: 0 = success, 1 = fatal error.

CLI override (optional):
  python url_auditor_headless.py [input_file] [--url-col COL] [--status-col COL]
                                 [--no-firefox] [--visible]
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime

# ── path helpers shared with GUI ───────────────────────────────────────────────

def _get_base_dir() -> str:
    return (os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))


# Add this script's dir to sys.path so we can import url_auditor internals
_HERE = _get_base_dir()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Import shared backend — suppress GUI import side-effects by checking frozen flag
import pandas as pd
from url_auditor import (
    load_config,
    get_config_path,
    sanitize_input_url,
    normalize_url_key,
    full_url,
    check_skip_domain,
    setup_chrome,
    setup_firefox,
    dual_check,
    determine_status_change,
    APP_NAME,
    APP_VERSION,
)

# ── logging ────────────────────────────────────────────────────────────────────

def _init_logger() -> logging.Logger:
    ts     = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path   = os.path.join(_get_base_dir(), f"url_auditor_{ts}.log")
    logger = logging.getLogger("url_auditor_headless")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    # GitHub Actions runner console is cp1252 on Windows — force UTF-8 to avoid UnicodeEncodeError
    if hasattr(ch.stream, "reconfigure"):
        try:
            ch.stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    logger.addHandler(ch)

    return logger

log = _init_logger()


# ── main ───────────────────────────────────────────────────────────────────────

def run(input_path: str, url_col: str, status_col: str,
        use_firefox: bool = True, headless: bool = True) -> int:
    log.info("%s v%s — headless mode", APP_NAME, APP_VERSION)
    log.info("Input file : %s", input_path)
    log.info("URL column : %s", url_col)
    log.info("Status col : %s", status_col or "(none)")

    # ── load workbook ─────────────────────────────────────────────────────────
    try:
        df = (pd.read_csv(input_path) if input_path.endswith(".csv")
              else pd.read_excel(input_path))
    except Exception as e:
        log.error("Failed to load input file: %s", e)
        return 1

    if url_col not in df.columns:
        log.error("Column '%s' not found. Available: %s", url_col, list(df.columns))
        return 1

    skip_domains, bad_titles, cf_signs, _, _ = load_config()

    df["_raw_url"]  = df[url_col].apply(sanitize_input_url)
    df["_norm_key"] = df["_raw_url"].apply(normalize_url_key)

    seen = set()
    unique_urls = []
    for _, row in df.iterrows():
        k = row["_norm_key"]
        if k and k not in seen:
            seen.add(k)
            unique_urls.append((k, row["_raw_url"]))

    total = len(unique_urls)
    log.info("Unique URLs to check: %d", total)

    # ── start drivers ─────────────────────────────────────────────────────────
    log.info("Starting Chrome driver…")
    drv_chrome = setup_chrome(headless=headless)
    if not drv_chrome:
        log.error(
            "Chrome WebDriver failed to start.\n"
            "Check chromedriver.exe version matches installed Chrome.\n"
            "Download from: https://googlechromelabs.github.io/chrome-for-testing/")
        return 1

    drv_firefox = None
    if use_firefox:
        log.info("Starting Firefox driver…")
        drv_firefox = setup_firefox(headless=headless)
        if not drv_firefox:
            log.warning("Firefox driver unavailable — continuing with Chrome only.")

    # ── audit loop ────────────────────────────────────────────────────────────
    results: dict = {}
    try:
        for i, (norm_key, raw_url) in enumerate(unique_urls):
            url = full_url(raw_url)
            log.info("[%d/%d] %s", i + 1, total, url)
            t0 = time.time()

            if check_skip_domain(url, skip_domains):
                res = {
                    "status": "Skipped", "title": "—",
                    "notes": "Domain in skip list",
                    "method": "Skip Rule", "verified": "N/A",
                    "skipped": True, "time_s": 0.0,
                }
                log.info("  → SKIPPED")
            else:
                r   = dual_check(url, drv_chrome, drv_firefox,
                                 cf_signs, bad_titles, use_firefox)
                res = {
                    "skipped": False,
                    "time_s": round(time.time() - t0, 2),
                    **r,
                }
                log.info("  -> %s  [%s]  %.1fs",
                         res["status"], res.get("method", ""), res["time_s"])
            results[norm_key] = res
    finally:
        try:
            if drv_chrome:  drv_chrome.quit()
            if drv_firefox: drv_firefox.quit()
        except Exception:
            pass

    # ── build output dataframe ────────────────────────────────────────────────
    def g(k, f): return results.get(k, {}).get(f, "")

    out = df.copy()
    out["New Status"]  = out["_norm_key"].apply(lambda k: g(k, "status"))
    out["Page Title"]  = out["_norm_key"].apply(lambda k: g(k, "title"))
    out["Notes"]       = out["_norm_key"].apply(lambda k: g(k, "notes"))
    out["Verified By"] = out["_norm_key"].apply(lambda k: g(k, "verified"))
    out["Method"]      = out["_norm_key"].apply(lambda k: g(k, "method"))
    out["Time (s)"]    = out["_norm_key"].apply(lambda k: g(k, "time_s"))
    out["Skipped"]     = out["_norm_key"].apply(lambda k: g(k, "skipped"))

    if status_col and status_col in out.columns:
        out["Status Change"] = out.apply(
            lambda row: determine_status_change(row[status_col], row["New Status"]),
            axis=1)

    out.drop(columns=["_raw_url", "_norm_key"], inplace=True, errors="ignore")

    # ── save output ───────────────────────────────────────────────────────────
    now       = datetime.now()
    ts_folder = now.strftime("output_%Y-%m-%d_%H-%M-%S")
    out_dir   = os.path.join(_get_base_dir(), ts_folder)
    os.makedirs(out_dir, exist_ok=True)
    out_file  = os.path.join(out_dir, now.strftime("url_audit_report_%d-%m-%Y_%H-%M.xlsx"))

    try:
        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            out.to_excel(writer, index=False, sheet_name="URL Audit")
            writer.sheets["URL Audit"].freeze_panes = "A2"
    except Exception as e:
        log.error("Failed to write output: %s", e)
        return 1

    log.info("Output saved: %s", out_file)

    # summary
    statuses = [results[k]["status"] for k in results]
    active   = sum(1 for s in statuses if s == "Active")
    inactive = sum(1 for s in statuses if s == "Inactive")
    skipped  = sum(1 for s in statuses if s == "Skipped")
    log.info("Done — Active: %d  Inactive: %d  Skipped: %d  Total: %d",
             active, inactive, skipped, total)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} — headless audit")
    parser.add_argument("input_file", nargs="?",
                        help="Path to input Excel/CSV. Default: input.xlsx next to EXE.")
    parser.add_argument("--url-col",    default="",
                        help="Column containing URLs (overrides config).")
    parser.add_argument("--status-col", default="",
                        help="Column with previous status (overrides config).")
    parser.add_argument("--no-firefox", action="store_true",
                        help="Disable Firefox dual-browser fallback.")
    parser.add_argument("--visible",    action="store_true",
                        help="Run browsers in visible (non-headless) mode.")
    args = parser.parse_args()

    # resolve input file
    input_path = args.input_file
    if not input_path:
        input_path = os.path.join(_get_base_dir(), "input.xlsx")
    if not os.path.exists(input_path):
        log.error("Input file not found: %s", input_path)
        sys.exit(1)

    # resolve column names: CLI > config
    _, _, _, cfg_url_col, cfg_status_col = load_config()
    url_col    = args.url_col    or cfg_url_col
    status_col = args.status_col or cfg_status_col

    if not url_col:
        # fall back to first column in the file
        try:
            df_peek = (pd.read_csv(input_path, nrows=0) if input_path.endswith(".csv")
                       else pd.read_excel(input_path, nrows=0))
            url_col = df_peek.columns[0]
            log.warning("url_column not set in config — using first column: '%s'", url_col)
        except Exception as e:
            log.error("Cannot read column names: %s", e)
            sys.exit(1)

    exit_code = run(
        input_path  = input_path,
        url_col     = url_col,
        status_col  = status_col,
        use_firefox = not args.no_firefox,
        headless    = not args.visible,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
