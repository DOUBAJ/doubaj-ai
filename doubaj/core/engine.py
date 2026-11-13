"""Conversation engine: builds the prompt (system instructions, memory, project knowledge,
attachments, web results), trims history to the context budget and post-processes answers
(file generation, memory suggestions). Provider-independent."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..documents.generator import PPTX_SCHEMA, XLSX_SCHEMA
from ..documents.reader import read_file
from ..providers.base import ChatMessage, ChatRequest

MEMORY_BLOCK = re.compile(r"^(`{3,})doubaj-memory\s*\n(.*?)\n\1[ \t]*$", re.S | re.M)

LANG_NAMES = {"ar": "Arabic", "fr": "French", "en": "English"}

MODES = {
    "general": "",
    "education": (
        "EDUCATION MODE: you assist a teacher (Moroccan / francophone context is common). Produce lesson "
        "plans (fiches pédagogiques / جذاذات), exercises with corrections, tests, summaries, mind maps "
        "(as nested lists or Mermaid), technical diagrams and activities. Respect the official programme and "
        "uploaded sources; never invent data that is not in the sources - say when information is missing."),
    "code": (
        "CODE MODE: act as a senior software engineer. Analyse the request, list the features, choose the "
        "technology, design the project structure, then write complete, runnable files (no placeholders). "
        "Explain how to run and test. For multi-file projects, emit each file as a doubaj-file block whose "
        "name includes the project folder, e.g. name=\"gestion_notes/main.py\"; the app zips the folder."),
}


def build_system_prompt(*, provider_label: str, model: str, ui_lang: str, mode: str, reasoning: str,
                        memories: list[str], project: dict | None, length: str) -> str:
    parts = [
        "You are DOUBAJ AI, a desktop AI assistant application created by Doubaj Ahmed "
        "(teacher of industrial technology). "
        f"The application is currently connected to the model '{model}' provided by {provider_label}. "
        "If asked which model you are, say so honestly: DOUBAJ AI is the application, the language model "
        "comes from that provider. Never claim DOUBAJ AI owns its own model.",
        f"Reply in the language the user writes in (interface language: {LANG_NAMES.get(ui_lang, 'English')}). "
        "Use Markdown: headings, lists, tables, fenced code blocks with a language tag, and LaTeX with $...$ "
        "for formulas. Be accurate and structured; say clearly when you are unsure, and separate confirmed "
        "facts from hypotheses.",
        "When the user's question is about attached documents, base your answer on them and cite the "
        "location, e.g. (source: cours.pdf, page 3) or (slide 4) or (§12), using the markers present in the "
        "document text such as [Page 3], [Slide 4], [§12], [Sheet: X].",
        f"""FILE CREATION - when the user asks for a file (Word, PDF, PowerPoint, Excel, CSV, HTML, Markdown, TXT,
code, project), you MUST produce a real file by writing a block fenced with FOUR backticks:

````doubaj-file name="filename.ext"
...content...
````

Content rules by type:
- .docx / .pdf / .md / .html : complete Markdown (headings, lists, tables, **bold**). Write the full document.
- .pptx : JSON exactly like {PPTX_SCHEMA}
  Aim for 8-15 slides with rich content; use tables, charts, diagrams, notes and exercises when relevant.
