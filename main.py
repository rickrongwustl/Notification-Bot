import requests
from bs4 import BeautifulSoup
import time

# --- CONFIGURATION ---
URLS = [
    "https://www.predatorcues.com/usa/pool-cues/break-jump-cues/bk-rush-break-cues.html",
    "https://www.predatorcues.com/usa/pool-cues/lines/p3-pool-cues.html",
    "https://www.predatorcues.com/usa/new/new/new-arrivals.html"
]

TOPIC_NAME = "bkrush_ric" 
CHECK_INTERVAL = 300 

# --- STATE TRACKING ---
stock_history = {}

def send_push_alert(product_name, link, title_override=None):
    """Sends a push notification via ntfy.sh"""
    try:
        # FIXED: Removed emojis from title to prevent crashes
        title = title_override if title_override else "Predator Stock Update"
        
        requests.post(f"https://ntfy.sh/{TOPIC_NAME}", 
            data=f"ITEM: {product_name}",
            headers={
                "Title": title,
                "Click": link,
                "Priority": "high",
                # ntfy converts these text tags to emojis automatically
                "Tags": "rotating_light,white_check_mark,buy" 
            }
        )
        print(f"-> ALERT SENT for {product_name}")
    except Exception as e:
        print(f"Error sending alert: {e}")

def check_page(url):
    print(f"Scanning: {url} ...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")
        products = soup.select("li.product-item")
        
        if not products:
            print("  Warning: No products found on this page.")
            return

        for product in products:
            # 1. Get Details safely
            name_el = product.select_one(".product-item-link")
            if not name_el:
                continue
                
            name = name_el.text.strip()
            # FIXED: Use .get() to avoid KeyError if href is missing
            link = name_el.get('href', url) 
            
            stock_el = product.select_one(".amstockstatus")
            status_text = stock_el.text.strip() if stock_el else "Unknown"
            
            # --- LOGIC SPLIT BASED ON PAGE ---
            
            # RULE 1: If we are on "New Arrivals" page...
            if "new-arrivals" in url:
                # ...Strictly IGNORE everything that is NOT "LE True Splice 16"
                if "LE True Splice 16" not in name:
                    continue # Skip to next product
                
                # If we found it, force an alert immediately (even if we've seen it)
                # because this is a rare item.
                print(f"  !!! SPECIAL FIND: {name}")
                send_push_alert(name, link, title_override="NEW LISTING DETECTED")
                continue # Done with this item

            # RULE 2: Standard Logic for other pages (BK Rush, P3)
            else:
                # Filter: Ignore Black BK Rush
                if "BK Rush" in name and "Black" in name:
                    stock_history[name] = status_text
                    continue

                # Check for Status Change
                is_in_stock = "In Stock" in status_text
                previous_status = stock_history.get(name, "Unknown")

                if is_in_stock:
                    if previous_status != "In Stock":
                        print(f"  !!! STATUS CHANGE: {name} is now In Stock")
                        send_push_alert(name, link, title_override="In Stock Alert")
                
                # Update history
                stock_history[name] = "In Stock" if is_in_stock else "Out of Stock"

    except Exception as e:
        print(f"  Error fetching page: {e}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    print("Bot started...")
    
    while True:
        for url in URLS:
            check_page(url)
            time.sleep(2) 
            
        print(f"Cycle complete. Sleeping for {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)