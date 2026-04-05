"""天気×服装コーディネート Slack通知Bot"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

TNQL_API_KEY = os.environ.get("TNQL_API_KEY", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# TNQL Coords Trial V2 (RapidAPI)
TNQL_HOST = "tnql-coords-trial-v2.p.rapidapi.com"
TNQL_ENDPOINT = f"https://{TNQL_HOST}/v2/api/coords_trial"
# 成田空港（東京エリア）
AIRPORT = "NRT"


def fetch_weather() -> dict:
    """TNQL APIから天気・コーデ情報を取得する"""
    url = f"{TNQL_ENDPOINT}?airport={AIRPORT}"
    req = urllib.request.Request(url, headers={
        "Content-Type": "application/json",
        "x-rapidapi-key": TNQL_API_KEY,
        "x-rapidapi-host": TNQL_HOST,
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def build_message(data: dict) -> str:
    """Slack送信用メッセージを組み立てる"""
    now = datetime.now(JST)
    date_str = now.strftime("%-m月%-d日") + f"（{'月火水木金土日'[now.weekday()]}）"

    results = data.get("results", {})

    # 朝(a)の最初のコーデから天気情報を取得
    morning = results.get("a", [{}])[0] if results.get("a") else {}
    weather_text = morning.get("description1", "—")
    condition_text = morning.get("description2", "—")

    # 天気に合った絵文字
    if "晴" in weather_text:
        weather_emoji = "☀️"
    elif "曇" in weather_text:
        weather_emoji = "☁️"
    elif "雨" in weather_text:
        weather_emoji = "🌧️"
    elif "雪" in weather_text:
        weather_emoji = "❄️"
    else:
        weather_emoji = "🌤️"

    lines = [
        f"{weather_emoji} *今日の天気｜{date_str}*",
        "",
        f"📝 {weather_text}",
        f"🌡 {condition_text}",
        "",
    ]

    # 時間帯ごとのコーデ提案（各1つずつ）
    time_labels = [("a", "🌅 朝"), ("b", "☀️ 昼"), ("c", "🌙 夜")]
    for key, label in time_labels:
        coords = results.get(key, [])
        if coords:
            coord = coords[0]
            lines.append(f"*{label}のコーデ*")
            lines.append(f"👗 {coord.get('description3', '—')}")
            image = coord.get("image", "")
            if image:
                lines.append(f"📷 {image}")
            lines.append("")

    return "\n".join(lines)


def send_slack(text: str) -> None:
    """Slack Incoming Webhookにメッセージを送信する"""
    payload = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Slack returned {resp.status}")


def send_error(err: str) -> None:
    """エラー発生時にSlackへ通知する"""
    if SLACK_WEBHOOK_URL:
        try:
            send_slack(f"⚠️ *天気Bot エラー*\n```\n{err}\n```")
        except Exception:
            pass


def main() -> None:
    if not TNQL_API_KEY:
        print("ERROR: TNQL_API_KEY is not set")
        sys.exit(1)
    if not SLACK_WEBHOOK_URL:
        print("ERROR: SLACK_WEBHOOK_URL is not set")
        sys.exit(1)

    try:
        data = fetch_weather()
        message = build_message(data)
        send_slack(message)
        print("通知送信完了 ✅")
    except Exception as e:
        print(f"ERROR: {e}")
        send_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
