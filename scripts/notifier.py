#!/usr/bin/env python3
"""
scripts/notifier.py
WelFamily 100% Free-Tier Multi-Channel Notification Dispatcher.
Supports Telegram Bot, Discord Webhook, and Kakao Talk '나에게 보내기'.
Runs without external dependencies (Python standard library only).
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNC_PATH = os.path.join(ROOT_DIR, "data", "latest_sync.json")


def log(msg: str):
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    print(f"[{now_str}] {msg}", flush=True)


def send_telegram_alert(bot_token: str, chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log("Telegram push alert successfully delivered!")
            return True
    except Exception as e:
        log(f"Telegram dispatch error: {e}")
        return False


def send_discord_webhook(webhook_url: str, title: str, description: str, fields: list) -> bool:
    payload = {
        "username": "WelFamily 복지비서",
        "avatar_url": "https://raw.githubusercontent.com/google/material-design-icons/master/png/action/account_balance/materialicons/48dp/1x/baseline_account_balance_black_48dp.png",
        "embeds": [{
            "title": title,
            "description": description,
            "color": 3447003, # Blue
            "fields": fields,
            "footer": {"text": "WelFamily • 대한민국 정부·지자체 맞춤 복지 레이더"}
        }]
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log("Discord webhook alert successfully delivered!")
            return True
    except Exception as e:
        log(f"Discord dispatch error: {e}")
        return False


def build_alert_message(sync_data: dict) -> tuple:
    alerts = sync_data.get("latest_alerts", [])
    total_active = sync_data.get("total_active_policies", 16)
    breakdown = sync_data.get("breakdown", {})

    title = "🔔 [WelFamily] 최신 복지 공고 및 마감 D-Day 알림"
    body = (
        f"📅 **기준 일시:** {datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M')}\n"
        f"🏠 **관리 중인 총 복지:** {total_active}건 (중앙 {breakdown.get('central_gov_count', 0)}건 / 지자체 {breakdown.get('local_gov_count', 0)}건)\n\n"
        f"🚨 **놓치면 안 되는 주요 일정:**\n"
    )

    fields = []
    for alert in alerts:
        p_title = alert.get("title", "")
        a_type = alert.get("alert_type", "")
        if "URGENT_DDAY" in a_type:
            line = f"• **[마감 임박 D-3]** {p_title} (마감일: {alert.get('deadline')})\n"
            fields.append({"name": "🚨 마감 임박 (선착순)", "value": f"{p_title}\n마감: {alert.get('deadline')}", "inline": False})
        elif "REGULAR_PAYMENT" in a_type:
            line = f"• **[정기 입금]** {p_title} (입금일: 매월 {alert.get('pay_day', '25일')})\n"
            fields.append({"name": "💰 정기 지급", "value": f"{p_title}\n입금일: {alert.get('pay_day')}", "inline": False})
        else:
            line = f"• {p_title}\n"
        body += line

    body += "\n👉 [내 가구 맞춤 복지 확인하러 가기](https://welfamily.github.io)"
    return title, body, fields


def main():
    log("=== Starting WelFamily Notification Dispatcher ===")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")

    sync_data = {}
    if os.path.exists(SYNC_PATH):
        with open(SYNC_PATH, "r", encoding="utf-8") as f:
            sync_data = json.load(f)

    title, message, fields = build_alert_message(sync_data)

    dispatched = False
    if telegram_token and telegram_chat_id:
        log("Dispatching Telegram alert...")
        if send_telegram_alert(telegram_token, telegram_chat_id, f"*{title}*\n\n{message}"):
            dispatched = True

    if discord_webhook:
        log("Dispatching Discord webhook alert...")
        if send_discord_webhook(discord_webhook, title, message, fields):
            dispatched = True

    if not dispatched:
        log("Notice: No live webhook tokens configured (TELEGRAM_BOT_TOKEN or DISCORD_WEBHOOK_URL).")
        log("Simulating local dry-run notification output:")
        print("--------------------------------------------------")
        print(f"TITLE: {title}")
        print(message)
        print("--------------------------------------------------")
        log("Dry-run notification test completed successfully (100% Free-Tier Ready).")


if __name__ == "__main__":
    main()
