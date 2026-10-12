import requests
from bs4 import BeautifulSoup
import time
import json
import os
import random
import re
from utils import send_telegram, get_local_time, extract_mp, extract_metro, extract_specific_address, get_headers

# --- CONFIGURATION ---
URL = "https://www.storia.ro/ro/rezultate/vanzare/apartament/locatii-multiple?limit=36&ownerTypeSingleSelect=ALL&priceMin=70000&priceMax=125000&areaMin=45&daysSinceCreated=7&locations=%5Bbucuresti%2Fsectorul-2%2Cbucuresti%2Fsectorul-3%5D&buildYearMin=1977&by=DEFAULT&direction=DESC"
CHAT_ID = "YOUR_CHAT_ID"
DB_FILE = "seen_storia.json"
TAG = "STORIA"

def scrape():
    headers = get_headers()
    try:
        response = requests.get(URL, headers=headers, timeout=20)
        print(f"[{get_local_time()}] {TAG}: Status {response.status_code}")
        
        if response.status_code != 200:
            print(f"Eroare {TAG} ({response.status_code}).")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Collect all unique ad links containing '/oferta/'
        all_links = soup.find_all('a', href=True)
        ad_links = []
        seen_ad_urls = set()
        
        for a in all_links:
            href = a['href']
            if '/oferta/' in href:
                if href.startswith('/'):
                    href = "https://www.storia.ro" + href
                if href not in seen_ad_urls:
                    ad_links.append(a)
                    seen_ad_urls.add(href)
        
        print(f"[{get_local_time()}] {TAG}: Găsit {len(ad_links)} link-uri de anunțuri unice.")

        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                seen_ids = set(json.load(f))
        else:
            seen_ids = set()

        new_count = 0
        for ad_link_tag in ad_links:
            link = ad_link_tag['href']
            if link.startswith('/'):
                link = "https://www.storia.ro" + link
                
            # Use the URL slug ID as ad_id
            ad_id = link.split('-')[-1]
            if not ad_id or ad_id in seen_ids:
                continue
                
            # Try to find price and location in parent container
            container = ad_link_tag.find_parent(attrs={'data-testid': 'ad-card'}) or ad_link_tag.parent.parent
            price_tag = container.find(attrs={'data-testid': 'ad-card-price'}) if container else None
            price = price_tag.text.strip() if price_tag else "Vezi în anunț"
            
            location_tag = container.find(attrs={'data-testid': 'ad-card-location'}) if container else None
            neighborhood = location_tag.text.strip().replace('Apartament de vânzare: ', '').replace('Garsonieră de vânzare: ', '') if location_tag else "București"
            
            # link is already defined above
            time.sleep(random.uniform(4.0, 8.0)) 
            
            ad_resp = requests.get(link, headers=headers)
            ad_soup = BeautifulSoup(ad_resp.text, 'html.parser')
            
            # --- IMPROVED PRICE EXTRACTION ---
            if price == "Vezi în anunț":
                # Try to find price in JSON data within the HTML
                price_match = re.search(r'"ad_price":\s*(\d+)', ad_resp.text)
                currency_match = re.search(r'"price_currency":"([^"]+)"', ad_resp.text)
                if price_match:
                    p_val = int(price_match.group(1))
                    p_curr = currency_match.group(1) if currency_match else "EUR"
                    # Format: 122 000 EUR
                    price = f"{p_val:,} {p_curr}".replace(',', ' ')
                else:
                    # Fallback to data-testid if regex fails (though regex is usually more stable in scripts)
                    price_tag_detail = ad_soup.find(attrs={'data-testid': 'ad-price-container'})
                    if price_tag_detail:
                        price = price_tag_detail.get_text(strip=True)
            
            # --- IMAGE EXTRACTION ---
            image_tag = ad_soup.find('meta', property='og:image')
            image_url = image_tag['content'] if image_tag else None
            
            street_name = extract_specific_address(ad_soup)
            sq_meters = extract_mp(ad_soup)
            metro_station = extract_metro(ad_soup)
                
            # neighborhood is already defined from the list card, 
            # but we can refine it with AI if it's just "București"
            
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
                     f"Scanat: {len(ad_links)} anunțuri\n" \
                     f"Noi: {new_count} de anunțuri"
        send_telegram(status_msg, CHAT_ID)
        
        print(f"[{get_local_time()}] {TAG}: Scanat {len(ad_links)} anunțuri. Găsite {new_count} noi.")

    except Exception as e:
        print(f"Scrape error ({TAG}): {e}")

if __name__ == "__main__":
    while True:
        print(f"[{get_local_time()}] Începere scanare {TAG}...")
        scrape()
        sleep_time = random.randint(3300, 3900)
        print(f"[{get_local_time()}] Așteptare {sleep_time // 60} minute...")
        time.sleep(sleep_time)
