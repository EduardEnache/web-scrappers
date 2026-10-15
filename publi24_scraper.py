import requests
from bs4 import BeautifulSoup
import time
import json
import os
import random
from utils import send_telegram, get_local_time, extract_mp, extract_metro, extract_specific_address, get_headers

# --- CONFIGURATION ---
URL = "https://www.publi24.ro/anunturi/imobiliare/de-vanzare/apartamente/bucuresti/?FromDate=639088966349430000&maxprice=125000&minprice=70000&livingspace=50-&yearofbuilding=1977-&resfeatures=decomandat&withpictures=true&commercial=false"
CHAT_ID = os.environ["PUBLI24_CHAT_ID"]  # set in .env (gitignored)
DB_FILE = "seen_publi24.json"
TAG = "PUBLI24"

def scrape():
    headers = get_headers()
    try:
        response = requests.get(URL, headers=headers, timeout=20)
        print(f"[{get_local_time()}] {TAG}: Status {response.status_code}")
        print(f"[{get_local_time()}] {TAG}: HTML Preview: {response.text[:500]}")
        
        if response.status_code != 200:
            print(f"Eroare {TAG} ({response.status_code}).")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        # On Publi24, ads have links containing '/anunt/'
        all_links = soup.find_all('a', href=True)
        print(f"[{get_local_time()}] {TAG}: Total links found on page: {len(all_links)}")
        
        ad_links = []
        seen_ad_urls = set()
        
        for a in all_links:
            href = a['href']
            # Match both relative and absolute links containing /anunt/
            if '/anunt/' in href and href not in seen_ad_urls:
                ad_links.append(a)
                seen_ad_urls.add(href)
        
        print(f"[{get_local_time()}] {TAG}: Găsit {len(ad_links)} link-uri de tip anunt.")

        # Filter out links that are just images or duplicates of the same ad
        # Usually each ad has multiple links (image, title). We just need one container per unique ad.
        listings = []
        seen_container_ids = set()
        for link in ad_links:
            parent = link.find_parent(['li', 'div', 'article'])
            if parent:
                # Use the link itself as a way to identify the unique listing container
                listing_id = link['href'].split('/')[-1]
                if listing_id not in seen_container_ids:
                    listings.append(parent)
                    seen_container_ids.add(listing_id)

        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                seen_ids = set(json.load(f))
        else:
            seen_ids = set()

        new_count = 0
        for ad in listings:
            if not ad: continue
            
            link_tag = ad.find('a', href=True)
            if not link_tag: continue
            
            link = link_tag['href']
            if link.startswith('/'):
                link = "https://www.publi24.ro" + link
            
            # Use the URL or part of it as ID
            ad_id = link.split('/')[-1].replace('.html', '')
            
            if not ad_id or ad_id in seen_ids:
                continue
                
            price_tag = ad.find('strong') or ad.find('span', class_=lambda x: x and 'price' in x)
            price = price_tag.text.strip() if price_tag else "Vezi în anunț"
            
            time.sleep(random.uniform(4.0, 8.0)) 
            
            ad_resp = requests.get(link, headers=headers)
            ad_soup = BeautifulSoup(ad_resp.text, 'html.parser')
            
            # --- IMPROVED PRICE EXTRACTION ---
            if price == "Vezi în anunț":
                price_tag_detail = ad_soup.find('span', class_='product-price')
                if price_tag_detail:
                    # Clean up price text (remove EUR/m2 part if present)
                    price_main = price_tag_detail.find('span')
                    if price_main:
                        price = price_main.get_text(strip=True) + " EUR"
                    else:
                        price = price_tag_detail.get_text(strip=True)
            
            # --- IMAGE EXTRACTION ---
            image_tag = ad_soup.find('meta', property='og:image')
            image_url = image_tag['content'] if image_tag else None
            
            street_name = extract_specific_address(ad_soup)
            sq_meters = extract_mp(ad_soup)
            metro_station = extract_metro(ad_soup)
            
            # Publi24 location is often in a specific span or in the title
            location_tag = ad.find('span', class_=lambda x: x and 'location' in x) or ad.find('p', class_='ad-location')
            neighborhood = location_tag.text.strip() if location_tag else "București"
            
            # --- AI FALLBACK REMOVED ---
            
            image_link = f'<a href="{image_url}">&#8205;</a>' if image_url else ""
            msg = (
                f"<b>🏢 [{TAG}] ANUNȚ NOU</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{image_link}"
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
    while True:
        # heartbeat for the compose healthcheck: a hung loop stops touching it
        open("/tmp/heartbeat", "w").close()
        print(f"[{get_local_time()}] Începere scanare {TAG}...")
        scrape()
        sleep_time = random.randint(3300, 3900)
        print(f"[{get_local_time()}] Așteptare {sleep_time // 60} minute...")
        time.sleep(sleep_time)
