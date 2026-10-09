import asyncio

import chromadb

from agent import ask_agent

ASK_TIMEOUT_SECONDS = 60


def search_docs(collection: chromadb.Collection, query: str, n_results: int = 5) -> dict:
    effective = min(max(n_results, 1), collection.count())
    if effective == 0:
        return {"results": [], "references": []}
    results = collection.query(query_texts=[query], n_results=effective)
    output = []
    seen_urls: list[str] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        relevance_score = round(max(0.0, 1 - dist), 3)
        if relevance_score <= 0.0:
            continue
        url = meta.get("source_url", "unknown")
        output.append({
            "text": doc,
            "source_url": url,
            "relevance_score": relevance_score,
        })
        if url not in seen_urls:
            seen_urls.append(url)
    return {"results": output, "references": seen_urls}


async def ask(collection: chromadb.Collection, query: str, n_results: int = 5) -> dict:
    retrieved = search_docs(collection, f"{collection.name}: {query}", n_results)
    relevant = [r for r in retrieved["results"] if r["relevance_score"] > 0]
    if not relevant:
        return {"answer": "No relevant content found in this namespace.", "references": []}
    references: list[str] = []
    for r in relevant:
        if r["source_url"] not in references:
            references.append(r["source_url"])
    context = "\n\n".join(
        f"Source: {r['source_url']}\n{r['text']}" for r in relevant
    )
    prompt = (
        "Answer the question using only the context below. "
        "Cite sources by URL when relevant.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )
    try:
        answer = await asyncio.wait_for(ask_agent(prompt, collection.name), timeout=ASK_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return {"error": "Agent call timed out"}
    except Exception as e:
        return {"error": f"Agent call failed: {e}"}
    return {"answer": answer, "references": references}
