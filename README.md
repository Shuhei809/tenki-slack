# 天気×服装コーディネート Slack通知Bot

毎朝8時（JST）に、豊洲エリアの天気予報と服装コーディネート提案をSlackに自動送信するBot。

## セットアップ

### 1. TNQL API キーの取得

1. [RapidAPI](https://rapidapi.com/) でアカウント作成
2. [TNQL Coords Trial V2](https://rapidapi.com/legrand-legrand-default/api/tnql-coords-trial-v2) に登録（無料枠あり）
3. APIキーをコピー

### 2. Slack Incoming Webhook の作成

1. [Slack API](https://api.slack.com/apps) でアプリ作成
2. **Incoming Webhooks** を有効化
3. 通知先チャンネルを選択してWebhook URLを取得

### 3. GitHub Secrets の登録

リポジトリの **Settings → Secrets and variables → Actions** で以下を登録:

| Secret名 | 値 |
|---|---|
| `TNQL_API_KEY` | RapidAPIのAPIキー |
| `SLACK_WEBHOOK_URL` | Slack Webhook URL |

### 4. 動作確認

GitHub Actions の **Actions** タブから `Weather & Outfit Notification` を選択し、**Run workflow** で手動実行できる。

## ローカルで実行

```bash
export TNQL_API_KEY="your-api-key"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python notify.py
```

## カスタマイズ

- **地点の変更**: `notify.py` の `LATITUDE` / `LONGITUDE` を変更
- **送信時間の変更**: `.github/workflows/weather-notify.yml` の `cron` を変更（UTC指定）
