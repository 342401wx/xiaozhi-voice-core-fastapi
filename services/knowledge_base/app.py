import os
from flask import Flask, request, jsonify, Response, render_template, session
import json
from database import (
    init_database, fetch_chat_history, save_chat_message,
    get_user_info, update_user_info,
    register_user, login_user, get_user_by_id,
)
from intent_detector import detect_intent_code
from rag_engine import get_response_from_vectorstore
from vector_store import init_knowledge_base
from tools import (
    tools,
    execute_tool,
    infer_search_type,
    format_web_research_fallback,
)
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_CACHE_TTL

# Redis 缓存
try:
    import redis
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
    print("Redis 缓存已启用")
except Exception as e:
    redis_client = None
    REDIS_AVAILABLE = False
    print(f"Redis 不可用，使用内存缓存: {e}")

# 内存缓存（Redis 不可用时的降级方案）
memory_cache = {}

def get_cache(key):
    """获取缓存"""
    if REDIS_AVAILABLE:
        try:
            data = redis_client.get(key)
            return json.loads(data) if data else None
        except:
            return None
    else:
        import time
        if key in memory_cache:
            value, expire_time = memory_cache[key]
            if time.time() < expire_time:
                return value
            else:
                del memory_cache[key]
        return None

def set_cache(key, value, ttl=None):
    """设置缓存"""
    ttl = ttl or REDIS_CACHE_TTL
    if REDIS_AVAILABLE:
        try:
            redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except:
            pass
    else:
        import time
        memory_cache[key] = (value, time.time() + ttl)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "seachat-secret-key-change-in-production")

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

WEB_RESEARCH_INTENT_CODE = 1

ENTERPRISE_COLLECTION_MAP = {
    2: "it_service_knowledge",
    3: "hr_policy_knowledge",
    4: "admin_service_knowledge",
    5: "finance_reimbursement_knowledge",
}

SYSTEM_PROMPT_TEMPLATE = """你是SeaChat企业内部服务台智能客服助手，负责解答员工关于IT、人事、行政和财务流程的问题。

用户信息：
{user_info}

回答策略：
{response_strategy}
"""


def is_plain_greeting(query):
    normalized = query.strip().lower().strip("。！？!?~ ")
    return normalized in {"你好", "您好", "hi", "hello", "hey", "在吗"}


def decide_response_strategy(user_info, intent_code):
    intent_names = {
        1: "网络搜索",
        2: "IT服务支持",
        3: "HR人事政策",
        4: "行政办公服务",
        5: "财务报销制度",
        6: "常规回答",
    }
    if not user_info:
        return f"这是新用户或缺少用户画像。当前意图为{intent_names.get(intent_code, '未知')}，回答时先给直接结论，再提示必要的下一步。"

    preferred = intent_names.get(user_info.get("intent_preference"), "暂无明确历史偏好")
    current = intent_names.get(intent_code, "未知")
    return (
        f"用户历史偏好为：{preferred}；当前识别意图为：{current}。"
        "回答时优先匹配当前问题，不要因为历史偏好偏离用户本次需求；涉及流程、权限、费用、政策时给出边界并提示转人工条件。"
    )


def get_web_search_response(query):
    result = execute_tool("web_research", {
        "query": query,
        "search_type": infer_search_type(query),
        "max_results": 5,
        "max_pages": 3,
    })
    return summarize_web_research(query, result)


def build_web_research_context(research_result):
    sections = []
    for index, page in enumerate(research_result.get("pages") or [], start=1):
        title = page.get("title") or page.get("search_title") or "未命名网页"
        url = page.get("final_url") or page.get("url") or ""
        text = page.get("text") or page.get("search_snippet") or ""
        table_lines = []
        for table_index, table in enumerate(page.get("tables") or [], start=1):
            rows = [" | ".join(row) for row in table.get("rows", [])[:6]]
            if rows:
                caption = table.get("caption") or f"表格{table_index}"
                table_lines.append(f"{caption}: " + " / ".join(rows))
        image_lines = []
        for image in (page.get("images") or [])[:5]:
            image_lines.append(f"{image.get('alt') or '未命名图片'} - {image.get('url')}")
        sections.append(
            "\n".join([
                f"[网页{index}] {title}",
                f"URL: {url}",
                f"搜索摘要: {page.get('search_snippet', '')}",
                f"正文摘录: {text}",
                "表格资料: " + ("; ".join(table_lines) if table_lines else "未提取到HTML表格"),
                "图片/图表链接: " + ("; ".join(image_lines) if image_lines else "未提取到图片信息"),
            ])
        )
    if sections:
        return "\n\n".join(sections)

    fallback_results = []
    for index, item in enumerate(research_result.get("search_results") or [], start=1):
        fallback_results.append(
            f"[搜索结果{index}] {item.get('title', '')}\nURL: {item.get('link', '')}\n摘要: {item.get('snippet', '')}"
        )
    return "\n\n".join(fallback_results)


