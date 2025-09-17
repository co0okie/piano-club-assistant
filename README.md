# Piano Club Assistant

## 開發環境設定

1. 安裝 [Docker](https://docs.docker.com/engine/install/)

2. Clone

    ```bash
    git clone https://github.com/co0okie/piano-club-assistant.git
    cd piano-club-assistant
    ```

3. 新增 `.env`，內容舉例:

    ```
    MONGO_INITDB_ROOT_USERNAME=piano
    MONGO_INITDB_ROOT_PASSWORD=piano
    ANTHROPIC_API_KEY=
    LINE_CHANNEL_ACCESS_TOKEN=
    LINE_CHANNEL_SECRET=
    NGROK_AUTHTOKEN=
    NGROK_DOMAIN=
    ```

4. 啟動 (測試)

    ```bash
    docker compose -f infra/docker/compose.dev.yml up
    ```

5. 關閉

    ```bash
    docker compose -f infra/docker/compose.dev.yml down -v
    ```

## 常用指令

- MCP Inspector

    ```bash
    npx @modelcontextprotocol/inspector
    ```