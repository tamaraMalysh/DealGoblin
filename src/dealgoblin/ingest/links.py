def build_message_link(username: str | None, chat_id: int, message_id: int) -> str:
    if username:
        return f"https://t.me/{username}/{message_id}"
    internal_id = abs(chat_id) % 10**12
    return f"https://t.me/c/{internal_id}/{message_id}"
