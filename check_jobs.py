#!/usr/bin/env python3
import os, json, re, hashlib, time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

COMPANIES_FILE = "companies.json"
SEEN_FILE = "seen.json"
USER_AGENT = "Mozilla/5.0 (compatible; JobWatcher/1.0; +https://github.com/yourrepo)"

KEYWORDS = [
    r"\bSDE\b", r"Software Engineer Intern", r"Software Engineering Intern",
    r"SDE Intern", r"Summer 2026", r"Summer\\s*2026", r"2026 Summer", r"Intern - Software",
    r"Software Intern", r"Engineering Intern"
]

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_page(url):
    try:
        headers = {"User-Agent": USER_AGENT}
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"[!] Error fetching {url}: {e}")
        return ""

def extract_jobs_from_html(company_name, url, html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    candidates = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 10:
            continue
        for kw in KEYWORDS:
            if re.search(kw, line, flags=re.I):
                id_src = company_name + "|" + line
                job_id = hashlib.sha256(id_src.encode("utf-8")).hexdigest()
                candidates.append({
                    "company": company_name,
                    "url": url,
                    "snippet": line,
                    "id": job_id
                })
                break
    return candidates

def send_email(subject, body_text):
    if not SENDGRID_API_KEY or not RECIPIENT_EMAIL or not SENDER_EMAIL:
        print("[!] Missing email config. Set SENDGRID_API_KEY, SENDER_EMAIL, RECIPIENT_EMAIL.")
        return False
    data = {
      "personalizations": [{"to": [{"email": RECIPIENT_EMAIL}]}],
      "from": {"email": SENDER_EMAIL},
      "subject": subject,
      "content": [{"type": "text/plain", "value": body_text}]
    }
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, json=data, timeout=20)
    if resp.status_code in (200, 202):
        print("[+] Email sent")
        return True
    else:
        print("[!] SendGrid failed:", resp.status_code, resp.text)
        return False

def main():
    companies = load_json(COMPANIES_FILE, [])
    seen = load_json(SEEN_FILE, [])
    seen_set = set(seen)
    new_jobs = []

    for c in companies:
        name = c.get("name")
        url = c.get("url")
        if not name or not url:
            continue
        print(f"[i] Checking {name} -> {url}")
        html = get_page(url)
        if not html:
            continue
        candidates = extract_jobs_from_html(name, url, html)
        for job in candidates:
            if job["id"] not in seen_set:
                new_jobs.append(job)
                seen_set.add(job["id"])
        time.sleep(2)

    if not new_jobs:
        print("[i] No new jobs found.")
        save_json(SEEN_FILE, list(seen_set))
        return

    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    subject = f"New SDE intern openings — {len(new_jobs)} new — {date_str}"
    body_lines = []
    for j in new_jobs:
        body_lines.append(f"Company: {j['company']}")
        body_lines.append(f"URL: {j['url']}")
        body_lines.append(f"Snippet: {j['snippet']}")
        body_lines.append("-" * 60)
    body_text = "\n".join(body_lines)
    print("[i] Sending email with", len(new_jobs), "items")
    ok = send_email(subject, body_text)
    if ok:
        save_json(SEEN_FILE, list(seen_set))

if __name__ == "__main__":
    main()
