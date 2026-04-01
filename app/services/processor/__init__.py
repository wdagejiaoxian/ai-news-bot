# -*- coding: utf-8 -*-
"""
数据处理器
"""

from app.services.processor.deduplicator import deduplicator
from app.services.processor.scorer import scorer
from app.services.processor.summarizer import summarizer

__all__ = ["deduplicator", "scorer", "summarizer"]
