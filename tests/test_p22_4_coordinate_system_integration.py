"""
P22.4 CoordinateSystem v1 — B.2 集成测试 (静态契约 + server smoke)

检查 B.2 接入是否完整:
  1. index.html script tag 包含 coordinate-system.js?v= 在 app.js?v= 之前
  2. server.py 有 /coordinate-system.js route
  3. app.js 顶部有 const cs = new window.CoordinateSystem();
  4. app.js renderSingleNotationSafe 末尾有 cs.updateLayout (单谱)
  5. app.js renderPianoNotation 末尾有 cs.updateLayout (双谱, 含 treble/bass geometry)
  6. app.js handleRenderError 有 cs.clearLayout
  7. server 200 OK on /coordinate-system.js
  8. /coordinate-system.js 返回内容包含 window.CoordinateSystem 暴露
  9. cs 集成后 P22.3 旧测试无回归 (test_*.py 全部仍 pass)
"""

import os
import re
import unittest

from fastapi.testclient import TestClient

import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "web", "app.js")
INDEX_HTML = os.path.join(ROOT, "web", "index.html")
SERVER_PY = os.path.join(ROOT, "server.py")
CS_JS = os.path.join(ROOT, "web", "coordinate-system.js")
CLIENT = TestClient(server.app)


def _read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _http_get(path):
    """GET one app route and return (status_code, body_str).
    第一次 GET 偶尔会因 server 刚启动 / chunked encoding 返回不完整 body; retry 一次保稳.
    """
    response = CLIENT.get(path)
    return response.status_code, response.content.decode("utf-8", errors="replace")


class TestIndexHtmlScriptOrder(unittest.TestCase):
    """index.html 必须先加载 cs 再加载 app.js"""

    def test_index_html_loads_cs_before_app(self):
        html = _read(INDEX_HTML)
        cs_idx = html.find("coordinate-system.js")
        app_idx = html.find("app.js?v=")
        self.assertGreater(cs_idx, 0, "coordinate-system.js not found in index.html")
        self.assertGreater(app_idx, 0, "app.js?v= not found in index.html")
        self.assertLess(cs_idx, app_idx,
            f"coordinate-system.js must load BEFORE app.js (cs@{cs_idx}, app@{app_idx})")

    def test_cs_has_cache_bust(self):
        html = _read(INDEX_HTML)
        self.assertRegex(html, r"coordinate-system\.js\?v=\S+",
            "coordinate-system.js must have cache-bust ?v=...")

    def test_app_js_has_cache_bust(self):
        html = _read(INDEX_HTML)
        self.assertRegex(html, r"app\.js\?v=\S+",
            "app.js must have cache-bust ?v=...")


class TestServerPyRoute(unittest.TestCase):
    """server.py 必须有 /coordinate-system.js route"""

    def test_server_py_has_coordinate_route(self):
        py = _read(SERVER_PY)
        self.assertIn("/coordinate-system.js", py,
            "server.py must have /coordinate-system.js route")
        # 应在 @app.get 装饰器下
        self.assertRegex(py, r'@app\.get\("/coordinate-system\.js"\)',
            "Must be a proper @app.get route")

    def test_server_py_route_returns_file_response(self):
        py = _read(SERVER_PY)
        # 找包含 /coordinate-system.js 的 root_* function
        m = re.search(
            r'@app\.get\("/coordinate-system\.js"\)\s*\n\s*def\s+(\w+)\([^)]*\)\s*->\s*FileResponse:\s*\n\s*return\s+FileResponse\(WEB_DIR\s*/\s*"coordinate-system\.js"\)',
            py
        )
        self.assertIsNotNone(m, "Route handler must return FileResponse(WEB_DIR / 'coordinate-system.js')")


class TestAppJSCSConstruction(unittest.TestCase):
    """app.js 顶部必须有 cs 构造 (在 editorState 之后)"""

    def test_app_js_constructs_cs(self):
        js = _read(APP_JS)
        self.assertIn("const cs = new window.CoordinateSystem();", js,
            "app.js must construct: const cs = new window.CoordinateSystem();")

    def test_cs_constructed_after_editor_state(self):
        """cs 必须在 editorState 块之后 (避免 hoisting 问题)"""
        js = _read(APP_JS)
        es_end = js.find("};", js.find("const editorState = {"))
        cs_pos = js.find("const cs = new window.CoordinateSystem();")
        self.assertGreater(es_end, 0, "editorState block not found")
        self.assertGreater(cs_pos, es_end, "cs must be constructed after editorState block")


