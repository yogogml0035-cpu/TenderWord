"""
Base State module for the project refactoring.

This module defines the BaseState TypedDict that all specific state classes
will inherit from. It provides common fields that all graphs need.
"""

from typing import TypedDict


class BaseState(TypedDict, total=False):
    """
    基础 State 类，定义所有 graph 共享的字段
    
    使用 total=False 允许字段可选，提高灵活性。
    所有具体的 state 类都应该继承此类以获得通用字段。
    
    字段说明：
        task_id: 任务ID，用于进度追踪和取消
        user_session_id: 用户会话ID，用于多用户隔离
        tender_type: 招标类型标识符（"xjcg"、"gngk" 等）
    
    使用示例：
        class MyGraphState(BaseState):
            # 添加特定字段
            my_field: str
            another_field: int
    """
    # 任务标识
    task_id: str                    # 任务ID，用于进度追踪和取消
    user_session_id: str            # 用户会话ID，用于多用户隔离
    tender_type: str                # 招标类型标识符（"xjcg"、"gngk" 等）
