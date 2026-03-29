"""Web crawler package."""

from .crawler import Crawler
from .models import ErrorType, PageResult

__all__ = ["Crawler", "ErrorType", "PageResult"]
