import tiktoken
from bs4 import BeautifulSoup
from markdownify import markdownify

enc = tiktoken.get_encoding("cl100k_base")


def parse(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["nav", "footer", "script", "style", "header"]):
        tag.decompose()
    return markdownify(str(soup.body), heading_style="ATX")


def chunk(text: str, max_tokens: int = 500) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current, count = [], [], 0
    for para in paragraphs:
        tokens = enc.encode(para)
        n = len(tokens)
        if n > max_tokens:
            if current:
                chunks.append("\n\n".join(current))
                current, count = [], 0
            for i in range(0, n, max_tokens):
                chunks.append(enc.decode(tokens[i:i + max_tokens]))
            continue
        if count + n > max_tokens and current:
            chunks.append("\n\n".join(current))
            current, count = [], 0
        current.append(para)
        count += n
    if current:
        chunks.append("\n\n".join(current))
    return chunks