- .xlsx : JSON exactly like {XLSX_SCHEMA}  (Excel formulas allowed as strings starting with '=').
- .csv / .txt / code files : the raw content.
- Multi-file projects: one block per file, name="project_folder/path/file.ext" (the app creates a ZIP).
The application converts each block into the real file and shows a download button; outside the blocks,
briefly describe what you produced. Do not tell the user you cannot create files.""",
        "If the user asks you to remember something, or shares a lasting preference, propose it as:\n"
        "````doubaj-memory\n<one short fact>\n````\nThe user will be asked to approve it. Never store passwords, "
        "keys, health or other sensitive data.",
    ]
    if reasoning == "fast":
        parts.append("RESPONSE MODE: quick answer - be concise and direct.")
    elif reasoning == "deep":
        parts.append("RESPONSE MODE: deep analysis - reason step by step, examine alternatives, verify "
                     "calculations and give a thorough, well-structured answer.")
    if length == "short":
        parts.append("Keep answers short unless a file is requested.")
    elif length == "long":
        parts.append("Give detailed, comprehensive answers.")
    if MODES.get(mode):
        parts.append(MODES[mode])
    if memories:
        parts.append("USER MEMORY (facts the user allowed you to remember):\n" + "\n".join(f"- {m}" for m in memories))
    if project:
        parts.append(f"ACTIVE PROJECT: {project['name']}\nDescription: {project.get('description', '')}\n"
                     f"Project instructions (follow them): {project.get('instructions', '')}")
    return "\n\n".join(p for p in parts if p)


# ------------------------------------------------------------------ simple retrieval
_WORD = re.compile(r"\w{3,}", re.U)


def _chunks(text: str, size: int = 1800) -> list[str]:
    """Split on page/slide markers first, then by size."""
    pieces = re.split(r"(?=\[(?:Page|Slide|Sheet)[^\]]*\])", text)
    out = []
    for p in pieces:
        while len(p) > size:
            cut = p.rfind("\n", 0, size)
            cut = cut if cut > size // 2 else size
            out.append(p[:cut])
            p = p[cut:]
        if p.strip():
            out.append(p)
    return out


def retrieve(query: str, docs: list[tuple[str, str]], budget_chars: int) -> str:
    """docs: [(name, text)]. If everything fits, return it all; else BM25-like top chunks."""
    total = sum(len(t) for _, t in docs)
    if total <= budget_chars:
        return "\n\n".join(f"=== DOCUMENT: {n} ===\n{t}" for n, t in docs)
    q = Counter(w.lower() for w in _WORD.findall(query))
    chunks = [(n, c) for n, t in docs for c in _chunks(t)]
    df = Counter()
    toks = []
    for _, c in chunks:
        tc = Counter(w.lower() for w in _WORD.findall(c))
        toks.append(tc)
        df.update(tc.keys())
    N = len(chunks)
    scored = []
    for idx, tc in enumerate(toks):
        s = sum((math.log(1 + N / (1 + df[w])) * tc[w] / (tc[w] + 1.2)) for w in q if w in tc)
        scored.append((s, idx))
    scored.sort(reverse=True)
    picked, used = [], 0
    for s, idx in scored:
        n, c = chunks[idx]
        if used + len(c) > budget_chars:
            continue
        picked.append((idx, n, c))
        used += len(c)
    picked.sort()
    return ("NOTE: documents are large; only the most relevant excerpts are included.\n\n" +
            "\n\n".join(f"=== EXCERPT from {n} ===\n{c}" for _, n, c in picked))


# ------------------------------------------------------------------ request building
@dataclass
class Attachment:
    name: str
    path: str
    kind: str
    text: str = ""
    images: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_path(cls, path: str) -> "Attachment":
        r = read_file(path)
        return cls(name=r.name, path=str(path), kind=r.kind, text=r.text, images=r.images, warnings=r.warnings)

    def to_record(self) -> dict:
        return {"name": self.name, "path": self.path, "kind": self.kind, "text": self.text,
                "n_images": len(self.images), "warnings": self.warnings}


def _images_for_record(rec: dict) -> list[dict]:
    if not rec.get("n_images"):
        return []
    p = Path(rec.get("path", ""))
    if not p.exists():
        return []
    return read_file(p).images


def build_request(*, model: str, system: str, history: list[dict], reasoning: str, max_tokens: int,
                  temperature: float | None, context_chars: int, project_docs: list[tuple[str, str]],
                  web_context: str = "", send_images: bool = True) -> ChatRequest:
    """history: DB message rows (role, content, attachments). The last row is the new user message."""
    msgs: list[ChatMessage] = []
    last_user_text = history[-1]["content"] if history else ""
    doc_budget = int(context_chars * 0.5)

    if project_docs:
        system += "\n\nPROJECT REFERENCE DOCUMENTS:\n" + retrieve(last_user_text, project_docs, doc_budget // 2)

    for i, row in enumerate(history):
        text = row["content"]
        images: list[dict] = []
        atts = row.get("attachments") or []
        if row["role"] == "user" and atts:
            docs = [(a["name"], a.get("text", "")) for a in atts if a.get("text")]
            if docs:
                text = ("ATTACHED DOCUMENTS:\n" + retrieve(text, docs, doc_budget) + "\n\n---\nUSER MESSAGE:\n" + text)
            if send_images:
                for a in atts:
                    images.extend(_images_for_record(a))
        if i == len(history) - 1 and web_context:
            text = web_context + "\n\n---\nUSER MESSAGE:\n" + text
        msgs.append(ChatMessage(row["role"], text, images[:20]))

    # Trim oldest turns to respect the context budget (keep the last message intact).
    def size(ms):
        return sum(len(m.text) for m in ms) + len(system)
    while len(msgs) > 1 and size(msgs) > context_chars:
        msgs.pop(0)
    while msgs and msgs[0].role != "user":
        msgs.pop(0)
    # merge consecutive same-role messages (some APIs require alternation)
    merged: list[ChatMessage] = []
    for m in msgs:
        if merged and merged[-1].role == m.role:
            merged[-1].text += "\n\n" + m.text
            merged[-1].images += m.images
        else:
            merged.append(ChatMessage(m.role, m.text, list(m.images)))
    return ChatRequest(model=model, system=system, messages=merged, reasoning=reasoning,
                       temperature=temperature, max_tokens=max_tokens)


def extract_memories(answer: str) -> list[str]:
    return [m.strip() for _, m in MEMORY_BLOCK.findall(answer) if m.strip()]


def strip_memory_blocks(answer: str) -> str:
    return MEMORY_BLOCK.sub("", answer)


def auto_title(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return (t[:48] + "…") if len(t) > 50 else (t or "Nouvelle conversation")
