import json
from openai import OpenAI
from database import get_connection
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

SQL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_chat_history",
            "description": "查询用户的聊天历史记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "用户ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回记录数量，默认10条"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_user_stats",
            "description": "查询用户咨询统计信息，包括各意图的咨询次数",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "用户ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_all_users",
            "description": "查询所有注册用户列表",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_recent_chats",
            "description": "查询最近的聊天记录（所有用户）",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回记录数量，默认20条"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_intent_distribution",
            "description": "查询所有用户的意图分布统计",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行自定义SQL查询语句（只读）",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL查询语句，只能是SELECT语句"
                    }
                },
                "required": ["sql"]
            }
        }
    }
]

def execute_sql_tool(tool_name, arguments):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if tool_name == "query_chat_history":
            uid = arguments["user_id"]
            limit = arguments.get("limit", 10)
            cursor.execute(
                "SELECT role, content, intent_code, created_at FROM chat_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (uid, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        elif tool_name == "query_user_stats":
            uid = arguments["user_id"]
            cursor.execute(
                "SELECT intent_code, COUNT(*) as count FROM chat_history WHERE user_id = ? GROUP BY intent_code",
                (uid,)
            )
            rows = cursor.fetchall()
            intent_map = {1: "网络搜索", 2: "IT服务支持", 3: "HR人事政策", 4: "行政办公服务", 5: "财务报销制度", 6: "其他"}
            return [{"意图": intent_map.get(r["intent_code"], "未知"), "次数": r["count"]} for r in rows]

        elif tool_name == "query_all_users":
            cursor.execute("SELECT u.id, u.username, u.created_at, ui.intent_preference FROM users u LEFT JOIN user_info ui ON u.id = ui.user_id")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        elif tool_name == "query_recent_chats":
            limit = arguments.get("limit", 20)
            cursor.execute(
                "SELECT ch.user_id, u.username, ch.role, ch.content, ch.intent_code, ch.created_at FROM chat_history ch LEFT JOIN users u ON ch.user_id = u.id ORDER BY ch.created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        elif tool_name == "query_intent_distribution":
            cursor.execute("SELECT intent_code, COUNT(*) as count FROM chat_history GROUP BY intent_code")
            rows = cursor.fetchall()
            intent_map = {1: "网络搜索", 2: "IT服务支持", 3: "HR人事政策", 4: "行政办公服务", 5: "财务报销制度", 6: "其他"}
            return [{"意图": intent_map.get(r["intent_code"], "未知"), "总次数": r["count"]} for r in rows]
        
        elif tool_name == "execute_sql":
            sql = arguments["sql"].strip()
            if not sql.upper().startswith("SELECT"):
                return {"error": "只允许执行SELECT查询语句"}
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()
    
    return {"error": "未知工具"}

def sql_agent_query(user_query):
    messages = [
        {"role": "system", "content": "你是SQL数据库查询助手。根据用户的自然语言问题，调用合适的工具查询数据库并返回结果。用中文回答。"},
        {"role": "user", "content": user_query}
    ]
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        tools=SQL_TOOLS,
        tool_choice="auto"
    )
    
    assistant_message = response.choices[0].message
    
    if assistant_message.tool_calls:
        messages.append(assistant_message.model_dump())
        
        for tool_call in assistant_message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            result = execute_sql_tool(func_name, func_args)
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": json.dumps(result, ensure_ascii=False, default=str)
            })
        
        final_response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )
        return final_response.choices[0].message.content
    else:
        return assistant_message.content
