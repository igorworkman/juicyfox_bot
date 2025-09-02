# 🤖 Codex Rules (JuicyFox)

## 📌 Назначение  
Codex отвечает только за **реализацию кода**.  
Задачи формулирует GPTS, Codex выполняет их строго по этим правилам.  

---

## ⚖️ Safety-Contract

### 1. Где можно править  
- ✅ Только в файлах/модулях, которые указаны в задаче.  
- ✅ Новые блоки кода должны быть заключены в REGION-маркеры:  
  ```python
  # REGION AI: <описание>
  ... код ...
  # END REGION AI
  ```  
- ✅ SQL-правки:  
  - Если проект использует **alembic** → правки только в `alembic/versions/`.  
  - Если alembic не используется → правки в `shared/db/schema.sql`.  
- 🚫 Запрещены изменения в `env`, `requirements`, `Dockerfile`, CI/CD, миграциях (кроме alembic), secrets.  

### 2. Что именно можно менять  
- ✅ Вставка и замена кода в пределах указанного региона.  
- ✅ Импорты — только в `# REGION: imports`.  
- 🚫 Не менять сигнатуры публичных функций/классов без явного указания.  
- 🚫 Не трогать FSM/Router namespace и имена состояний.  
- 🚫 Не хардкодить секреты, URL, токены. Использовать конфиги и ENV.  

### 3. Объём изменений  
- ✅ Δ ≤50 строк кода (без учёта комментариев/пустых строк).  
- ✅ ≤2 hunks (изменённых блока) на PR.  
- 🚫 Массовые рефакторинги и переименования запрещены.  

### 4. Формат результата  
- ✅ **По умолчанию**: возвращать изменения в формате **Pull Request (PR)** — готовый код, окружённый REGION-маркерами.  
- ✅ Допустимо использовать **diff-формат** (`+`/`-` префиксы), если это удобнее для представления изменений.  
- ✅ В обоих случаях обязательно добавлять changelog-комментарий (1–3 строки: что и зачем).  
- ✅ Если используется diff-формат, строки с `+`/`-` должны отражать **только реальные изменения**, без лишнего контекста.  
- ✅ Стиль кода сохраняется (PEP8, отступы, кавычки).  

### 5. Инварианты  
- ✅ Модуль должен импортироваться (`python -c "import <module>").  
- ✅ Существующие вызовы функций должны остаться валидными.  
- ✅ FSM и handlers не должны потерять состояния и обработчики.  
- ✅ Логика платежей и событий остаётся идемпотентной.  
- 🚫 Не удалять и не переименовывать существующие API, модели и поля БД.  

### 6. Авто-проверки перед PR  
- ✅ Линтер: `ruff/flake8` на изменённом файле.  
- ✅ Импорт-чек:  
  ```bash
  python -c "import importlib; importlib.import_module('<module>')"
  ```  
- ✅ Smoke-тест (если доступно):  
  ```bash
  uvicorn api.webhook:app --port 0
  ```  
- ✅ Unit-тесты (`pytest`) на изменённых модулях.  

---

## 📦 Что можно / нельзя

| ✅ Можно | 🚫 Нельзя |
|---------|-----------|
| Добавлять новые функции в `modules/*/handlers.py` | Менять `apps/bot_core/main.py` |
| Расширять Enum состояний в `apps/bot_core/state.py` | Удалять или переименовывать существующие состояния |
| Создавать новые UI-элементы в `keyboards.py` | Хардкодить токены/URL |
| Добавлять новые записи в `locales/*.json` | Ломать совместимость API |
| Создавать новые провайдеры в `modules/payments/providers/` | Изменять `requirements*.txt` |
| Добавлять миграции в `alembic/versions/` | Редактировать secrets, env |  

---

## 📌 Пример ответа Codex  

⚠️ Это **только пример оформления**, он **не отражает текущее состояние кода**.  

**Вариант 1 — PR-формат (рекомендуется):**

```sql
# fix: добавлена таблица pending_invoices для корректной работы платежей

# REGION AI: pending_invoices table
CREATE TABLE pending_invoices (
    invoice_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    plan_code TEXT NOT NULL,
    currency TEXT NOT NULL,
    price REAL NOT NULL,
    plan_name TEXT,
    plan_callback TEXT,
    period INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
# END REGION AI
```

**Вариант 2 — Diff-формат (также разрешён):**

```diff
# fix: добавлена таблица pending_invoices для корректной работы платежей
+ CREATE TABLE pending_invoices (
+     invoice_id TEXT PRIMARY KEY,
+     user_id INTEGER NOT NULL,
+     plan_code TEXT NOT NULL,
+     currency TEXT NOT NULL,
+     price REAL NOT NULL,
+     plan_name TEXT,
+     plan_callback TEXT,
+     period INTEGER,
+     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+ );
```

---

## ⚡ Cheatsheet (шпаргалка Codex)

- Δ ≤50 строк, ≤2 hunks.  
- Только файлы/области из задачи.  
- Все новые блоки → REGION-маркеры.  
- SQL → только в alembic (если есть).  
- Формат ответа → **PR по умолчанию**, diff — допустим как fallback.  
- Проверки: flake8 + pytest + импорт.  

---

👉 Это инструкция чисто для Codex.  
GPTS использует отдельный файл `GPTS_RULES.md` для анализа и постановки задач.

