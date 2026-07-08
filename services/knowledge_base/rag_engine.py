from openai import OpenAI
from vector_store import query_documents
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME, RESPONSE_PROMPT_TEMPLATE

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

RELEVANCE_THRESHOLD = 1.5


def _first_result_list(results, key):
    values = results.get(key) or []
    return values[0] if values else []


def _build_rag_context(results):
    documents = _first_result_list(results, "documents")
    metadatas = _first_result_list(results, "metadatas")
    distances = _first_result_list(results, "distances")

    if not documents:
        return "暂无相关信息", []

    context_parts = []
    sources = []
    seen_sources = set()

    for index, document in enumerate(documents, start=1):
        metadata = metadatas[index - 1] if index - 1 < len(metadatas) else {}
        distance = distances[index - 1] if index - 1 < len(distances) else None

        if isinstance(distance, (int, float)) and distance > RELEVANCE_THRESHOLD:
            continue

        source_address = metadata.get("source_address") or metadata.get("source_file") or "未记录来源地址"
        doc_id = metadata.get("doc_id") or metadata.get("source_id") or f"doc_{index}"
        title = metadata.get("title") or f"知识片段 {index}"
        collection = metadata.get("collection", "")

        context_parts.append(
            "\n".join([
                f"[来源{index}]",
                f"标题：{title}",
                f"集合：{collection}",
                f"文档ID：{doc_id}",
                f"来源地址：{source_address}",
                f"相似度距离：{distance:.4f}" if isinstance(distance, (int, float)) else "相似度距离：-",
                f"内容：{document}",
            ])
        )

        source_key = (source_address, doc_id)
        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append({
                "index": len(sources) + 1,
                "title": title,
                "doc_id": doc_id,
                "collection": collection,
                "source_address": source_address,
            })

    if not context_parts:
        return "暂无相关信息", []

    return "\n\n".join(context_parts), sources


def _format_source_list(sources):
    if not sources:
        return ""

    lines = ["", "", "知识库来源："]
    for source in sources:
        collection = f"，集合：{source['collection']}" if source.get("collection") else ""
        lines.append(
            f"{source['index']}. {source['title']}（文档ID：{source['doc_id']}{collection}）"
        )
        lines.append(f"   来源地址：{source['source_address']}")
    return "\n".join(lines)


def get_response_from_vectorstore(query, collection_name, user_info=""):
    try:
        results = query_documents(collection_name, query, n_results=3)
        context, sources = _build_rag_context(results)
    except Exception as e:
        print(f"向量库查询失败，回退到直接回答: {e}")
        context = "暂无相关信息"
        sources = []

    has_knowledge = bool(sources)

    if has_knowledge:
        system_msg = "你是SeaChat智能客服助手。请严格依据提供的知识库内容回答，不要编造。回答后列出知识库来源。"
        prompt = RESPONSE_PROMPT_TEMPLATE.format(query=query, context=context, user_info=user_info)
    else:
        system_msg = "你是SeaChat企业内部服务台智能客服助手，友好专业地回答员工问题。"
        prompt = f"用户问题：{query}\n\n请直接回答用户问题。"

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        answer = response.choices[0].message.content

        if has_knowledge:
            return f"{answer}{_format_source_list(sources)}", "knowledge_base"
        return answer, "llm"
    except Exception as e:
        print(f"生成响应错误: {e}")
        return "抱歉，系统暂时出现问题，请稍后再试。", "llm"
