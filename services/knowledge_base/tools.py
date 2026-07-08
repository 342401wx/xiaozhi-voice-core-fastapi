from database import get_user_info, get_user_stats, update_user_info


WEB_SEARCH_KEYWORDS = [
    "今天", "最新", "实时", "新闻", "资讯", "热点", "网上", "网络",
    "联网", "搜索", "查一下", "帮我查", "查查", "现在", "最近",
]

NEWS_SEARCH_KEYWORDS = ["新闻", "热点", "资讯", "头条", "今天"]


def should_use_web_search(query):
    return any(keyword in query for keyword in WEB_SEARCH_KEYWORDS)


def infer_search_type(query):
    return "news" if any(keyword in query for keyword in NEWS_SEARCH_KEYWORDS) else "web"


def format_web_search_response(search_result):
    if search_result.get("status") != "success":
        return f"网络搜索失败：{search_result.get('error', '未知错误')}。请稍后重试，或换一个更具体的关键词。"

    results = search_result.get("results") or []
    if not results:
        return "我已经尝试联网搜索，但没有找到可用结果。你可以换一个更具体的关键词再试。"

    search_name = "新闻搜索" if search_result.get("search_type") == "news" else "网页搜索"
    lines = [
        f"我已完成{search_name}，以下是检索到的结果：",
        "",
    ]

    for index, item in enumerate(results, start=1):
        title = item.get("title") or "未命名结果"
        source = item.get("source") or item.get("published_at") or "来源未标明"
        snippet = item.get("snippet") or "暂无摘要"
        link = item.get("link") or ""
        lines.extend([
            f"{index}. {title}",
            f"   来源/时间：{source}",
            f"   摘要：{snippet}",
        ])
        if link:
            lines.append(f"   链接：{link}")
        lines.append("")

    lines.append(f"检索时间：{search_result.get('fetched_at', '')}")
    return "\n".join(lines).strip()


def format_web_research_fallback(research_result):
    if research_result.get("status") != "success":
        return f"联网研究失败：{research_result.get('error', '未知错误')}。请稍后重试，或换一个更具体的关键词。"

    pages = research_result.get("pages") or []
    if not pages:
        return format_web_search_response({
            "status": "success",
            "query": research_result.get("query"),
            "search_type": research_result.get("search_type"),
            "results": research_result.get("search_results") or [],
            "fetched_at": research_result.get("fetched_at"),
        })

    lines = ["我已经打开搜索结果并提取网页内容，整理如下：", ""]
    for index, page in enumerate(pages, start=1):
        title = page.get("title") or page.get("search_title") or "未命名网页"
        url = page.get("final_url") or page.get("url") or ""
        text = page.get("text") or page.get("search_snippet") or "未提取到正文。"
        lines.extend([
            f"{index}. {title}",
            f"   网址：{url}",
            f"   要点：{text[:500]}",
        ])
        tables = page.get("tables") or []
        if tables:
            lines.append(f"   表格：提取到 {len(tables)} 个HTML表格。")
        images = page.get("images") or []
        if images:
            lines.append(f"   图片/图表：提取到 {len(images)} 个图片链接。")
        lines.append("")
    lines.append(f"检索时间：{research_result.get('fetched_at', '')}")
    return "\n".join(lines).strip()

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "获取用户的详细信息，包括姓名、咨询偏好和历史统计",
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
            "name": "update_user_preference",
            "description": "更新用户的咨询偏好",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "用户ID"
                    },
                    "intent_code": {
                        "type": "integer",
                        "description": "意图编号：1-网络搜索，2-IT服务支持，3-HR人事政策，4-行政办公服务，5-财务报销制度，6-其他",
                        "enum": [1, 2, 3, 4, 5, 6]
                    }
                },
                "required": ["user_id", "intent_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "搜索知识库获取相关信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "category": {
                        "type": "string",
                        "description": "知识库类别",
                        "enum": ["it", "hr", "admin", "finance"]
                    }
                },
                "required": ["query", "category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索网页或新闻，用于回答今天、最新、实时、新闻、网上查找等知识库外部问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或用户问题"
                    },
                    "search_type": {
                        "type": "string",
                        "description": "搜索类型：news表示新闻搜索，web表示普通网页搜索",
                        "enum": ["news", "web"]
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回结果数量，默认5条"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_research",
            "description": "联网搜索并打开网页，提取正文、HTML表格和图片信息，用于生成带来源网址的综合回答",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或用户问题"
                    },
                    "search_type": {
                        "type": "string",
                        "description": "搜索类型：news表示新闻搜索，web表示普通网页搜索",
                        "enum": ["news", "web"]
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "搜索结果数量，默认5条"
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "最多打开并提取的网页数量，默认3个"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def execute_tool(tool_name, arguments):
    if tool_name == "get_user_profile":
        user_info = get_user_info(arguments["user_id"])
        stats = get_user_stats(arguments["user_id"])
        return {"user_info": user_info, "stats": stats}
    elif tool_name == "update_user_preference":
        update_user_info(
            arguments["user_id"],
            intent_preference=arguments["intent_code"]
        )
        return {"status": "success", "message": "用户偏好已更新"}
    elif tool_name == "search_knowledge_base":
        from vector_store import query_documents
        collection_map = {
            "it": "it_service_knowledge",
            "hr": "hr_policy_knowledge",
            "admin": "admin_service_knowledge",
            "finance": "finance_reimbursement_knowledge",
        }
        results = query_documents(
            collection_map[arguments["category"]],
            arguments["query"],
            n_results=3
        )
        return {"results": results["documents"][0] if results["documents"] else []}
    elif tool_name == "web_search":
        from web_search import web_search
        return web_search(
            arguments["query"],
            arguments.get("search_type") or infer_search_type(arguments["query"]),
            arguments.get("max_results", 5)
        )
    elif tool_name == "web_research":
        from web_search import web_research
        return web_research(
            arguments["query"],
            arguments.get("search_type") or infer_search_type(arguments["query"]),
            arguments.get("max_results", 5),
            arguments.get("max_pages", 3)
        )
    return {"error": "未知工具"}
