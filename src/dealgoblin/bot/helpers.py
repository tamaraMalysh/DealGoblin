from __future__ import annotations


def format_source_list(sources: list[dict]) -> str:
    if not sources:
        return "No sources configured."
    lines = []
    for s in sources:
        name = s.get("username") or s.get("title") or str(s["chat_id"])
        lines.append(f"  {s['id']}. {name} (chat_id={s['chat_id']})")
    return "Sources:\n" + "\n".join(lines)


def format_search_results(results: list[dict]) -> str:
    if not results:
        return "No results found."
    lines = []
    for r in results:
        snippet = (r.get("text_raw") or "")[:120]
        link = r.get("link") or ""
        lines.append(f"- {snippet}\n  {link}")
    return "\n\n".join(lines)


def format_watch_list(watches: list[dict]) -> str:
    if not watches:
        return "No watches configured."
    lines = []
    for w in watches:
        status = "ON" if w["enabled"] else "OFF"
        price = ""
        if w.get("price_min") is not None or w.get("price_max") is not None:
            price = f" [{w.get('price_min', '*')}-{w.get('price_max', '*')}]"
        lines.append(f"  {w['id']}. [{status}] {w['name']}: {w['fts_query']}{price}")
    return "Watches:\n" + "\n".join(lines)
