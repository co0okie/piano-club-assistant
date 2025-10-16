import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import anthropic
import logging
from typing import Dict, List, Union, Optional
from openai import OpenAI
from openai.types.conversations import Conversation as OpenAIConversation
from rich import print

API = anthropic
# ANTHROPIC_MODEL = "claude-3-haiku-20240307"
# ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
# ANTHROPIC_MODEL = "claude-3-7-sonnet-20250219"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
# ANTHROPIC_MODEL = "claude-opus-4-20250514"
# ANTHROPIC_MODEL = "claude-opus-4-1-20250805"

# API = OpenAI
OPENAI_MODEL = "gpt-5-nano-2025-08-07"

SYSTEM_PROMPT = (
    "你是台科大鋼琴社的小助手，請幫助使用者完成各種鋼琴社相關事務，"
    "使用純文字回答，不要使用任何Markdown或者**粗體**格式。協助使用者報名活動時，對於每個資訊欄位，"
    "請逐項詢問，不要自行編造答案。"
)

HELP_TEXT = (
    "功能說明\n"
    "— 直接傳訊息開始聊天（保留最近20則上下文）\n"
    "— 指令：/clear 清除對話、/help 顯示說明\n"
    "— 範例：\n"
    "  搜尋近期活動\n"
    "  協助報名並逐項確認資訊\n"
)


conversation_history: Dict[str, Union[List[dict], OpenAIConversation]] = {}

# 移除舊的 MCP 連接器和狀態變數，改用官方 API設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
NGROK_DOMAIN = os.getenv('NGROK_DOMAIN', '')

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
    logger.info("LINE Bot API 初始化成功")
except Exception as e:
    logger.error(f"LINE Bot API 初始化失敗: {e}")
    raise

if API is anthropic:
    try:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("Claude (Anthropic) 初始化成功")
    except Exception as e:
        logger.error(f"Claude 初始化失敗: {e}")
        raise
elif API is OpenAI:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI 初始化成功")
    except Exception as e:
        logger.error(f"OpenAI 初始化失敗: {e}")
        raise
else:
    raise RuntimeError("API 常數必須是 anthropic 或 OpenAI")

# def call_openai_api(messages, user_id):
#     resp = openai_client.responses.create(
#         model=OPENAI_MODEL,
#         tools=[
#             {
#                 "type": "mcp",
#                 "server_label": "piano-club-assistant",
#                 "server_url": f"https://{NGROK_DOMAIN}/mcp",
#                 "require_approval": "never",
#             },
#         ],
#         input="Write something to console using the print_message tool.",
#         conversation=conversation_history.get(user_id, {}).id,
#     )

def get_claude_response_with_mcp(user_message, user_id):
    """使用 MCP 增強的 Claude 回應"""
    assert claude_client is not None

    if user_id not in conversation_history or not isinstance(conversation_history[user_id], list):
        conversation_history[user_id] = []
    
    messages: List[dict] = conversation_history[user_id]
    messages = messages[-20:]
    messages.append({"role": "user", "content": user_message})

    try:
        response = claude_client.beta.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1200,
            messages=messages,
            mcp_servers=[{
                "type": "url",
                "url": f"https://{NGROK_DOMAIN}/mcp",
                "name": "piano-club-assistant"
            }],
            system=SYSTEM_PROMPT,
            betas=["mcp-client-2025-04-04"]
        )
        assistant_response = "\n".join([
            content.text
            for content in response.content
            if hasattr(content, "text") and content.text
        ])
        if assistant_response == "":
            assistant_response = "<無回應>"
        logger.info(f"Claude 回應:")
        print(response)
        
        # 更新對話歷史
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })
        conversation_history[user_id] = messages
        
        return assistant_response
        
    except Exception as e:
        logger.error(f"Claude API 錯誤: {e}")
        return "Claude API 錯誤"

@app.route("/callback", methods=['POST'])
def callback():
    """LINE Bot webhook 回調函數"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logger.info("收到 LINE webhook 請求")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. 請檢查 channel access token/channel secret.")
        abort(400)
    except Exception as e:
        logger.error(f"處理 webhook 時發生錯誤: {e}")
        abort(500)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    user_message = event.message.text
    
    logger.info(f"收到用戶 {user_id} 的訊息: {user_message}")
    if user_id in conversation_history:
        print(conversation_history[user_id])
    
    try:
        # 特殊命令處理
        if user_message.lower() == '/clear':
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
        
        elif user_message.lower() in ['/help', '/功能', '幫助']:
            help_msg = """🤖 **Claude LINE Bot + MCP 功能說明**

💬 **對話功能**
• 直接傳送訊息開始聊天
• 支援上下文記憶（最近20則）

⚡ **指令列表**
• `/clear` - 清除對話歷史
• `/help` - 顯示此說明

🎯 **使用範例**
• "搜尋最新的 AI 新聞"
• "分析這個 GitHub 專案"

開始體驗 MCP 增強的 AI 助理吧！ 🚀"""
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=help_msg)
            )
            return
        
        # 一般對話 - 使用 MCP 增強
        claude_response = get_claude_response_with_mcp(user_message, user_id)
        
        # 檢查回應長度
        if len(claude_response) > 5000:
            claude_response = claude_response[:4900] + "\n\n📝 *（回應過長已截斷）*"
        
        # 回覆訊息
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=claude_response)
        )
        logger.info(f"成功回覆用戶 {user_id}")
        
    except Exception as e:
        logger.error(f"處理訊息時發生錯誤: {e}")
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="抱歉，系統發生錯誤，請稍後再試。 🔧")
            )
        except:
            logger.error("無法發送錯誤訊息給用戶")

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