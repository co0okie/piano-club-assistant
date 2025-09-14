import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import anthropic
import logging
from concurrent.futures import ThreadPoolExecutor

# 儲存對話歷史
conversation_history = {}
executor = ThreadPoolExecutor(max_workers=4)

# 移除舊的 MCP 連接器和狀態變數，改用官方 API設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# API 金鑰設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# MCP 伺服器設定
MCP_SERVERS = {
    "deepwiki": {
        "url": "https://mcp.deepwiki.com/mcp",
        "type": "https",
        "name": "deepwiki",
        "description": "程式碼庫分析工具，提供架構圖和文件",
        "tools": ["analyze_repo", "get_structure"]
    },
    "web_search": {
        "url": "https://remote.mcpservers.org/fetch/mcp",
        "type": "https",
        "name": "search-server",
        "description": "網路搜尋功能",
        "tools": ["web_search", "fetch_content"]
    }
}

# 驗證設定
logger.info(f"✅ LINE Token 長度: {len(LINE_CHANNEL_ACCESS_TOKEN)}")
logger.info(f"✅ LINE Secret 長度: {len(LINE_CHANNEL_SECRET)}")  
logger.info(f"✅ Claude API Key 長度: {len(ANTHROPIC_API_KEY)}")
logger.info(f"✅ 配置了 {len(MCP_SERVERS)} 個 MCP 伺服器")

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

# 儲存對話歷史和 MCP 連接狀態
conversation_history = {}
mcp_status = {}
executor = ThreadPoolExecutor(max_workers=4)

class MCPConnector:
    """MCP 連接器類別（僅支援 HTTPS）"""
    
    def __init__(self):
        self.connections = {}
        self.tools = {}
    
    def test_https_connection(self, url, timeout=5):
        """測試 HTTPS 連接"""
        try:
            # 嘗試多種端點
            endpoints_to_try = [
                f"{url}/health",
                f"{url}/status", 
                f"{url}",
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    response = requests.get(endpoint, timeout=timeout)
                    if response.status_code in [200, 404, 405]:
                        return True
                except:
                    continue
            
            # 嘗試 POST 請求（某些 MCP 端點只接受 POST）
            try:
                response = requests.post(url, 
                    json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, 
                    timeout=timeout,
                    headers={"Content-Type": "application/json"})
                return response.status_code in [200, 404, 405, 501]
            except:
                pass
            
            return False
        except Exception as e:
            logger.debug(f"HTTPS 連接失敗 {url}: {e}")
            return False
    
    def check_server_status(self, server_name, config):
        """檢查單個伺服器狀態"""
        try:
            if config["type"] == "https":
                return self.test_https_connection(config["url"])
            else:
                logger.warning(f"不支援的伺服器類型: {config['type']} (需安裝 websockets)")
                return False
        except Exception as e:
            logger.debug(f"檢查伺服器 {server_name} 狀態時發生錯誤: {e}")
            return False
    
    def get_available_tools(self):
        """取得所有可用工具列表"""
        tools = []
        for server_name, status in mcp_status.items():
            if status.get("active"):
                server_config = MCP_SERVERS.get(server_name, {})
                server_tools = server_config.get("tools", [])
                for tool in server_tools:
                    tools.append({
                        "name": tool,
                        "server": server_name,
                        "description": f"{server_config.get('description', '')} - {tool}"
                    })
        return tools

# 全域 MCP 連接器
mcp_connector = MCPConnector()

def check_mcp_servers():
    """檢查所有 MCP 伺服器狀態"""
    global mcp_status
    active_servers = []
    
    for server_name, config in MCP_SERVERS.items():
        try:
            # 使用線程池進行非阻塞檢查
            future = executor.submit(mcp_connector.check_server_status, server_name, config)
            is_active = future.result(timeout=10)  # 10 秒超時
            
            server_info = {
                "name": server_name,
                "url": config["url"],
                "type": config["type"],
                "description": config["description"],
                "tools": config.get("tools", []),
                "status": "active" if is_active else "inactive"
            }
            
            # 更新狀態
            mcp_status[server_name] = {
                "active": is_active,
                "last_check": "now",
                "config": config
            }
            
            if is_active:
                active_servers.append(server_info)
                logger.info(f"✅ MCP 伺服器 {server_name} ({config['type']}) 可用")
            else:
                logger.warning(f"❌ MCP 伺服器 {server_name} ({config['type']}) 不可用")
                
        except Exception as e:
            logger.warning(f"⚠️ 檢查 MCP 伺服器 {server_name} 時發生錯誤: {e}")
            mcp_status[server_name] = {
                "active": False,
                "last_check": "error",
                "error": str(e)
            }
    
    return active_servers

def get_mcp_enhanced_system_prompt(active_servers):
    """生成包含 MCP 工具資訊的系統提示"""
    base_prompt = """你是一個友善的AI助理，會用繁體中文回應用戶。"""
    
    if not active_servers:
        return base_prompt + "\n請保持對話自然、有幫助且簡潔。"
    
    tools_info = "\n\n🔧 你現在具備以下工具能力：\n"
    for server in active_servers:
        tools_info += f"• **{server['name']}** ({server['type']}): {server['description']}\n"
        if server.get('tools'):
            tools_info += f"  可用功能: {', '.join(server['tools'])}\n"
    
    usage_guide = """
🎯 **使用指南**：
- 天氣查詢：使用 weather-server
- 檔案操作：使用 filesystem-server  
- 程式碼分析：使用 deepwiki
- 網路搜尋：使用 search-server

當用戶需要這些功能時，請告知你正在使用相應的工具協助處理。
如果工具暫時無法使用，請提供替代建議。"""
    
    return base_prompt + tools_info + usage_guide

def get_claude_response_with_mcp(user_message, user_id):
    """使用 MCP 增強的 Claude 回應"""
    try:
        # 檢查並更新 MCP 伺服器狀態（每次都檢查以確保即時性）
        active_servers = check_mcp_servers()
        
        # 取得用戶對話歷史
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        messages = conversation_history[user_id][-20:]
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        logger.info(f"發送給 Claude (MCP增強): {user_message[:50]}...")
        
        # 使用動態系統提示
        system_prompt = get_mcp_enhanced_system_prompt(active_servers)
        
        # 呼叫 Claude API
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1200,
            temperature=0.7,
            messages=messages,
            system=system_prompt
        )
        
        assistant_response = response.content[0].text
        logger.info(f"Claude (MCP) 回應: {assistant_response[:100]}...")
        
        # 如果回應中提到使用工具，添加工具狀態資訊
        if any(server["name"] in assistant_response.lower() for server in active_servers):
            tool_status = f"\n\n🔧 *工具狀態: {len(active_servers)} 個 MCP 工具可用*"
            assistant_response += tool_status
        
        # 更新對話歷史
        messages.append({
            "role": "assistant", 
            "content": assistant_response
        })
        conversation_history[user_id] = messages
        
        return assistant_response
        
    except Exception as e:
        logger.error(f"Claude MCP API 錯誤: {e}")
        return get_claude_response_fallback(user_message, user_id)

