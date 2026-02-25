# VK Group Messages Viewer

Сервис для получения всех чатов (conversations) и сообщений из группы ВКонтакте через VK API.

## Стек

- **Python 3.11** + **FastAPI** — async веб-фреймворк
- **httpx** — async HTTP-клиент для VK API
- **uvicorn** — ASGI-сервер
- **Jinja2** — шаблоны для веб-интерфейса

## Что делает

- Получает все диалоги группы через `messages.getConversations` с автоматической пагинацией
- Получает все сообщения каждого диалога через `messages.getHistory` с автоматической пагинацией
- Соблюдает rate limit VK API (20 req/s для токена сообщества)
- Предоставляет веб-интерфейс и JSON API

## Эндпоинты

| Маршрут | Описание |
|---|---|
| `GET /` | Веб-страница со списком всех диалогов |
| `GET /chat/{peer_id}` | Веб-страница с сообщениями конкретного диалога |
| `GET /api/conversations` | JSON — все диалоги |
| `GET /api/messages/{peer_id}` | JSON — все сообщения диалога |
| `GET /api/all` | JSON — все диалоги + все их сообщения (может быть медленным!) |

---

## Деплой на Railway — пошаговая инструкция

### Предварительные требования

1. Аккаунт на [railway.app](https://railway.app)
2. Установленный [Railway CLI](https://docs.railway.app/guides/cli) (опционально)
3. VK access_token сообщества с правами на сообщения
4. ID группы VK

### Получение VK токена (если ещё нет)

1. Зайдите в управление сообществом → Настройки → Работа с API
2. Создайте ключ доступа с правами: **Сообщения сообщества**
3. Убедитесь, что в настройках сообщества включены сообщения

### Вариант А: Деплой через GitHub (рекомендуется)

#### Шаг 1 — Пуш репозитория на GitHub

```bash
# Если ещё нет remote:
gh repo create vk-messages --private --source=. --push
# Или если уже есть:
git push origin main
```

#### Шаг 2 — Создание проекта в Railway

1. Откройте [railway.app/new](https://railway.app/new)
2. Нажмите **"Deploy from GitHub repo"**
3. Выберите ваш репозиторий `vk-messages`
4. Railway автоматически определит Python-проект и начнёт сборку

#### Шаг 3 — Настройка переменных окружения

1. В Railway dashboard откройте ваш сервис
2. Перейдите во вкладку **Variables**
3. Добавьте переменные:
   - `VK_ACCESS_TOKEN` = ваш токен сообщества
   - `VK_GROUP_ID` = ID вашей группы (только цифры, без минуса)

#### Шаг 4 — Генерация домена

1. Перейдите во вкладку **Settings** → **Networking**
2. Нажмите **"Generate Domain"**
3. Вы получите URL вида `https://your-app.up.railway.app`

#### Шаг 5 — Проверка

Откройте ваш URL — вы увидите список диалогов группы.

### Вариант Б: Деплой через Railway CLI

```bash
# 1. Установка CLI
npm install -g @railway/cli

# 2. Авторизация
railway login

# 3. Создание проекта
railway init

# 4. Установка переменных
railway variables set VK_ACCESS_TOKEN=ваш_токен
railway variables set VK_GROUP_ID=ваш_id_группы

# 5. Деплой
railway up

# 6. Получение URL
railway domain
```

---

## Эксплуатация

### Просмотр логов

```bash
# Через CLI:
railway logs

# Или через dashboard: вкладка "Deployments" → выбрать деплой → "View Logs"
```

### Обновление

При деплое через GitHub — просто пушите изменения в main, Railway автоматически пересоберёт и задеплоит.

При деплое через CLI:
```bash
railway up
```

### Локальный запуск (для разработки)

```bash
# 1. Создайте .env файл
cp .env.example .env
# Заполните VK_ACCESS_TOKEN и VK_GROUP_ID в .env

# 2. Установите зависимости
pip install -r requirements.txt

# 3. Запуск
uvicorn app.main:app --reload
# Откройте http://localhost:8000
```

### Важные моменты

- **Rate limits**: VK API допускает 20 запросов/сек для токена сообщества. Клиент автоматически соблюдает лимит.
- **Endpoint `/api/all`**: Выгружает ВСЕ сообщения из ВСЕХ чатов. Для группы с большим количеством переписок это может занять значительное время. Используйте с осторожностью.
- **Стоимость Railway**: Hobby plan ($5/мес) включает достаточно ресурсов. Сервис потребляет минимум RAM/CPU в idle.
- **Безопасность**: Не коммитьте `.env` файл. Переменные окружения настраиваются только через Railway Variables.
