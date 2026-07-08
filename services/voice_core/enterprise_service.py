from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


VOICE_CORE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VOICE_CORE_DIR.parent.parent
DEFAULT_KB_PATH = PROJECT_ROOT / "services" / "knowledge_base" / "enterprise_service_desk_knowledge_base.json"

COLLECTION_LABELS = {
    "it_service_knowledge": "IT服务支持",
    "hr_policy_knowledge": "HR人事政策",
    "admin_service_knowledge": "行政办公服务",
    "finance_reimbursement_knowledge": "财务报销制度",
}

COLLECTION_KEYWORDS = {
    "it_service_knowledge": [
        "账号", "密码", "mfa", "多因素", "验证器", "vpn", "邮箱", "邮件", "teams",
        "microsoft", "office", "onedrive", "sharepoint", "软件", "设备", "电脑",
        "权限", "数据泄露", "钓鱼", "安全", "工单", "内网", "远程办公",
    ],
    "hr_policy_knowledge": [
        "入职", "劳动合同", "合同", "试用期", "转正", "考勤", "打卡", "请假",
        "年假", "年休假", "病假", "事假", "婚假", "产假", "陪产假", "薪资",
        "工资", "社保", "公积金", "五险一金", "五险", "一金", "养老保险",
        "医疗保险", "失业保险", "工伤保险", "生育保险", "住房公积金",
        "绩效", "培训", "转岗", "离职", "离职证明",
    ],
    "admin_service_knowledge": [
        "门禁", "工牌", "访客", "会议室", "停车", "办公用品", "打印机", "工位",
        "快递", "邮件", "资产", "差旅预订", "行政", "报修", "空调", "停电",
        "消防", "突发事件", "办公区",
    ],
    "finance_reimbursement_knowledge": [
        "报销", "发票", "电子发票", "数电票", "火车票", "机票", "酒店",
        "差旅", "差旅标准", "预算", "超预算", "供应商", "付款", "采购",
        "合同付款", "退回", "财务", "税号", "成本中心", "项目编码",
    ],
}


def _kb_path() -> Path:
    configured = os.getenv("XIAOZHI_ENTERPRISE_KB_PATH")
    return Path(configured) if configured else DEFAULT_KB_PATH


@lru_cache(maxsize=1)
def _load_knowledge_base() -> dict[str, Any]:
    path = _kb_path()
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data


def reload_knowledge_base() -> None:
    _load_knowledge_base.cache_clear()


def stats() -> dict[str, Any]:
    data = _load_knowledge_base()
    collections = data.get("collections", {})
    counts = {name: len(items or []) for name, items in collections.items()}
    return {
        "path": str(_kb_path()),
        "version": data.get("version"),
        "collections": counts,
        "total": sum(counts.values()),
    }


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _metadata_text(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}
    tags = metadata.get("tags") or []
    if isinstance(tags, list):
        tags_text = " ".join(str(tag) for tag in tags)
    else:
        tags_text = str(tags)
    return " ".join(
        [
            str(item.get("id", "")),
            str(item.get("title", "")),
            str(metadata.get("category", "")),
            tags_text,
        ]
    )


def _detect_collection(query: str) -> tuple[str | None, dict[str, int]]:
    normalized = _normalize(query)
    scores: dict[str, int] = {}
    for collection, keywords in COLLECTION_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            key = keyword.lower()
            if key and key in normalized:
                score += 3 if len(key) >= 3 else 2
        scores[collection] = score
    best_collection = max(scores, key=scores.get) if scores else None
    if best_collection and scores[best_collection] > 0:
        return best_collection, scores
    return None, scores


