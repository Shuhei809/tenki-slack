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
# 羽田空港（江東区最寄り）
AIRPORT = "HND"

# Open-Meteo API（気温データ用・江東区）
LATITUDE = "35.6726"
LONGITUDE = "139.8171"
OPEN_METEO_URL = (
    f"https://api.open-meteo.com/v1/jma"
    f"?latitude={LATITUDE}&longitude={LONGITUDE}"
    f"&hourly=temperature_2m,precipitation_probability&past_days=1&timezone=Asia%2FTokyo"
)

# 気温を取得する時刻（JST）
TEMP_HOURS = [6, 12, 19]


def fetch_coords() -> dict:
    """TNQL APIからコーデ情報を取得する"""
    url = f"{TNQL_ENDPOINT}?airport={AIRPORT}"
    req = urllib.request.Request(url, headers={
        "Content-Type": "application/json",
        "x-rapidapi-key": TNQL_API_KEY,
        "x-rapidapi-host": TNQL_HOST,
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_weather_data() -> dict:
    """Open-Meteo APIから今日・昨日の気温・降水確率を取得する"""
    req = urllib.request.Request(OPEN_METEO_URL)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    hourly = data["hourly"]
    times = hourly["time"]           # "2026-04-04T00:00", ...
    temps = hourly["temperature_2m"]
    precip = hourly.get("precipitation_probability", [None] * len(times))

    now = datetime.now(JST)
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    result = {"today": {}, "yesterday": {}}
    for t, temp, pop in zip(times, temps, precip):
        date_part, time_part = t.split("T")
        hour = int(time_part.split(":")[0])
        if hour in TEMP_HOURS:
            entry = {"temp": temp, "pop": pop}
            if date_part == today_str:
                result["today"][hour] = entry
            elif date_part == yesterday_str:
                result["yesterday"][hour] = entry

    return result


def format_diff(today_temp, yesterday_temp) -> str:
    """昨日との気温差を文字列にする"""
    if today_temp is None or yesterday_temp is None:
        return ""
    diff = today_temp - yesterday_temp
    if diff > 0:
        return f"(昨日比 +{diff:.1f}℃)"
    elif diff < 0:
        return f"(昨日比 {diff:.1f}℃)"
    return "(昨日と同じ)"


def build_message(coord_data: dict, temp_data: dict) -> str:
    """Slack送信用メッセージを組み立てる"""
    now = datetime.now(JST)
    date_str = now.strftime("%-m月%-d日") + f"（{'月火水木金土日'[now.weekday()]}）"

    results = coord_data.get("results", {})

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
        f"{weather_emoji} *今日の天気｜{date_str}　江東区*",
        "",
        f"📝 {weather_text}",
        f"🌡 {condition_text}",
        "",
    ]

    # 気温・降水確率（朝6時・昼12時・夜19時 + 昨日比）
    today = temp_data.get("today", {})
    yesterday = temp_data.get("yesterday", {})
    temp_labels = [(6, "🌅  6時"), (12, "☀️ 12時"), (19, "🌙 19時")]

    lines.append("*🌡 気温・降水確率（江東区）*")
    for hour, label in temp_labels:
        td = today.get(hour, {})
        yd = yesterday.get(hour, {})
        t = td.get("temp") if isinstance(td, dict) else None
        pop = td.get("pop") if isinstance(td, dict) else None
        y = yd.get("temp") if isinstance(yd, dict) else None
        if t is not None:
            diff_str = format_diff(t, y)
            pop_str = f"☂ {pop}%" if pop is not None else ""
            lines.append(f"　{label}:  {t:.1f}℃ {diff_str}　{pop_str}")
        else:
            lines.append(f"　{label}:  —")
    lines.append("")

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
        coord_data = fetch_coords()
        temp_data = fetch_weather_data()
        message = build_message(coord_data, temp_data)
        send_slack(message)
        print("通知送信完了 ✅")
    except Exception as e:
        print(f"ERROR: {e}")
        send_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
