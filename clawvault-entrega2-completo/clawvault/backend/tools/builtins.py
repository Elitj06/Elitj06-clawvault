"""
ClawVault — Built-in tools for Function Calling.

Tools:
- web_fetch: fetch content from a URL
- api_call: generic HTTP requests
- vault_search: search ClawVault knowledge base
- calculator: safe math evaluation
- get_current_time: current date/time
"""

from __future__ import annotations
import ast
import math
import operator
import re
from datetime import datetime, timezone
from typing import Any

from backend.tools.base import Tool


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch and extract readable text content from a URL."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max characters to return", "default": 5000},
        },
        "required": ["url"],
    }

    def execute(self, url: str, max_chars: int = 5000) -> str:
        import requests
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "ClawVault/1.0"})
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            return f"Error fetching URL: {e}"

        # Try BeautifulSoup for HTML → text
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            # Remove scripts/styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        except ImportError:
            # Fallback: crude tag stripping
            text = re.sub(r"<[^>]+>", " ", text)

        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text[:max_chars]


class ApiCallTool(Tool):
    name = "api_call"
    description = "Make an HTTP request to any URL. Supports GET, POST, PUT, DELETE."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to call"},
            "method": {"type": "string", "description": "HTTP method", "default": "GET", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
            "headers": {"type": "object", "description": "Request headers", "default": {}},
            "body": {"type": "string", "description": "Request body (JSON string)", "default": None},
        },
        "required": ["url"],
    }

    def execute(self, url: str, method: str = "GET", headers: dict | None = None, body: str | None = None) -> str:
        import requests
        import json as _json

        hdrs = {"User-Agent": "ClawVault/1.0", "Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)

        kwargs: dict[str, Any] = {"method": method.upper(), "url": url, "headers": hdrs, "timeout": 15}
        if body:
            kwargs["data"] = body

        try:
            resp = requests.request(**kwargs)
            content = resp.text[:5000]
            return f"Status: {resp.status_code}\n{content}"
        except Exception as e:
            return f"Error: {e}"


class VaultSearchTool(Tool):
    name = "vault_search"
    description = "Search the ClawVault knowledge base (vault) for relevant notes and information."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "mode": {"type": "string", "description": "Search mode: keyword, semantic, hybrid", "default": "hybrid", "enum": ["keyword", "semantic", "hybrid"]},
            "limit": {"type": "integer", "description": "Max results", "default": 5},
        },
        "required": ["query"],
    }

    def execute(self, query: str, mode: str = "hybrid", limit: int = 5) -> str:
        try:
            from backend.memory.vault import vault
            results = vault.search(query, limit=limit)
        except Exception as e:
            return f"Error searching vault: {e}"

        if not results:
            return "No results found in vault."

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", r.get("path", "Untitled"))
            snippet = r.get("snippet", r.get("content", ""))[:300]
            lines.append(f"{i}. {title}\n   {snippet}")
        return "\n\n".join(lines)


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a mathematical expression safely. Supports basic arithmetic, trig, log, etc."
    parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression to evaluate (e.g. '2 + 3 * 4', 'sqrt(16)', 'sin(pi/2)')"},
        },
        "required": ["expression"],
    }

    # Safe operators/functions for eval
    _SAFE_NAMES = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow,
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "log2": math.log2,
        "pi": math.pi, "e": math.e,
        "ceil": math.ceil, "floor": math.floor,
    }

    def execute(self, expression: str) -> str:
        # Safety: only allow safe AST nodes
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            return f"Syntax error: {e}"

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call)):
                if isinstance(node, ast.Call):
                    # Allow safe function calls
                    if isinstance(node.func, ast.Name) and node.func.id in self._SAFE_NAMES:
                        continue
                    if isinstance(node.func, ast.Attribute):
                        return "Error: attribute access not allowed"
                    continue
                return "Error: imports not allowed"
            if isinstance(node, ast.Name) and node.id not in self._SAFE_NAMES:
                return f"Error: name '{node.id}' not allowed"

        try:
            result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, self._SAFE_NAMES)
            return str(result)
        except Exception as e:
            return f"Error evaluating: {e}"


class GetCurrentTimeTool(Tool):
    name = "get_current_time"
    description = "Get the current date and time in a specific timezone."
    parameters = {
        "type": "object",
        "properties": {
            "timezone": {"type": "string", "description": "Timezone name (e.g. 'UTC', 'America/Sao_Paulo', 'US/Eastern')", "default": "UTC"},
        },
        "required": [],
    }

    def execute(self, timezone: str = "UTC") -> str:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now(datetime.timezone.utc)
            return f"{now.strftime('%Y-%m-%d %H:%M:%S')} UTC (timezone '{timezone}' not found, using UTC)"

        return now.strftime(f"%Y-%m-%d %H:%M:%S {timezone}")