def _query_terms(query: str) -> list[str]:
    normalized = _normalize(query)
    terms: set[str] = set(re.findall(r"[a-zA-Z0-9]+", normalized))
    for keywords in COLLECTION_KEYWORDS.values():
        for keyword in keywords:
            key = keyword.lower()
            if key and key in normalized:
                terms.add(key)

    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    for chunk in chinese_chunks:
        if len(chunk) <= 6:
            terms.add(chunk)
        for size in (2, 3, 4):
            if len(chunk) >= size:
                for index in range(0, len(chunk) - size + 1):
                    terms.add(chunk[index:index + size])

    stop_terms = {"怎么", "什么", "需要", "可以", "一下", "这个", "那个", "如果", "员工"}
    return sorted(term for term in terms if len(term) >= 2 and term not in stop_terms)


def _score_item(
    query: str,
    item: dict[str, Any],
    collection: str,
    detected_collection: str | None,
    terms: list[str],
) -> int:
    title = _normalize(item.get("title"))
    text = _normalize(item.get("text"))
    metadata = _normalize(_metadata_text(item))
    score = 0

    if detected_collection == collection:
        score += 8
    if title and (title in _normalize(query) or _normalize(query) in title):
        score += 12

    for term in terms:
        if term in title:
            score += 8
        if term in metadata:
            score += 6
        if term in text:
            score += 2

    return score


def retrieve(query: str, max_hits: int = 4) -> dict[str, Any]:
    data = _load_knowledge_base()
    detected_collection, category_scores = _detect_collection(query)
    terms = _query_terms(query)
    hits: list[dict[str, Any]] = []

    for collection, items in (data.get("collections") or {}).items():
        for item in items or []:
            score = _score_item(query, item, collection, detected_collection, terms)
            if score <= 0:
                continue
            hits.append(
                {
                    "collection": collection,
                    "collection_label": COLLECTION_LABELS.get(collection, collection),
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "text": item.get("text"),
                    "metadata": item.get("metadata") or {},
                    "score": score,
                }
            )

    hits.sort(key=lambda item: item["score"], reverse=True)
    top_hits = hits[:max_hits]
    top_score = top_hits[0]["score"] if top_hits else 0
    matched = bool(top_hits and (top_score >= 10 or detected_collection))
    context = build_context(top_hits) if matched else ""

    return {
        "matched": matched,
        "detected_collection": detected_collection,
        "detected_label": COLLECTION_LABELS.get(detected_collection or "", ""),
        "category_scores": category_scores,
        "query_terms": terms,
        "top_score": top_score,
        "hits": top_hits,
        "context": context,
        "sources": [
            {
                "id": hit["id"],
                "title": hit["title"],
                "collection": hit["collection"],
                "collection_label": hit["collection_label"],
            }
            for hit in top_hits
        ],
    }


def build_context(hits: list[dict[str, Any]]) -> str:
    sections = []
    for index, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata") or {}
        tags = metadata.get("tags") or []
        tags_text = "、".join(tags) if isinstance(tags, list) else str(tags)
        sections.append(
            "\n".join(
                [
                    f"[来源{index}] {hit.get('title')}（{hit.get('id')}）",
                    f"集合：{hit.get('collection_label')}",
                    f"标签：{tags_text}",
                    f"内容：{hit.get('text')}",
                ]
            )
        )
    return "\n\n".join(sections)


def build_fallback_answer(query: str, retrieval: dict[str, Any]) -> str:
    hits = retrieval.get("hits") or []
    if not hits:
        return "我暂时没有在企业知识库里找到足够匹配的内容，建议补充问题细节或提交人工工单。"

    lines = [
        "我先根据企业知识库给你一个直接答复：",
        "",
        hits[0].get("text", ""),
    ]
    if len(hits) > 1:
        lines.extend(["", "相关参考："])
        for hit in hits[1:3]:
            lines.append(f"- {hit.get('title')}：{hit.get('text')}")
    lines.extend(["", "知识库来源："])
    for source in retrieval.get("sources") or []:
        lines.append(f"- {source['title']}（{source['id']}，{source['collection_label']}）")
    return "\n".join(lines)
