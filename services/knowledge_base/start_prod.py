"""
SeaChat 生产环境启动脚本
特点：多进程，适合正式使用，支持几十人并发
"""
import os
import subprocess
import sys
import multiprocessing

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    workers = int(os.getenv("WORKERS", min(4, multiprocessing.cpu_count())))
    threads = int(os.getenv("THREADS", 4))

    print("=" * 50)
    print("SeaChat 生产环境启动")
    print(f"端口: {port}")
    print(f"Workers: {workers}")
    print(f"Threads: {threads}")
    print(f"并发能力: {workers * threads} 个并发请求")
    print("访问: http://127.0.0.1:5000")
    print("特点: 多进程多线程，适合正式使用")
    print("=" * 50)

    # Windows 下使用 gunicorn 命令
    if sys.platform == 'win32':
        # Windows 不支持 gunicorn，使用 waitress 作为替代
        try:
            from waitress import serve
            from app import app
            from database import init_database
            from vector_store import init_knowledge_base

            init_database()
            init_knowledge_base()

            print("使用 waitress 服务器（Windows 兼容）")
            serve(app, host='0.0.0.0', port=port, threads=threads)
        except ImportError:
            print("请安装 waitress: pip install waitress")
            print("或使用开发环境: python start_dev.py")
    else:
        # Linux/Mac 使用 gunicorn
        from app import app
        from database import init_database
        from vector_store import init_knowledge_base

        init_database()
        init_knowledge_base()

        cmd = [
            sys.executable, "-m", "gunicorn",
            "--bind", f"0.0.0.0:{port}",
            "--workers", str(workers),
            "--threads", str(threads),
            "--timeout", "120",
            "app:app"
        ]
        subprocess.run(cmd)
