"""Mock OpenAI-compatible and Anthropic streaming servers for offline tests."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPLY = None  # set by tests


def default_reply(body):
    last = body["messages"][-1]["content"]
    if isinstance(last, list):
        last = " ".join(p.get("text", "") for p in last if isinstance(p, dict))
    return f"Réponse **test**. Vous avez dit : {last[-60:]}"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.endswith("/models"):
            if "anthropic" in self.path or self.headers.get("x-api-key"):
                return self._json({"data": [{"id": "claude-opus-5-5", "type": "model", "display_name": "x", "created_at": "2026-01-01T00:00:00Z"}],
                                   "has_more": False, "first_id": "a", "last_id": "a"})
            return self._json({"object": "list", "data": [{"id": "mock-model", "object": "model", "created": 0, "owned_by": "me"}]})
        self._json({}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        H.last_body = body
        text = (REPLY or default_reply)(body)
        pieces = [text[i:i + 12] for i in range(0, len(text), 12)]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if self.path.endswith("/chat/completions"):
            for p in pieces:
                chunk = {"id": "1", "object": "chat.completion.chunk", "created": 0, "model": body["model"],
                         "choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.005)
            self.wfile.write(b"data: [DONE]\n\n")
        elif self.path.endswith("/messages"):
            def ev(name, data):
                self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
                self.wfile.flush()
            ev("message_start", {"type": "message_start", "message": {"id": "m1", "type": "message", "role": "assistant",
                 "model": body["model"], "content": [], "stop_reason": None, "stop_sequence": None,
                 "usage": {"input_tokens": 11, "output_tokens": 0}}})
            ev("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
            for p in pieces:
                ev("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": p}})
            ev("content_block_stop", {"type": "content_block_stop", "index": 0})
            ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                 "usage": {"output_tokens": 42}})
            ev("message_stop", {"type": "message_stop"})


H.last_body = None


def start(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
