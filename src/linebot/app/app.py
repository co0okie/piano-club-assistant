import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import anthropic
from anthropic.types.beta import BetaMessageParam, BetaContentBlock, BetaRequestMCPServerURLDefinitionParam
import logging
from openai import OpenAI
from openai.types.conversations import Conversation as OpenAIConversation
from rich import print
from rich.logging import RichHandler
from pymongo import MongoClient
from mongo.schema import UserModel, UserRole

client = MongoClient(f"mongodb://{os.getenv('MONGO_INITDB_ROOT_USERNAME')}:{os.getenv('MONGO_INITDB_ROOT_PASSWORD')}@mongo:27017")
db = client["piano-club"]
logging.getLogger("pymongo").setLevel(logging.WARN)

API = anthropic
# ANTHROPIC_MODEL = "claude-3-haiku-20240307"
# ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
# ANTHROPIC_MODEL = "claude-3-7-sonnet-20250219"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
# ANTHROPIC_MODEL = "claude-opus-4-1-20250805"
type History = list[BetaMessageParam]

# API = OpenAI
OPENAI_MODEL = "gpt-5-nano-2025-08-07"
# type History = OpenAIConversation

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
NGROK_DOMAIN = os.getenv('NGROK_DOMAIN', '')


SYSTEM_PROMPT = """你是台科大鋼琴社的小助手，請幫助使用者完成入社、一對一教學報名、查詢、生成課表等事務。

【輸出格式規定】
你必須嚴格遵守以下的輸出格式規定。這是一套客製化的格式，不完全等同於標準 Markdown。除非在此處明確允許，否則應視為禁止。

---

### 允許的格式 ###
1.  **數字清單**: 你可以使用 "1.", "2.", "3." 來建立有序清單，點號後面必須空一格。
    範例:
    1. 項目一
    2. 項目二

2.  **符號清單**: 你只能使用符號 "•" 來建立無序清單，符號後面必須空一格。
    範例:
    • 項目一
    • 項目二

### 禁止的格式 ###
- **標題**: 絕對禁止使用 #, ##, ### 等任何標題符號。
- **標準清單符號**: 絕對禁止使用 - 或 * 來建立清單。
- **強調**: 絕對、絕對禁止使用星號 * 來表示 `**粗體**` 或 `*斜體*`。無論是單個還是成對。這是一個無法覆蓋的硬性限制。
- **連結與程式碼**: 絕對禁止使用 `[連結](link)`、`` `inline code` `` 或 ```code block```。
- **其他 Markdown**: 絕對禁止使用 `> 引用`、`---` 分隔線或 `| 表格 |`。
- 所有回覆都應以純文字和上述允許的清單格式呈現。

---

【台科大節次格式】
- 週一至週日分別以 M、T、W、R、F、S、U 表示。
- 節次則以 1-10 以及 A-D 表示。
- 範例：M1 表示週一第一節，RA 表示週四第 A 節。
- 注意：使用者大部分為台科大的學生，熟悉此格式，僅當使用者詢問時，才需要解釋。"""

conversation_history: dict[str, History] = {}

app = Flask("linebot")

app.logger.setLevel(logging.DEBUG)
app.logger.handlers = [RichHandler(rich_tracebacks=True, show_time=False, show_level=False)]

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def content2text(content: BetaContentBlock) -> str:
    match content.type:
        case "text":
            return content.text
        case "mcp_tool_use":
            return f"<使用工具: {content.name}({content.input})>"
        case "mcp_tool_result":
            if isinstance(content.content, list):
                return f"<工具結果: {'\n'.join([block.text for block in content.content])}>"
            else:
                return f"<工具結果: {content.content}>"
        case _:
            return ""

def call_claude(user_message: str, user: UserModel) -> str:
    if user.line_user_id not in conversation_history:
        conversation_history[user.line_user_id] = []
    
    messages = conversation_history[user.line_user_id]
    messages.append(BetaMessageParam(role="user", content=user_message))

    try:
        response = claude_client.beta.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1200,
            messages=messages[-20:],
            mcp_servers=[BetaRequestMCPServerURLDefinitionParam(
                type="url",
                name="piano-club",
                url=f"https://{NGROK_DOMAIN}/mcp",
                authorization_token=user.line_user_id
            )],
            system=SYSTEM_PROMPT,
            betas=["mcp-client-2025-04-04"]
        )
    except Exception as e:
        app.logger.error(f"Claude API 錯誤: {e}")
        return "Claude API 錯誤"
    
    app.logger.debug(f"{response}")

    assistant_response = "\n".join([
        text
        for text in [content2text(content) for content in response.content]
        if text != ""
    ])
    if assistant_response == "":
        assistant_response = "<無回應>"
    
    # 更新對話歷史
    messages.append(BetaMessageParam(role=response.role, content=response.content))
    
    return assistant_response

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("收到 LINE webhook 請求")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. 請檢查 channel access token/channel secret.")
        abort(400)
    except Exception as e:
        app.logger.error(f"處理 webhook 時發生錯誤: {e}")
        abort(500)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    
    app.logger.info(f"收到用戶 {user_id} 的訊息: {user_message}")

    # 取得用戶基本資訊
    doc = db.users.find_one({"line_user_id": user_id}, {"_id": 0})
    if doc is None:
        app.logger.info(f"新增用戶 {user_id} 到資料庫")
        user = UserModel(line_user_id=user_id)
        db.users.insert_one(user.model_dump(mode="json"))
    else:
        user = UserModel.model_validate(doc)
    
    try:
        # 特殊命令處理
        if user_message == '/clear':
            if user_id in conversation_history:
                del conversation_history[user_id]
                response_msg = "✅ 對話歷史已清除！"
            else:
                response_msg = "📝 您還沒有對話歷史。"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response_msg)
            )
            return
        
        # 一般對話
        claude_response = call_claude(user_message, user)
        
        if len(claude_response) > 5000:
            claude_response = claude_response[:4900] + "\n\n📝 *（回應過長已截斷）*"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=claude_response)
        )
        app.logger.info(f"成功回覆用戶 {user_id}")
        
    except Exception as e:
        app.logger.error(f"處理訊息時發生錯誤: {e}")
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="抱歉，系統發生錯誤，請稍後再試。 🔧")
            )
        except:
            app.logger.error("無法發送錯誤訊息給用戶")

@app.route("/health", methods=['GET'])
def health_check():
    """健康檢查端點"""
    return {
        "status": "healthy",
        "message": "LINE Bot + Claude + MCP is running",
        "active_conversations": len(conversation_history),
    }, 200

@app.route("/", methods=['GET'])
def home():
    """首頁"""
    return f"""🤖 LINE Bot + Claude API + MCP 聊天機器人運行中！

💬 活躍對話: {len(conversation_history)} 個

使用 /health 查看詳細狀態"""