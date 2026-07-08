from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME, INTENT_PROMPT_TEMPLATE

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

def detect_intent_code(query):
    prompt = INTENT_PROMPT_TEMPLATE.format(query=query)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一个意图识别助手，只返回数字编号。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )
        result = response.choices[0].message.content.strip()
        if result in ["1", "2", "3", "4", "5", "6"]:
            return int(result)
        return 6
    except Exception as e:
        print(f"意图识别错误: {e}")
        return 6
