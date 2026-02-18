import requests
from bs4 import BeautifulSoup
import json
import os
import datetime
import time
import subprocess

# --- CONFIGURATION (ONLY WHAT YOU WANT) ---
# --- Mezz USA commit ---
URLS = [
    # Predator BK Rush page
    "https://www.predatorcues.com/usa/pool-cues/break-jump-cues/bk-rush-break-cues.html",
    # Predator P3 page
    "https://www.predatorcues.com/usa/pool-cues/lines/p3-pool-cues.html",
]

# Mezz Power Break G (PBG) product handles (from the uploaded collection HTML)
MEZZ_PRODUCT_HANDLES = [
    "power-break-g",
    "power-break-g-no-wrap",
]

TOPIC_NAME = "bkrush_ric"
HISTORY_FILE = "history.json"
CHECK_INTERVAL = 3

def run_git_push():
    try:
        subprocess.run(["git", "add", HISTORY_FILE], check=True)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        subprocess.run(["git", "commit", "-m", f"Heartbeat: {timestamp}"], stdout=subprocess.DEVNULL)
        print("-> Pushing heartbeat to GitHub...")
        subprocess.run(["git", "push"], check=True)
        print("-> Push successful.")
    except Exception as e:
        print(f"Git Error: {e}")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(history):
    history["_last_checked"] = str(datetime.datetime.now())
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def send_push_alert(product_name, link, title_override=None):
    try:
        title = title_override if title_override else "Stock Update"
        requests.post(
            f"https://ntfy.sh/{TOPIC_NAME}",
            data=f"ITEM: {product_name}",
            headers={
                "Title": title,
                "Click": link,
                "Priority": "high",
                "Tags": "rotating_light,white_check_mark,buy",
            },
            timeout=15,
        )
        print(f"-> ALERT SENT for {product_name}")
    except Exception as e:
        print(f"Error sending alert: {e}")

def _normalize_status_text(s: str) -> str:
    s = (s or "").strip()
    if "In Stock" in s:
        return "In Stock"
    if "Out of Stock" in s:
        return "Out of Stock"
    return s if s else "Unknown"

def check_predator_page(url: str, soup: BeautifulSoup, stock_history: dict):
    products = soup.select("li.product-item")

    for product in products:
        name_el = product.select_one(".product-item-link")
        if not name_el:
            continue

        name = name_el.text.strip()
        link = name_el.get("href", url)

        stock_el = product.select_one(".amstockstatus")
        status_text = _normalize_status_text(stock_el.text if stock_el else "Unknown")

        # ---- FILTERS: ONLY WHAT YOU WANT ----
        # BK Rush page: ONLY BK Rush and IGNORE BLACK
        if "bk-rush-break-cues" in url:
            if ("BK Rush" not in name) or ("Black" in name):
                continue

        # P3 page: ONLY items containing P3 (avoid other random stuff on page)
        if "p3-pool-cues" in url:
            if "P3" not in name:
                continue

        key = f"predator::{name}"

        prev = stock_history.get(key, "Unknown")
        curr = "In Stock" if status_text == "In Stock" else "Out of Stock"

        # ALERT ONLY ON OUT -> IN
        if curr == "In Stock" and prev != "In Stock":
            send_push_alert(name, link, title_override="In Stock Alert")

        stock_history[key] = curr

def check_mezz_pbg(stock_history: dict, headers: dict):
    for handle in MEZZ_PRODUCT_HANDLES:
        js_url = f"https://mezzusa.com/products/{handle}.js"
        try:
            r = requests.get(js_url, headers=headers, timeout=20)
            r.raise_for_status()
            data = r.json()

            title = data.get("title", handle)
            product_url = f"https://mezzusa.com/products/{handle}"

            variants = data.get("variants", []) or []
            is_in_stock = any(bool(v.get("available")) for v in variants)

            key = f"mezz::{handle}"
            prev = stock_history.get(key, "Unknown")
            curr = "In Stock" if is_in_stock else "Out of Stock"

            # ALERT ONLY ON OUT -> IN
            if curr == "In Stock" and prev != "In Stock":
                send_push_alert(f"Mezz PBG: {title}", product_url, title_override="Mezz PBG In Stock")

            stock_history[key] = curr

        except Exception as e:
            print(f"Error scanning Mezz {handle}: {e}")

def check_stock():
    stock_history = load_history()
    print(f"\n--- Scan started at {datetime.datetime.now().strftime('%H:%M:%S')} ---")

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    }

    # Predator scans (ONLY BK Rush + P3, filtered)
    for url in URLS:
        try:
            response = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.content, "html.parser")
            check_predator_page(url, soup, stock_history)
        except Exception as e:
            print(f"Error scanning {url}: {e}")

    # Mezz scans (ONLY Power Break G)
    check_mezz_pbg(stock_history, headers)

    save_history(stock_history)
    run_git_push()

if __name__ == "__main__":
    print("Local Bot Started...")
    while True:
        check_stock()
        print(f"Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)
