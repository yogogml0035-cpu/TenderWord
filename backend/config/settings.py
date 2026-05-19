"""Pydantic Settings 配置模块.

使用 Pydantic Settings v2 管理环境变量配置.
支持从 backend/.env 文件加载配置.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
BACKEND_ENV_FILE = BACKEND_DIR / ".env"
BACKEND_ENV_EXAMPLE_FILE = BACKEND_DIR / ".env.example"
ENV_FILES = (BACKEND_ENV_FILE,)
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


class Settings(BaseSettings):
    """应用配置类.

    所有配置项都有默认值，可通过环境变量覆盖.
    环境变量名称与类属性名称完全一致（大写）.
    """

    model_config = SettingsConfigDict(
        env_file=[str(p) for p in ENV_FILES],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # 忽略未定义的额外环境变量
    )

    # ========================================
    # 应用基础配置
    # ========================================
    APP_NAME: str = Field(default="TenderWord API", description="应用名称")
    APP_VERSION: str = Field(default="1.0.0", description="应用版本")
    DEBUG: bool = Field(default=False, description="调试模式")

    # 服务器配置
    HOST: str = Field(default="0.0.0.0", description="服务器绑定地址")
    PORT: int = Field(default=8000, description="服务器端口")

    # CORS 配置
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:8502",
            "http://127.0.0.1:8502"
        ],
        description="允许的 CORS 来源",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="允许 CORS 凭证")
    CORS_ALLOW_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="允许的 HTTP 方法",
    )
    CORS_ALLOW_HEADERS: List[str] = Field(
        default=[
            "*",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Accept",
            "Origin",
            "Cache-Control",
            "Last-Event-ID",  # SSE 必需
            "X-Accel-Buffering",  # SSE 代理缓冲控制
        ],
        description="允许的 HTTP 头",
    )

    # ========================================
    # LLM 提供商配置 - DeepSeek
    # ========================================
    DEEPSEEK_BASE_URL: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API 基础 URL",
    )
    DEEPSEEK_API_KEY: Optional[str] = Field(
        default=None,
        description="DeepSeek API 密钥",
    )
    DEEPSEEK_MODEL: str = Field(
        default=DEFAULT_DEEPSEEK_MODEL,
        description="DeepSeek 默认模型",
    )

    # ========================================
    # LLM 提供商配置 - Doubao (ARK)
    # ========================================
    ARK_BASE_URL: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        description="ARK (Doubao) API 基础 URL",
    )
    ARK_API_KEY: Optional[str] = Field(
        default=None,
        description="ARK API 密钥",
    )
    DOUBAO_MODEL: str = Field(
        default="doubao-seed-1-6-251015",
        description="Doubao 默认模型",
    )

    # ========================================
    # LLM 提供商配置 - Qwen (DashScope)
    # ========================================
    DASHSCOPE_BASE_URL: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="DashScope API 基础 URL",
    )
    DASHSCOPE_API_KEY: Optional[str] = Field(
        default=None,
        description="DashScope API 密钥",
    )
    QWEN_MODEL: str = Field(
        default="qwen-plus",
        description="Qwen 默认模型",
    )
    LLM_STREAM_TIMEOUT_SECONDS: int = Field(
        default=20,
        description="LLM 流式响应超时时间（秒）",
    )

    # ========================================
    # LangFuse 配置（可选）
    # ========================================
    LANGSMITH_TRACING: str = Field(default="false", description="LangSmith 追踪开关")
    LANGFUSE_SECRET_KEY: Optional[str] = Field(
        default=None, description="LangFuse 密钥"
    )
    LANGFUSE_PUBLIC_KEY: Optional[str] = Field(
        default=None, description="LangFuse 公钥"
    )
    LANGFUSE_BASE_URL: Optional[str] = Field(
        default=None, description="LangFuse 基础 URL"
    )

    # ========================================
    # 文件上传配置
    # ========================================
    UPLOAD_DIR: str = Field(
        default="D:/UploadFiles",
        description="文件上传目录",
    )
    MAX_UPLOAD_SIZE: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        description="最大上传文件大小（字节）",
    )
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".docx", ".doc", ".pdf", ".txt", ".xlsx", ".xls"],
        description="允许上传的文件扩展名",
    )
    TEMPLATE_CANDIDATE_API_URL: str = Field(
        default="http://dserp.dongsong-cn.com/dongsong/servlet/tender.TenderJsonActionMb",
        description="模板候选列表外部接口地址",
    )
    TENDER_DATA_API_URL: str = Field(
        default="http://dserp.dongsong-cn.com/dongsong//servlet/tender.TenderJsonAction",
        description="招标详情外部接口地址",
    )
    TEMPLATE_CANDIDATE_ALLOWED_HOSTS: List[str] = Field(
        default=["10.11.0.213", "10.11.1.224"],
        description="模板候选下载允许访问的外部主机",
    )
    EXTERNAL_REQUEST_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        description="外部 HTTP 请求超时时间（秒）",
    )
    TEMPLATE_CANDIDATE_RANKING_LLM_PROVIDER: str = Field(
        default="deepseek",
        description="模板候选 AI 排序使用的模型提供商",
    )

    # ========================================
    # 并发锁配置
    # ========================================
    LOCK_FILE_PATH: Optional[str] = Field(
        default=None,
        description="跨进程锁文件路径，默认使用系统临时目录",
    )
    LOCK_TIMEOUT: float = Field(
        default=600.0,
        description="锁获取超时时间（秒）",
    )
    LOCK_WAIT_TIMEOUT: float = Field(
        default=1200.0,
        description="等待锁超时时间（秒）",
    )

    # ========================================
    # 日志配置
    # ========================================
    LOG_DIR: str = Field(default="logs", description="日志目录（相对于backend目录）")
    LOG_QUEUE_MAXSIZE: int = Field(default=10000, description="日志队列最大容量")
    PROGRESS_LOG_BACKUP_COUNT: int = Field(default=7, description="进度日志保留天数")
    EXECUTION_LOG_BACKUP_COUNT: int = Field(default=30, description="执行日志保留天数")
    LOG_ROTATION_WHEN: str = Field(default="midnight", description="日志轮转时间")
    LOG_CLEANUP_MAX_MB: int = Field(default=200, description="日志清理最大容量（MB）")

    # ========================================
    # SSE 配置
    # ========================================
    SSE_MAX_EVENTS_PER_TASK: int = Field(
        default=1000, description="每个任务最大 SSE 事件数"
    )
    SSE_EVENT_TTL: int = Field(default=3600, description="SSE 事件 TTL（秒）")
    SSE_HEARTBEAT_INTERVAL: int = Field(default=15, description="SSE 心跳间隔（秒）")

    # ========================================
    # 任务队列配置
    # ========================================
    TASK_TOTAL_NODES: int = Field(default=7, description="任务总节点数，用于进度计算")
    TASK_HEARTBEAT_TIMEOUT: int = Field(default=15, description="任务心跳超时（秒）")
    TASK_CLEANUP_INTERVAL: int = Field(default=5, description="任务清理间隔（秒）")

    @property
    def langsmith_tracing_enabled(self) -> bool:
        """检查是否启用 LangSmith 追踪."""
        return self.LANGSMITH_TRACING.lower() in ("true", "1", "yes", "on")

    def get_llm_config(self, provider: str = "deepseek") -> dict:
        """获取指定 LLM 提供商的配置.

        Args:
            provider: 提供商名称 (deepseek, doubao, qwen)

        Returns:
            包含 base_url, api_key, model 的字典
        """
        configs = {
            "deepseek": {
                "base_url": self.DEEPSEEK_BASE_URL,
                "api_key": self.DEEPSEEK_API_KEY,
                "model": self.DEEPSEEK_MODEL,
            },
            "doubao": {
                "base_url": self.ARK_BASE_URL,
                "api_key": self.ARK_API_KEY,
                "model": self.DOUBAO_MODEL,
            },
            "qwen": {
                "base_url": self.DASHSCOPE_BASE_URL,
                "api_key": self.DASHSCOPE_API_KEY,
                "model": self.QWEN_MODEL,
            },
        }
        return configs.get(provider, configs["deepseek"])


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例模式）.

    使用 lru_cache 确保配置只加载一次，提高性能.

    Returns:
        Settings 配置实例
    """
    return Settings()


# 导出配置实例供直接使用
settings = get_settings()
