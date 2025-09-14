import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import anthropic
import logging

# 儲存對話歷史
conversation_history = {}

# 移除舊的 MCP 連接器和狀態變數，改用官方 API設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# API 金鑰設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
NGROK_DOMAIN = os.getenv('NGROK_DOMAIN', '')

# 驗證設定
logger.info(f"✅ LINE Token 長度: {len(LINE_CHANNEL_ACCESS_TOKEN)}")
logger.info(f"✅ LINE Secret 長度: {len(LINE_CHANNEL_SECRET)}")  
logger.info(f"✅ Claude API Key 長度: {len(ANTHROPIC_API_KEY)}")

# 初始化 LINE Bot API
try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
    logger.info("✅ LINE Bot API 初始化成功")
except Exception as e:
    logger.error(f"❌ LINE Bot API 初始化失敗: {e}")
    exit(1)

# 初始化 Claude API
try:
    claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info("✅ Claude API 初始化成功")
except Exception as e:
    logger.error(f"❌ Claude API 初始化失敗: {e}")
    exit(1)

def get_claude_response_with_mcp(user_message, user_id):
    """使用 MCP 增強的 Claude 回應"""
    try:
        # 取得用戶對話歷史
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        messages = conversation_history[user_id][-20:]
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        logger.info(f"發送給 Claude (MCP增強): {user_message[:50]}...")
        
        # 呼叫 Claude API
        response = claude_client.beta.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1200,
            temperature=0.7,
            messages=messages,
            mcp_servers=[{
                "type": "url",
                "url": f"https://{NGROK_DOMAIN}/mcp",
                "name": "piano-club-assistant"
            }],
            system="你是一個友善的AI助理，會用繁體中文回應用戶。請保持對話自然、有幫助且簡潔。",
            betas=["mcp-client-2025-04-04"]
        )
        
        assistant_response = response.content[-1].text or "<無回應>"
        logger.info(f"Claude (MCP) 回應: {assistant_response[:100]}...")
        
        # 更新對話歷史
        messages.append({
            "role": "assistant", 
            "content": assistant_response
        })
        conversation_history[user_id] = messages
        
        return assistant_response
        
    except Exception as e:
        logger.error(f"Claude MCP API 錯誤: {e}")
        return "抱歉，我現在無法回應您的訊息。請稍後再試。 🔧"

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
    
    try:
        # 特殊命令處理
        if user_message.lower() in ['/clear', '/reset', '清除對話']:
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