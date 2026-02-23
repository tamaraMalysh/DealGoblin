def build_fts_query(include: list[str], exclude: list[str] | None = None) -> str | None:
    include = [t.strip() for t in include if t.strip()]
    if not include:
        return None
    query = " AND ".join(include)
    for term in exclude or []:
        term = term.strip()
        if term:
            query += f" NOT {term}"
    return query
