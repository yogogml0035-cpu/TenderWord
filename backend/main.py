"""FastAPI 应用主入口.

提供 TenderWord 后端 API 服务，支持 SSE 流式输出.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Fix module import path: add parent directory of backend to sys.path
# This ensures all modules using `from backend.xxx` absolute imports can resolve correctly
_current_file = os.path.abspath(__file__)
_backend_dir = os.path.dirname(_current_file)
_project_root = os.path.dirname(_backend_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config.settings import get_settings, settings

# 导入日志工具
from backend.util.log_util.progress_log import (
    progress_log,
    start_progress_log_listener,
    stop_progress_log_listener,
)
from backend.util.log_util.execution_log import (
    start_execution_log_listener,
    stop_execution_log_listener,
)
from backend.util.log_util.log_cleanup import cleanup_logs
from backend.util.log_util.sse_log_handler import init_sse_log_handler

# 导入 SSE 管理器
from backend.core.sse_manager import sse_manager

# 导入 API 路由
from backend.api.upload import router as upload_router
from backend.api.tender import router as tender_router
from backend.api.tasks import router as tasks_router
from backend.api.stream import router as stream_router
from backend.api.generate import router as generate_router
from backend.api.download import router as download_router


# ========================================
# JSON 日志格式化器
# ========================================
class JSONFormatter(logging.Formatter):
    """JSON 格式的日志格式化器."""

    def format(self, record: logging.LogRecord) -> str:
        """将日志记录格式化为 JSON 字符串."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加额外字段
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外属性
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
                "request_id",
                "user_id",
            }:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """配置 JSON 格式的日志系统."""
    # 根日志器配置
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # 清除现有处理器
    root_logger.handlers = []

    # 标准输出处理器
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    stdout_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(stdout_handler)

    # 第三方库日志级别调整
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ========================================
# FastAPI 应用初始化
# ========================================
def create_application() -> FastAPI:
    """创建并配置 FastAPI 应用实例.

    Returns:
        配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="TenderWord API - 招标文档生成服务",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
    )

    # 配置 CORS 中间件（支持 SSE）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=[
            "X-Request-ID",
            "X-Accel-Buffering",  # 用于控制 Nginx 代理缓冲
            "Cache-Control",
            "Content-Type",
            "Last-Event-ID",  # SSE 必需
        ],
        max_age=600,  # 预检请求缓存 10 分钟
    )

    # 注册 API 路由
    app.include_router(upload_router, prefix="/api")
    app.include_router(tender_router, prefix="/api")
    app.include_router(tasks_router, prefix="/api")
    app.include_router(stream_router, prefix="/api")
    app.include_router(generate_router, prefix="/api")
    app.include_router(download_router, prefix="/api")

    return app


# 创建应用实例
app = create_application()
logger = logging.getLogger(__name__)


# ========================================
# 启动/关闭事件
# ========================================
@app.on_event("startup")
async def startup_event() -> None:
    """应用启动时执行."""
    setup_logging()

    # 启动进度日志监听器
    start_progress_log_listener()

    # 启动执行日志监听器
    start_execution_log_listener()

    # 初始化 SSE 日志 handler 并添加到 progress_log
    sse_handler = init_sse_log_handler(sse_manager)
    progress_log.addHandler(sse_handler)
    # 清理过期日志文件（保持总大小在 200MB 以下）
    try:
        deleted_count = cleanup_logs("backend/logs", max_total_mb=200)
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old log files")
    except Exception as e:
        logger.warning(f"Failed to cleanup logs: {e}")

    logger.info(
        "Application startup",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
            "host": settings.HOST,
            "port": settings.PORT,
            "upload_dir": settings.UPLOAD_DIR,
        },
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """应用关闭时执行."""
    # 停止执行日志监听器
    stop_execution_log_listener()

    # 停止进度日志监听器
    stop_progress_log_listener()

    logger.info("Application shutdown")


# ========================================
# 全局异常处理
# ========================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器."""
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ========================================
# 健康检查端点
# ========================================
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """健康检查端点.

    返回服务运行状态，用于负载均衡和监控检查.

    Returns:
        {"status": "ok", "timestamp": "...", "version": "..."}
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": settings.APP_VERSION,
        "service": settings.APP_NAME,
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check() -> Dict[str, Any]:
    """就绪检查端点.

    检查服务是否准备好接收流量.

    Returns:
        {"ready": true, "checks": {...}}
    """
    checks = {
        "config_loaded": True,
        "upload_dir_accessible": True,  # TODO: 实际检查目录权限
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/health/live", tags=["Health"])
async def liveness_check() -> Dict[str, str]:
    """存活检查端点.

    检查服务是否正在运行.

    Returns:
        {"alive": "true"}
    """
    return {"alive": "true"}


# ========================================
# 根路径
# ========================================
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """根路径端点.

    返回 API 基本信息.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health",
    }


# ========================================
# 主入口
# ========================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None,  # 使用自定义日志配置
    )
