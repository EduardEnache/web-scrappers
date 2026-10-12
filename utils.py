import requests
import random
import re
import json
import os
from datetime import datetime
import pytz

# --- SHARED CONFIG ---
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]  # set in .env (gitignored)

METRO_STATIONS = [
    "Piata Unirii", "Eroilor", "Universitate", "Piata Victoriei", "Gara de Nord", 
    "Basarab", "Obor", "Iancului", "Piata Muncii", "Dristor", "Nicolae Grigorescu", 
    "Titan", "Costin Georgian", "Republica", "Pantelimon", "Stefan cel Mare", 
    "Izvor", "Timpuri Noi", "Mihai Bravu", "Piperas", "Aurel Vlaicu", "Aviatorilor", 
    "Piata Romana", "Tineretului", "Eroii Revolutiei", "Constantin Brancoveanu", 
    "Piata Sudului", "Aparatorii Patriei", "Dimitrie Leonida", "Berceni", 
    "Preciziei", "Pacii", "Gorjului", "Lujerului", "Politehnica", 
    "1 Decembrie 1918", "Nicolae Teclu", "Anghel Saligny", "Straulesti", 
    "Laminorului", "Parc Bazilescu", "Jiului", "1 Mai", "Grivita", "Raul Doamnei",
    "Valea Ialomitei", "Romancierilor", "Constantin Brancusi", "Parc Drumul Taberei",
    "Tudor Vladimirescu", "Academia Militara", "Orizont", "Favorit"
]

def get_local_time():
    romania_tz = pytz.timezone('Europe/Bucharest')
    return datetime.now(romania_tz).strftime('%H:%M - %d/%m/%Y')

def send_telegram(message, chat_id):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.json().get("ok"):
            print(f"Eroare Telegram (API): {response.text}")
    except Exception as e:
        print(f"Eroare Telegram: {e}")

def extract_mp(soup):
    match = re.search(r'(\d+([\.,]\d+)?)\s*(mp|m2|m²|metri|utili)', soup.text, re.IGNORECASE)
    if match:
        return f"{match.group(1)} mp"
    return "Nemenționată"

def extract_metro(soup):
    text = soup.text.lower()
    for station in METRO_STATIONS:
        if station.lower() in text:
            return station
    return "Nespecificat"

def extract_specific_address(soup):
    pattern = r'((Strada|Str\.|Bulevardul|Bld\.|Soseaua|Sos\.|Calea|Intrarea|Prelungirea)\.?\s*[A-ZĂÎȘŢ][a-zăîșţ]+(\s*[A-ZĂÎȘŢ][a-zăîșţ]+)*)'
    match = re.search(pattern, soup.text)
    if match:
        return match.group(0)
    return "Nespecificată"

def get_headers(referer=None):
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    ]
    # NOTE: Do NOT set Accept-Encoding here — let requests handle decompression
    # automatically so response.text is always a decoded string, not binary.
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': '"Chromium";v="125", "Not.A/Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
    if referer:
        headers['Referer'] = referer
    return headers
