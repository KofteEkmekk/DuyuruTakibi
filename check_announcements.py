import json
import os
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://kapadokya.edu.tr/duyurular"
STATE_FILE = "seen.json"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DuyuruTakip/1.0)"}
LINK_RE = re.compile(r"/duyurular/[^/?#]+$")
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def fetch_announcements():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = {}
    for a in soup.find_all("a", href=LINK_RE):
        link = urljoin(URL, a["href"])
        if link in items:
            continue
        # Linkin bulundugu kutuyu bul: icinde sadece bu duyurunun linki olan en genis ust eleman
        box = a
        while box.parent and len(box.parent.find_all("a", href=LINK_RE)) == 1:
            box = box.parent
        lines = [t.strip() for t in box.get_text("\n").split("\n") if t.strip()]
        lines = [t for t in lines if t != "→"]
        date = next((t for t in lines if DATE_RE.match(t)), "")
        texts = [t for t in lines if not DATE_RE.match(t)]
        title = texts[0] if texts else link.rsplit("/", 1)[-1]
        items[link] = {"title": title, "date": date}
    return items  # sayfadaki sirayla (en yeni en ustte)


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )
    r.raise_for_status()


def main():
    items = fetch_announcements()
    if not items:
        print("Hic duyuru bulunamadi, sayfa yapisi degismis olabilir.")
        sys.exit(1)

    first_run = not os.path.exists(STATE_FILE)
    seen = []
    if not first_run:
        with open(STATE_FILE, encoding="utf-8") as f:
            seen = json.load(f)

    if first_run:
        send("✅ Kapadokya Üniversitesi duyuru takibi başladı. Yeni duyurular buraya gelecek.")
        new_links = []
    else:
        new_links = [l for l in items if l not in seen]

    # eskiden yeniye gonder
    for link in reversed(new_links):
        it = items[link]
        send(f"📢 Yeni duyuru\n\n{it['title']}\n{it['date']}\n\n{link}")
        print("Gonderildi:", it["title"])

    updated = seen + [l for l in reversed(list(items)) if l not in seen]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(updated[-500:], f, ensure_ascii=False, indent=2)

    print(f"Kontrol tamam. Yeni duyuru: {len(new_links)}")


if __name__ == "__main__":
    main()