class TestAppJSRenderHooks(unittest.TestCase):
    """app.js render 末尾必须调 cs.updateLayout (单谱 + 双谱)"""

    def test_renderSingleNotationSafe_calls_updateLayout(self):
        js = _read(APP_JS)
        # 找 renderSingleNotationSafe 函数 body
        m = re.search(r"function\s+renderSingleNotationSafe\s*\(\s*\)\s*\{([\s\S]*?)\n\}\s*\n", js)
        self.assertIsNotNone(m, "renderSingleNotationSafe not found")
        body = m.group(1)
        self.assertIn("cs.updateLayout", body, "renderSingleNotationSafe must call cs.updateLayout")
        # 必须传 staffGeometry + measureRects + currentMeasureIndex + timeSignature
        for field in ["staffGeometry", "measureRects", "currentMeasureIndex", "timeSignature"]:
            self.assertIn(field, body, f"renderSingleNotationSafe updateLayout must pass {field}")

    def test_renderPianoNotation_calls_updateLayout(self):
        js = _read(APP_JS)
        m = re.search(r"function\s+renderPianoNotation\s*\(\s*\)\s*\{([\s\S]*?)\n\}\s*\n", js)
        self.assertIsNotNone(m, "renderPianoNotation not found")
        body = m.group(1)
        self.assertIn("cs.updateLayout", body, "renderPianoNotation must call cs.updateLayout")
        # 双谱模式必须传 trebleGeometry + bassGeometry
        for field in ["trebleGeometry", "bassGeometry", "staffGeometry", "measureRects"]:
            self.assertIn(field, body, f"renderPianoNotation updateLayout must pass {field}")


class TestAppJSClearLayoutHook(unittest.TestCase):
    """app.js handleRenderError 必须调 cs.clearLayout"""

    def test_handleRenderError_calls_clearLayout(self):
        js = _read(APP_JS)
        m = re.search(r"function\s+handleRenderError\s*\([^)]*\)\s*\{([\s\S]*?)\n\}\s*\n", js)
        self.assertIsNotNone(m, "handleRenderError not found")
        body = m.group(1)
        self.assertIn("cs.clearLayout", body, "handleRenderError must call cs.clearLayout")


class TestAppJSCSGuardedCalls(unittest.TestCase):
    """cs.* 调用必须用 typeof 守卫 (防 cs 还没初始化时调用)"""

    def test_cs_calls_guarded(self):
        js = _read(APP_JS)
        # 找所有 cs. 调用 (排除注释行 + 字符串)
        for m in re.finditer(r"(cs\.(?:updateLayout|clearLayout))\b", js):
            line_start = js.rfind("\n", 0, m.start()) + 1
            line = js[line_start:js.find("\n", m.end())]
            # 跳过注释行
            if line.lstrip().startswith("//"):
                continue
            # 取调用前 200 字符
            before = js[max(0, m.start() - 200):m.start()]
            self.assertIn("typeof cs", before,
                f"cs call '{m.group(0)}' must be guarded with 'typeof cs' (P22.4-B.2: 防 cs 加载失败时崩)\nLINE: {line}")


class TestServerSmoke(unittest.TestCase):
    """Server 实际响应 (smoke test)"""

    def test_cs_served_at_200(self):
        status, body = _http_get("/coordinate-system.js")
        self.assertEqual(status, 200, f"/coordinate-system.js returned {status}: {body[:200]}")

    def test_cs_body_size_matches_file(self):
        """server 字节数 == 文件字节数 (body 是 str, 用 encode('utf-8') 取字节数)"""
        status, body = _http_get("/coordinate-system.js")
        self.assertEqual(status, 200)
        body_bytes = body.encode("utf-8")
        file_bytes = os.path.getsize(CS_JS)
        self.assertEqual(len(body_bytes), file_bytes,
            f"server bytes {len(body_bytes)} != file bytes {file_bytes} (str len {len(body)})")

    def test_cs_body_contains_window_export(self):
        status, body = _http_get("/coordinate-system.js")
        self.assertEqual(status, 200)
        self.assertIn("window.CoordinateSystem", body, "cs must export to window.CoordinateSystem")

    def test_app_js_also_served(self):
        """app.js 仍正常服务"""
        status, _ = _http_get("/app.js")
        self.assertEqual(status, 200)

    def test_health_still_200(self):
        status, _ = _http_get("/health")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
