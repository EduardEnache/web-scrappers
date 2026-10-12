import requests
import cloudscraper
from bs4 import BeautifulSoup
import time
import json
import os
import random
from utils import send_telegram, get_local_time, extract_mp, extract_metro, extract_specific_address, get_headers

# --- CONFIGURATION ---
URL = "https://www.olx.ro/imobiliare/apartamente-garsoniere-de-vanzare/bucuresti-ilfov-judet/?currency=EUR&search%5Bfilter_float_price:from%5D=70000&search%5Bfilter_float_price:to%5D=130000&search%5Bfilter_enum_compartimentare%5D%5B0%5D=decomandat&search%5Bfilter_float_m:from%5D=50&search%5Bfilter_enum_constructie%5D%5B0%5D=1977-1990&search%5Bfilter_enum_constructie%5D%5B1%5D=1990-2000&search%5Bfilter_enum_constructie%5D%5B2%5D=dupa-2000"
CHAT_ID = "YOUR_CHAT_ID"
DB_FILE = "seen_olx.json"
TAG = "OLX"

def scrape():
    headers = get_headers()
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(URL, headers=headers, timeout=20)
        if response.status_code == 403:
            print(f"Eroare {TAG} (403) - posibil blocat. Reîncercare cu alt User-Agent...")
            headers = get_headers(referer="https://www.olx.ro/")
            response = scraper.get(URL, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"Eroare {TAG} ({response.status_code}).")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        listings = soup.find_all('div', {'data-cy': 'l-card'})

        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                seen_ids = set(json.load(f))
        else:
            seen_ids = set()

        new_count = 0
        for ad in listings:
            ad_id = ad.get('id')
            if not ad_id or ad_id in seen_ids:
                continue
                
            price_tag = ad.find('p', {'data-testid': 'ad-price'}) or ad.find('h6')
            price = price_tag.text.strip() if price_tag else "Vezi în anunț"
            
            link_tag = ad.find('a', href=True)
            if link_tag:
                link = link_tag['href']
                if link.startswith('/'):
                    link = "https://www.olx.ro" + link
                
                time.sleep(random.uniform(4.0, 8.0)) 
                
                detail_headers = get_headers(referer=URL)
                ad_resp = scraper.get(link, headers=detail_headers)
                ad_soup = BeautifulSoup(ad_resp.text, 'html.parser')
                street_name = extract_specific_address(ad_soup)
                sq_meters = extract_mp(ad_soup)
                metro_station = extract_metro(ad_soup)
                
                location_tag = ad.find('p', {'data-testid': 'location-date'})
                neighborhood = location_tag.text.split(' - ')[0] if location_tag else "București"
                
                # --- AI FALLBACK REMOVED ---
                
                msg = (
                    f"<b>🏢 [{TAG}] ANUNȚ NOU</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💰 <b>Preț:</b> {price}\n"
                    f"📐 <b>Suprafață:</b> {sq_meters}\n"
                    f"📍 <b>Zonă:</b> {neighborhood}\n"
                    f"🚇 <b>Metrou:</b> {metro_station}\n"
                    f"🛣️ <b>Stradă:</b> {street_name}\n"
                    f"🕒 <b>Ora:</b> {get_local_time()}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔗 <a href='{link}'>Vezi detalii pe site</a>"
                )
                
                send_telegram(msg, CHAT_ID)
                seen_ids.add(ad_id)
                new_count += 1

        with open(DB_FILE, 'w') as f:
            json.dump(list(seen_ids), f)
        
        status_msg = f"<b>🔄 [{TAG}] SCANARE COMPLETĂ</b>\n" \
                     f"Scanat: {len(listings)} anunțuri\n" \
                     f"Noi: {new_count} de anunțuri"
        send_telegram(status_msg, CHAT_ID)
        
        print(f"[{get_local_time()}] {TAG}: Scanat {len(listings)} anunțuri. Găsite {new_count} noi.")

    except Exception as e:
        print(f"Scrape error ({TAG}): {e}")

if __name__ == "__main__":
    if os.path.exists("seen_ads.json") and not os.path.exists(DB_FILE):
        os.rename("seen_ads.json", DB_FILE)

    while True:
        # heartbeat for the compose healthcheck: a hung loop stops touching it
        open("/tmp/heartbeat", "w").close()
        print(f"[{get_local_time()}] Începere scanare {TAG}...")
        scrape()
        sleep_time = random.randint(3300, 3900)
        print(f"[{get_local_time()}] Așteptare {sleep_time // 60} minute...")
        time.sleep(sleep_time)