def summarize_web_research(query, research_result):
    if research_result.get("status") != "success":
        return format_web_research_fallback(research_result)

    context = build_web_research_context(research_result)
    if not context:
        return format_web_research_fallback(research_result)

    prompt = f"""请基于下面联网搜索并打开网页后提取到的资料，回答用户问题。

用户问题：{query}

要求：
1. 只根据提供的网页资料回答，不要编造没有依据的信息。
2. 先给出简洁结论，再用要点列出关键信息。
3. 如果资料里包含表格或图片/图表信息，请单独列出"图表/表格信息"。
4. 结尾必须列出"来源"，包含网页标题和URL。
5. 用中文输出。

网页资料：
{context}
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是严谨的联网资料整理助手，擅长基于网页正文、表格和图片信息生成带来源的中文答案。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1600,
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"联网资料总结错误: {exc}")
        return format_web_research_fallback(research_result)


def SeaChatInterview(user_id, query):
    chat_history = fetch_chat_history(user_id)

    if not chat_history and is_plain_greeting(query):
        update_user_info(user_id)
        welcome = "您好！我是SeaChat企业内部服务台助手，请问有什么可以帮您？"
        save_chat_message(user_id, "user", query)
        save_chat_message(user_id, "assistant", welcome)
        return welcome
    elif not chat_history:
        update_user_info(user_id)

    user_info = get_user_info(user_id)
    user_info_str = json.dumps(user_info, ensure_ascii=False, default=str) if user_info else "新用户"

    intent_code = detect_intent_code(query)
    response_strategy = decide_response_strategy(user_info, intent_code)
    user_context = f"{user_info_str}\n回答策略：{response_strategy}"

    if intent_code == WEB_RESEARCH_INTENT_CODE:
        response_text = get_web_search_response(query)
        save_chat_message(user_id, "user", query, intent_code)
        save_chat_message(user_id, "assistant", response_text, intent_code)
        update_user_info(user_id, intent_preference=intent_code)
        return response_text

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT_TEMPLATE.format(
                user_info=user_info_str,
                response_strategy=response_strategy,
            )
        }
    ]
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": query})

    if intent_code in ENTERPRISE_COLLECTION_MAP:
        collection = ENTERPRISE_COLLECTION_MAP[intent_code]
        response_text = get_response_from_vectorstore(query, collection, user_context)
    else:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        assistant_message = response.choices[0].message

        if assistant_message.tool_calls:
            tool_results = []
            for tool_call in assistant_message.tool_calls:
                result = execute_tool(tool_call.function.name, json.loads(tool_call.function.arguments))
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False)
                })
            messages.append(assistant_message.model_dump())
            messages.extend(tool_results)

            final_response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages
            )
            response_text = final_response.choices[0].message.content
        else:
            response_text = assistant_message.content

    save_chat_message(user_id, "user", query, intent_code)
    save_chat_message(user_id, "assistant", response_text, intent_code)
    update_user_info(user_id, intent_preference=intent_code)

    return response_text


# ---- Auth routes ----

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    result = register_user(data['username'], data['password'])
    if result['success']:
        return jsonify({"status": "success", "message": "注册成功，请登录"})
    return jsonify({"error": result['error']}), 400


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    result = login_user(data['username'], data['password'])
    if result['success']:
        session['user_id'] = result['user_id']
        session['username'] = result['username']
        return jsonify({"status": "success", "username": result['username']})
    return jsonify({"error": result['error']}), 401


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "success"})


@app.route('/session', methods=['GET'])
def check_session():
    if 'user_id' in session:
        return jsonify({
            "logged_in": True,
            "user_id": session['user_id'],
            "username": session['username'],
        })
    return jsonify({"logged_in": False})


# ---- Page routes ----

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat_api():
    if 'user_id' not in session:
        return jsonify({"error": "请先登录"}), 401

    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "缺少必要参数：query"}), 400

    user_id = session['user_id']
    query = data['query']

    def generate():
        chat_history = fetch_chat_history(user_id)

        if not chat_history and is_plain_greeting(query):
            update_user_info(user_id)
            welcome = "您好！我是SeaChat企业内部服务台助手，请问有什么可以帮您？"
            save_chat_message(user_id, "user", query)
            save_chat_message(user_id, "assistant", welcome)
            yield f"data: {json.dumps({'content': welcome, 'done': True}, ensure_ascii=False)}\n\n"
            return
        elif not chat_history:
            update_user_info(user_id)

        user_info = get_user_info(user_id)
        user_info_str = json.dumps(user_info, ensure_ascii=False, default=str) if user_info else "新用户"

        intent_code = detect_intent_code(query)
        response_strategy = decide_response_strategy(user_info, intent_code)
        user_context = f"{user_info_str}\n回答策略：{response_strategy}"

        if intent_code == WEB_RESEARCH_INTENT_CODE:
            response_text = get_web_search_response(query)
            save_chat_message(user_id, "user", query, intent_code)
            save_chat_message(user_id, "assistant", response_text, intent_code)
            update_user_info(user_id, intent_preference=intent_code)
            yield f"data: {json.dumps({'content': response_text, 'done': True, 'source': 'web_search'}, ensure_ascii=False)}\n\n"
            return

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_TEMPLATE.format(
                    user_info=user_info_str,
                    response_strategy=response_strategy,
                )
            }
        ]
        for msg in chat_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": query})

        if intent_code in ENTERPRISE_COLLECTION_MAP:
            collection = ENTERPRISE_COLLECTION_MAP[intent_code]

            # 检查缓存
            cache_key = f"kb:{collection}:{query}"
            cached_result = get_cache(cache_key)
            if cached_result:
                response_text = cached_result.get("response", "")
                source = cached_result.get("source", "knowledge_base")
            else:
                response_text, source = get_response_from_vectorstore(query, collection, user_context)
                # 设置缓存
                set_cache(cache_key, {"response": response_text, "source": source})
            save_chat_message(user_id, "user", query, intent_code)
            save_chat_message(user_id, "assistant", response_text, intent_code)
            update_user_info(user_id, intent_preference=intent_code)
            yield f"data: {json.dumps({'content': response_text, 'done': True, 'source': source}, ensure_ascii=False)}\n\n"
        else:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True
            )

            tool_calls_data = {}
            full_response = ""
            finish_reason = None

            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""}
                            }
                        if tc.id:
                            tool_calls_data[idx]["id"] = tc.id
                        if tc.function.name:
                            tool_calls_data[idx]["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_data[idx]["function"]["arguments"] += tc.function.arguments

                if delta.content:
                    full_response += delta.content
                    yield f"data: {json.dumps({'content': delta.content, 'done': False}, ensure_ascii=False)}\n\n"

            if tool_calls_data:
                tool_results = []
                for idx in sorted(tool_calls_data.keys()):
                    tc_data = tool_calls_data[idx]
                    result = execute_tool(tc_data["function"]["name"], json.loads(tc_data["function"]["arguments"]))
                    tool_results.append({
                        "tool_call_id": tc_data["id"],
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False)
                    })

                assistant_tool_msg = {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tc_data["id"],
                        "type": "function",
                        "function": tc_data["function"]
                    } for tc_data in tool_calls_data.values()]
                }
                messages.append(assistant_tool_msg)
                messages.extend(tool_results)

                final_response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    stream=True
                )

                full_response = ""
                for chunk in final_response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_response += delta.content
                        yield f"data: {json.dumps({'content': delta.content, 'done': False}, ensure_ascii=False)}\n\n"

            save_chat_message(user_id, "user", query, intent_code)
            save_chat_message(user_id, "assistant", full_response, intent_code)
            update_user_info(user_id, intent_preference=intent_code)
            yield f"data: {json.dumps({'content': '', 'done': True, 'source': 'llm'}, ensure_ascii=False)}\n\n"

    return Response(generate(), content_type='text/event-stream')


@app.route('/history', methods=['GET'])
def get_history():
    if 'user_id' not in session:
        return jsonify({"error": "请先登录"}), 401

    user_id = session['user_id']
    history = fetch_chat_history(user_id)
    return jsonify({"history": history[-50:]})


@app.route('/knowledge/update', methods=['POST'])
def update_knowledge():
    data = request.get_json()
    if not data or 'collection' not in data or 'documents' not in data:
        return jsonify({"error": "缺少必要参数：collection 和 documents"}), 400

    from vector_store import add_documents
    collection = data['collection']
    documents = data['documents']
    metadatas = data.get('metadatas')

    ids = add_documents(collection, documents, metadatas)
    return jsonify({"status": "success", "ids": ids})


@app.route('/knowledge/query', methods=['POST'])
def query_knowledge():
    data = request.get_json()
    if not data or 'collection' not in data or 'query' not in data:
        return jsonify({"error": "缺少必要参数：collection 和 query"}), 400

    from vector_store import query_documents
    results = query_documents(data['collection'], data['query'], data.get('n_results', 3))
    return jsonify({"results": results})


@app.route('/sql/query', methods=['POST'])
def sql_query():
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "缺少必要参数：query"}), 400

    from sql_agent import sql_agent_query
    result = sql_agent_query(data['query'])
    return jsonify({"response": result})


@app.route('/web/search', methods=['POST'])
def web_search_api():
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "缺少必要参数：query"}), 400

    result = execute_tool("web_search", {
        "query": data["query"],
        "search_type": data.get("search_type") or infer_search_type(data["query"]),
        "max_results": data.get("max_results", 5),
    })
    return jsonify(result)


@app.route('/web/research', methods=['POST'])
def web_research_api():
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"error": "缺少必要参数：query"}), 400

    result = execute_tool("web_research", {
        "query": data["query"],
        "search_type": data.get("search_type") or infer_search_type(data["query"]),
        "max_results": data.get("max_results", 5),
        "max_pages": data.get("max_pages", 3),
    })
    return jsonify(result)


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})


if __name__ == '__main__':
    init_database()
    init_knowledge_base()
    print("SeaChat服务启动中...")
    app.run(host='0.0.0.0', port=5000, debug=True)
