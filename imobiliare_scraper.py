from bs4 import BeautifulSoup
import time
import json
import os
import random
import re
from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from utils import send_telegram, get_local_time, extract_mp, extract_metro, extract_specific_address

# --- CONFIGURATION ---
URL = "https://www.imobiliare.ro/vanzare-apartamente/bucuresti/sector-2?location=33985,33986&price=65000-130000&area=50&partitioning=detached&comfort=1,luxury&nearby=metro-station&feature=zero-commission"
CHAT_ID = "-5243464452"
DB_FILE = "seen_imobiliare.json"
TAG = "IMOBILIARE"

PROFILE_DIR = "/data/chrome-profile"
LIST_SELECTOR = "div[data-id]"
DETAIL_SELECTOR = "meta[property='og:image']"

class BlockedError(Exception):
    pass

def goto(page, url, selector, timeout=45000):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector(selector, timeout=timeout)
    except PlaywrightTimeoutError:
        body = page.content()
        if "captcha-delivery" in body or "var dd=" in body:
            raise BlockedError("DataDome")
        raise BlockedError("selector timeout")
    return page.content()

def scrape():
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                channel="chromium",
                headless=False,
                no_viewport=True,
                locale="ro-RO",
                timezone_id="Europe/Bucharest",
            )
            try:
                page = ctx.new_page()

                try:
                    html = goto(page, URL, LIST_SELECTOR)
                except BlockedError as e:
                    print(f"Eroare {TAG}: blocat de {e}")
                    return

                soup = BeautifulSoup(html, 'html.parser')

                # Cards have data-id
                cards = soup.find_all('div', attrs={'data-id': True})
                print(f"[{get_local_time()}] {TAG}: Găsit {len(cards)} carduri de anunțuri.")

                if not os.path.exists(DB_FILE):
                    with open(DB_FILE, 'w') as f:
                        json.dump([], f)

                with open(DB_FILE, 'r') as f:
                    seen_ids = set(json.load(f))

                new_count = 0
                for card in cards:
                    ad_id = card.get('data-id')
                    if not ad_id or ad_id in seen_ids:
                        continue

                    link_tag = card.find('a', attrs={'data-cy': 'listing-information-link'})
                    if not link_tag:
                        continue

                    link = link_tag.get('href')
                    if not link.startswith('http'):
                        link = "https://www.imobiliare.ro" + link

                    price_tag = card.find(attrs={'data-cy': 'card-price'})
                    price = "Vezi în anunț"
                    if price_tag:
                        # Clean up price (might have preț vechi, TVA, etc.)
                        price_text = price_tag.get_text(" ", strip=True)
                        # Regex to find the first price pattern like "123.456 €"
                        price_match = re.search(r'([0-9.]+)\s*€', price_text)
                        if price_match:
                            price = price_match.group(0)
                        else:
                            price = price_text.split('+')[0].strip()

                    # Find neighborhood
                    neighborhood = "București"
                    sec_tag = card.find(lambda tag: tag.name in ['p', 'span', 'div'] and 'Sector' in tag.text)
                    if sec_tag:
                        neighborhood = sec_tag.get_text(strip=True).split(',')[0].strip()

                    print(f"[{get_local_time()}] {TAG}: Procesare anunț nou: {ad_id}")
                    time.sleep(random.uniform(3.0, 6.0))

                    try:
                        detail_html = goto(page, link, DETAIL_SELECTOR)
                        ad_soup = BeautifulSoup(detail_html, 'html.parser')

                        # --- IMAGE EXTRACTION ---
                        image_tag = ad_soup.find('meta', property='og:image')
                        image_url = image_tag['content'] if image_tag else None

                        street_name = extract_specific_address(ad_soup)
                        sq_meters = extract_mp(ad_soup)
                        metro_station = extract_metro(ad_soup)

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

                    except Exception as e:
                        print(f"Eroare detaliu anunț {ad_id}: {e}")
                        continue

                with open(DB_FILE, 'w') as f:
                    json.dump(list(seen_ids), f)

                status_msg = f"<b>🔄 [{TAG}] SCANARE COMPLETĂ</b>\n" \
                             f"Scanat: {len(cards)} anunțuri\n" \
                             f"Noi: {new_count} de anunțuri"
                send_telegram(status_msg, CHAT_ID)

                print(f"[{get_local_time()}] {TAG}: Scanat {len(cards)} anunțuri. Găsite {new_count} noi.")
            finally:
                ctx.close()

    except Exception as e:
        print(f"Scrape error ({TAG}): {e}")

if __name__ == "__main__":
    while True:
        print(f"[{get_local_time()}] Începere scanare {TAG}...")
        scrape()
        sleep_time = random.randint(3300, 3900)
        print(f"[{get_local_time()}] Așteptare {sleep_time // 60} minute...")
        time.sleep(sleep_time)
