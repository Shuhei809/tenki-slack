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
TNQL_ENDPOINT = f"https://{TNQL_HOST}/v2/coords"
# 豊洲エリアの緯度経度
LATITUDE = "35.6496"
LONGITUDE = "139.7963"


def fetch_weather() -> dict:
    """TNQL APIから天気・コーデ情報を取得する"""
    url = f"{TNQL_ENDPOINT}?lat={LATITUDE}&lng={LONGITUDE}"
    req = urllib.request.Request(url, headers={
        "x-rapidapi-key": TNQL_API_KEY,
        "x-rapidapi-host": TNQL_HOST,
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def build_message(data: dict) -> str:
    """Slack送信用メッセージを組み立てる"""
    now = datetime.now(JST)
    date_str = now.strftime("%-m月%-d日") + f"（{'月火水木金土日'[now.weekday()]}）"

    # レスポンス構造に合わせて柔軟に取得
    weather = data.get("weather", data)
    temp = weather.get("temp", "—")
    feels_like = weather.get("feels_like", weather.get("apparent_temp", "—"))
    humidity = weather.get("humidity", "—")
    pop = weather.get("pop", weather.get("precipitation_probability", "—"))
    description = weather.get("description", weather.get("text", "—"))

    # 天気に合った絵文字
    desc_str = str(description)
    if "晴" in desc_str:
        weather_emoji = "☀️"
    elif "曇" in desc_str:
        weather_emoji = "☁️"
    elif "雨" in desc_str:
        weather_emoji = "🌧️"
    elif "雪" in desc_str:
        weather_emoji = "❄️"
    else:
        weather_emoji = "🌤️"

    # コーデ情報の取得
    coord = data.get("coordinates", data.get("coords", data.get("coordinate", {})))
    if isinstance(coord, list) and coord:
        coord = coord[0]
    coord_text = ""
    if isinstance(coord, dict):
        items = []
        for key in ("tops", "bottoms", "outer", "inner", "shoes", "accessory", "items"):
            val = coord.get(key)
            if val:
                items.append(str(val) if not isinstance(val, list) else "、".join(str(v) for v in val))
        coord_text = "\n".join(items) if items else json.dumps(coord, ensure_ascii=False, indent=2)
    elif isinstance(coord, str):
        coord_text = coord
    else:
        # coordsが取れない場合はdata全体からそれらしいキーを探す
        for key in ("suggestion", "advice", "outfit", "style"):
            if key in data:
                coord_text = str(data[key])
                break
        if not coord_text:
            coord_text = "コーデ情報を取得できませんでした"

    lines = [
        f"{weather_emoji} *今日の天気｜{date_str}*",
        "",
        f"🌡 気温: {temp}℃ / 体感 {feels_like}℃",
        f"💧 湿度: {humidity}%",
        f"🌂 降水確率: {pop}%",
        f"📝 天気: {description}",
        "",
        "👗 *今日のコーデ提案*",
        f"→ {coord_text}",
    ]
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
