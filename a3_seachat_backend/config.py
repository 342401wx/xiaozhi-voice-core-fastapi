import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "MiMo-V2.5")

DATABASE_PATH = os.getenv("DATABASE_PATH", "seachat.db")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./chroma_db")

# Redis 配置
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "300"))  # 缓存过期时间 5 分钟

INTENT_PROMPT_TEMPLATE = """
你是一个意图识别助手。根据用户的输入，判断用户的意图编号。

意图编号说明：
1. 网络搜索 - 用户要求查询今天、最新、实时、新闻、热点、网上资料、外部网页、图片或当前公开信息
2. IT服务支持 - 用户询问账号权限、密码、VPN、邮箱、办公设备、软件安装、网络故障、数据备份、信息安全等问题
3. HR人事政策 - 用户询问入职、试用期、考勤、请假、薪资、绩效、培训、离职交接等问题
4. 行政办公服务 - 用户询问门禁、会议室、办公资产、差旅预订、快递、访客、办公环境报修、应急事件等问题
5. 财务报销制度 - 用户询问报销流程、发票、差旅报销、业务招待费、采购付款、预算、报销时效等问题
6. 其他 - 不属于以上五类的其他问题

用户输入：{query}

请只返回意图编号（1、2、3、4、5或6），不要返回其他内容。
"""

RESPONSE_PROMPT_TEMPLATE = """
你是SeaChat企业内部服务台智能客服助手。根据以下信息回答员工的问题。

用户问题：{query}
相关知识：{context}
用户历史信息：{user_info}

请用友好、专业、准确的语气回答。优先依据相关知识回答，并在关键结论后尽量引用对应的来源编号，例如“根据来源1”。如果知识库没有明确依据，请说明需要提交工单或转人工处理，不要编造公司政策、价格、审批结果或承诺。
"""
