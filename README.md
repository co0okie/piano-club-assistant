# Piano Club Assistant

## 開發環境設定

下載 Project

```bash
git clone https://github.com/co0okie/piano-club-assistant.git
cd piano-club-assistant
```

複製 Python 環境

```bash
uv sync
```

新增 `.env`，內容舉例:

```
POSTGRES_DB=<db_name>
POSTGRES_USER=<db_user>
POSTGRES_PASSWORD=<db_password>
```

啟動 (測試)

```bash
docker compose -f infra/docker/compose.dev.yml up
```

關閉

```bash
docker compose -f infra/docker/compose.dev.yml down
```