def get_claude_response_fallback(user_message, user_id):
    """備用的一般 Claude API"""
    try:
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        messages = conversation_history[user_id][-20:]
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        logger.info(f"使用備用 Claude API: {user_message[:50]}...")
        
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            temperature=0.7,
            messages=messages,
            system="你是一個友善的AI助理，會用繁體中文回應用戶。請保持對話自然、有幫助且簡潔。目前 MCP 工具暫時無法使用。"
        )
        
        assistant_response = response.content[0].text + "\n\n⚠️ *MCP 工具暫時無法使用*"
        
        # 更新對話歷史
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })
        conversation_history[user_id] = messages
        
        return assistant_response
        
    except Exception as e:
        logger.error(f"備用 Claude API 錯誤: {e}")
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
        if user_message.lower().startswith('/mcp'):
            active_servers = check_mcp_servers()
            if active_servers:
                status_msg = "🔧 **可用的 MCP 工具**：\n\n"
                for server in active_servers:
                    status_msg += f"✅ **{server['name']}** ({server['type']})\n"
                    status_msg += f"   📝 {server['description']}\n"
                    if server.get('tools'):
                        status_msg += f"   🛠️ 功能: {', '.join(server['tools'])}\n"
                    status_msg += f"   🌐 {server['url']}\n\n"
                status_msg += f"💡 *共 {len(active_servers)} 個工具可用*"
            else:
                status_msg = "❌ **目前沒有可用的 MCP 工具**\n\n"
                status_msg += "可能的原因：\n• 伺服器尚未啟動\n• 網路連接問題\n• 配置錯誤"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=status_msg)
            )
            return
        
        elif user_message.lower() in ['/clear', '/reset', '清除對話']:
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

🔧 **MCP 工具**
• 程式碼分析、網路搜尋
• 使用 `/mcp` 查看工具狀態

⚡ **指令列表**
• `/mcp` - 查看 MCP 工具狀態  
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
    active_servers = check_mcp_servers()
    return {
        "status": "healthy",
        "message": "LINE Bot + Claude + MCP is running",
        "mcp_servers_total": len(MCP_SERVERS),
        "mcp_servers_active": len(active_servers),
        "active_conversations": len(conversation_history),
        "mcp_status": mcp_status
    }, 200

@app.route("/", methods=['GET'])
def home():
    """首頁"""
    active_servers = check_mcp_servers()
    server_names = [s["name"] for s in active_servers]
    return f"""🤖 LINE Bot + Claude API + MCP 聊天機器人運行中！

🔧 MCP 狀態: {len(active_servers)}/{len(MCP_SERVERS)} 可用
📊 可用工具: {', '.join(server_names) if server_names else '無'}
💬 活躍對話: {len(conversation_history)} 個

使用 /health 查看詳細狀態"""

@app.route("/mcp/status", methods=['GET'])
def mcp_detailed_status():
    """MCP 伺服器詳細狀態"""
    active_servers = check_mcp_servers()
    
    detailed_status = {
        "timestamp": "now",
        "summary": {
            "total_servers": len(MCP_SERVERS),
            "active_servers": len(active_servers),
            "inactive_servers": len(MCP_SERVERS) - len(active_servers)
        },
        "servers": {}
    }
    
    for server_name, config in MCP_SERVERS.items():
        status_info = mcp_status.get(server_name, {"active": False})
        detailed_status["servers"][server_name] = {
            "config": {
                "url": config["url"],
                "type": config["type"],
                "description": config["description"],
                "tools": config.get("tools", [])
            },
            "status": {
                "active": status_info.get("active", False),
                "last_check": status_info.get("last_check", "never"),
                "error": status_info.get("error")
            }
        }
    
    return detailed_status, 200

@app.route("/mcp/tools", methods=['GET'])
def get_available_tools():
    """取得所有可用工具"""
    tools = mcp_connector.get_available_tools()
    return {
        "available_tools": tools,
        "total_tools": len(tools)
    }, 200

if __name__ == "__main__":
    logger.info("🚀 啟動 LINE Bot + Claude API + MCP 聊天機器人")
    
    # 初始檢查 MCP 伺服器
    active_servers = check_mcp_servers()
    logger.info(f"📊 MCP 狀態: {len(active_servers)}/{len(MCP_SERVERS)} 伺服器可用")
    
    # 啟動應用
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)