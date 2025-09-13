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
    POSTGRES_DB=<db_name>
    POSTGRES_USER=<db_user>
    POSTGRES_PASSWORD=<db_password>
    ```

4. 啟動 (測試)

    ```bash
    docker compose -f infra/docker/compose.dev.yml up
    ```

5. 關閉

    ```bash
    docker compose -f infra/docker/compose.dev.yml down -v
    ```