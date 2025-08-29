def get_lang(user) -> str:
    """
    Безопасно достаём язык пользователя.
    Возвращает 'ru', 'en', 'es' или 'en' по умолчанию.
    """
    code = getattr(user, "language_code", None) or "en"
    return code.split("-")[0]
