"""
SeaChat 简单模式启动脚本
特点：最小配置，快速启动
"""
import os
from app import app
from database import init_database
from vector_store import init_knowledge_base

if __name__ == "__main__":
    init_database()
    init_knowledge_base()
    port = int(os.getenv("PORT", "5000"))
    print("=" * 50)
    print("SeaChat 简单模式启动")
    print(f"端口: {port}")
    print("访问: http://127.0.0.1:5000")
    print("特点: 最小配置，快速启动")
    print("=" * 50)
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
