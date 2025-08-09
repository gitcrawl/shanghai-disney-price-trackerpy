import requests, re, datetime, pytz, os, csv
import smtplib, ssl

def send_email_alert(subject, body):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    to_email   = os.getenv("TO_EMAIL")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    if not all([smtp_server, smtp_user, smtp_pass, to_email]):
        print("Email not sent: SMTP env vars missing.")
        return

    msg = f"From: {from_email}\r\nTo: {to_email}\r\nSubject: {subject}\r\n\r\n{body}"
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.encode("utf-8"))

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                  ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
    'Referer': 'https://www.google.com/'
}
URL = "https://www.klook.com/activity/2128-disney-resort-shang-hai/"
CSV_PATH = "data/shanghai_disneyland_prices.csv"

def get_prices():
    html = requests.get(URL, headers=HEADERS, timeout=30).text
    match_usd = re.search(r'"offers"\s*:\s*\{[^{}]*?"price"\s*:\s*([0-9]+\.?[0-9]*)', html, re.DOTALL)
    match_cny = re.search(r'"ActPrice":"(\d+\.?\d*)"', html)
    if not match_cny and not match_usd:
        raise RuntimeError("Couldn’t find price fields in page HTML.")
    price_usd = float(match_usd.group(1)) if match_usd else None
    price_cny = float(match_cny.group(1)) if match_cny else None

    # If USD is missing, derive from CNY with a conservative rate (update if you like)
    if price_usd is None and price_cny is not None:
        usd_per_cny = 0.14
        price_usd = price_cny * usd_per_cny

    # AUD from USD (update periodically or switch to a live API if you want)
    aud_per_usd = 1.54
    price_aud = price_usd * aud_per_usd if price_usd is not None else None

    return price_usd, price_cny, price_aud

def record_price(csv_path):
    price_usd, price_cny, price_aud = get_prices()
    mel_tz = pytz.timezone('Australia/Melbourne')
    date_str = datetime.datetime.now(mel_tz).strftime('%Y-%m-%d')

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    new_file = not os.path.exists(csv_path)

    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(['Date', 'Price_USD', 'Price_CNY', 'Price_AUD'])
        w.writerow([date_str, price_usd, price_cny, price_aud])

# Alert if USD below threshold
THRESHOLD_USD = 55.0
if price_usd is not None and price_usd < THRESHOLD_USD:
    subject = f"[ALERT] Shanghai Disney price dropped: ${price_usd:.2f} USD"
    body = (
        f"Date: {date_str}\n"
        f"USD: ${price_usd:.2f}\nCNY: ¥{price_cny:.2f}\nAUD: ${price_aud:.2f}\n\n"
        f"URL: {URL}"
    )
    send_email_alert(subject, body)

if __name__ == "__main__":
    record_price(CSV_PATH)
