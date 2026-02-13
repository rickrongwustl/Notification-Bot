import requests
from bs4 import BeautifulSoup
import json
import os
import datetime # Add this at the top

def save_history(history):
    # Add a timestamp so the file content CHANGES every single time
    history["_last_checked"] = str(datetime.datetime.now())
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

# --- CONFIGURATION ---
URLS = [
    "https://www.predatorcues.com/usa/pool-cues/break-jump-cues/bk-rush-break-cues.html",
    "https://www.predatorcues.com/usa/pool-cues/lines/p3-pool-cues.html",
    "https://www.predatorcues.com/usa/new/new/new-arrivals.html"
]
TOPIC_NAME = "bkrush_ric" 
HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def send_push_alert(product_name, link, title_override=None):
    try:
        title = title_override if title_override else "Predator Stock Update"
        requests.post(f"https://ntfy.sh/{TOPIC_NAME}", 
            data=f"ITEM: {product_name}",
            headers={
                "Title": title, 
                "Click": link, 
                "Priority": "high", 
                "Tags": "rotating_light,white_check_mark,buy"
            }
        )
        print(f"-> ALERT SENT for {product_name}")
    except Exception as e:
        print(f"Error sending alert: {e}")

def check_stock():
    # 1. Load previous history from file
    stock_history = load_history()
    print(f"Loaded history for {len(stock_history)} items.")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    for url in URLS:
        print(f"Scanning: {url} ...")
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.content, "html.parser")
            products = soup.select("li.product-item")

            for product in products:
                name_el = product.select_one(".product-item-link")
                if not name_el: continue
                name = name_el.text.strip()
                link = name_el.get('href', url)
                
                stock_el = product.select_one(".amstockstatus")
                status_text = stock_el.text.strip() if stock_el else "Unknown"
                
                # --- LOGIC ---
                if "new-arrivals" in url:
                    if "LE True Splice 16" in name:
                        # If we haven't seen this specific item before
                        if name not in stock_history:
                            print(f"  !!! SPECIAL FIND: {name}")
                            send_push_alert(name, link, title_override="NEW LISTING DETECTED")
                else:
                    # Ignore Black BK Rush
                    if "BK Rush" in name and "Black" in name:
                        stock_history[name] = status_text
                        continue

                    is_in_stock = "In Stock" in status_text
                    previous_status = stock_history.get(name, "Unknown")

                    if is_in_stock and previous_status != "In Stock":
                        print(f"  !!! STATUS CHANGE: {name} is now In Stock")
                        send_push_alert(name, link, title_override="In Stock Alert")
                    
                    # Update History
                    stock_history[name] = "In Stock" if is_in_stock else "Out of Stock"
                    
        except Exception as e:
            print(f"Error scanning {url}: {e}")

    # 2. Save history back to file
    save_history(stock_history)

if __name__ == "__main__":
    check_stock()
