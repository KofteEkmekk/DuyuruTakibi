import json
import os
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://kapadokya.edu.tr/duyurular?page=1"
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


def load_state():
    """seen.json: {link: tarih}. Eski format (sadece link listesi) otomatik donusturulur."""
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {link: None for link in data}  # tarih bilinmiyor
    return data


def save_state(state):
    # en fazla 500 kayit tut (sozluk ekleme sirasini korur)
    keys = list(state)[-500:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({k: state[k] for k in keys}, f, ensure_ascii=False, indent=2)


def main():
    items = fetch_announcements()
    if not items:
        print("Hic duyuru bulunamadi, sayfa yapisi degismis olabilir.")
        sys.exit(1)

    state = load_state()
    first_run = state is None

    if first_run:
        send("✅ Kapadokya Üniversitesi duyuru takibi başladı. Yeni duyurular buraya gelecek.")
        state = {}

    notifications = []  # (tur, link)
    # eskiden yeniye dogru isle
    for link in reversed(list(items)):
        date = items[link]["date"]
        if link not in state:
            if not first_run:
                notifications.append(("new", link))
            state[link] = date
        else:
            old = state[link]
            if old is None:
                state[link] = date  # eski formattan gecis, bildirme
            elif date and old != date:
                notifications.append(("updated", link))
                state[link] = date

    for kind, link in notifications:
        it = items[link]
        head = "📢 Yeni duyuru" if kind == "new" else "🔄 Güncellenen duyuru"
        send(f"{head}\n\n{it['title']}\n{it['date']}\n\n{link}")
        print("Gonderildi:", kind, it["title"])

    save_state(state)
    print(f"Kontrol tamam. Bildirim: {len(notifications)}")


if __name__ == "__main__":
    main()
    
