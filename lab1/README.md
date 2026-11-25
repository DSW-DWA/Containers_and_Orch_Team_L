# Лабораторная работа 1
## Приложение

Счётчик посещений на Python и Redis. Оба Dockerfile собирают один и тот же `server.py`. Используется только стандартная библиотека Python, поэтому установка пакетов через pip не нужна.

При обращении к `/` сервер выполняет `INCR visits` в Redis и возвращает HTML с числом посещений. `/health/live` проверяет HTTP-сервер, `/health/ready` проверяет Redis командой `PING`. Если Redis недоступен, главная страница и readiness возвращают `503`, liveness продолжает отвечать `200`.

```text
браузер → localhost:8081 (bad) или localhost:8082 (good)
        → Python HTTP-сервер → lab1-redis:6379 → volume lab1-redis-data (/data)
```

Оба варианта используют один Redis и общий счётчик: открытие любой страницы увеличивает одно и то же значение.

| Файл | Назначение |
| --- | --- |
| `server.py` | HTTP-сервер и минимальный клиент протокола Redis, адаптированные к Docker |
| `Dockerfile.bad` | Рабочий образ с намеренными плохими практиками |
| `Dockerfile.good` | Исправленный образ того же приложения |
| `.dockerignore` | Исключение PDF, кешей, виртуального окружения и тестов из контекста сборки |

Настройки через переменные окружения: `REDIS_HOST` (по умолчанию `redis`), `REDIS_PORT` (`6379`), `PORT` (`8080`), `APP_TITLE` (`Docker visit counter`).

## Практическая часть: сборка и запуск

Нужен Docker Engine с Linux-контейнерами; в Windows можно использовать Docker Desktop. Команды ниже выполняются из корня репозитория в PowerShell. Имена `lab1-*` должны быть свободны при первом запуске.

### 1. Проверить Docker и собрать образы

```powershell
docker version
docker build -f lab1/Dockerfile.bad -t lab1-counter:bad lab1
docker build -f lab1/Dockerfile.good -t lab1-counter:good lab1
```

### 2. Создать сеть и постоянное хранилище

```powershell
docker network create lab1-net
docker volume create lab1-redis-data
docker run -d --name lab1-redis --network lab1-net --mount type=volume,source=lab1-redis-data,target=/data redis:7.4-alpine redis-server --appendonly yes --appendfsync always
docker exec lab1-redis redis-cli ping
```

Дождаться ответа `PONG`; если Redis ещё запускается, повторить последнюю команду. Порт Redis на хост не публикуется. Контейнеры находят его по имени `lab1-redis` в сети `lab1-net`.

Redis пишет AOF в `/data`, куда подключён volume. `--appendfsync always` выбран для наглядной проверки долговечности каждой записи в учебной работе; он увеличивает стоимость записи. Сам volume без включённого сохранения Redis не обеспечивает запись каждого изменения счётчика на диск.

### 3. Запустить оба варианта

```powershell
docker run -d --name lab1-counter-bad --network lab1-net -e REDIS_HOST=lab1-redis -p 127.0.0.1:8081:8080 lab1-counter:bad
docker run -d --name lab1-counter-good --network lab1-net -e REDIS_HOST=lab1-redis -p 127.0.0.1:8082:8080 lab1-counter:good
docker ps --filter name=lab1-
```

Открыть `http://localhost:8081/` и `http://localhost:8082/`. Обе страницы должны показывать счётчик; при обновлении значение растёт. Публикация ограничена локальным компьютером. `EXPOSE 8080` в Dockerfile только документирует порт, а публикует его параметр `-p`.

### 4. Проверить HTTP и отличия образов

```powershell
curl.exe -i http://localhost:8081/health/live
curl.exe -i http://localhost:8081/health/ready
curl.exe -i http://localhost:8081/
curl.exe -i http://localhost:8082/health/live
curl.exe -i http://localhost:8082/health/ready
curl.exe -i http://localhost:8082/
docker image ls lab1-counter
docker exec lab1-counter-bad id
docker exec lab1-counter-good id
docker exec lab1-counter-bad ls -la /app
docker exec lab1-counter-good ls -la /app
```

Ожидается HTTP `200` у обоих вариантов, UID `0` у плохого и `10001` у хорошего. В плохом образе в `/app` будут лишние файлы, включая README; в хорошем только код приложения. Зафиксировать реальные размеры образов из вывода Docker, не подставляя заранее придуманные числа.

### 5. Проверить сохранность данных после удаления контейнера Redis

Сначала открыть страницу несколько раз. Следующая команда читает счётчик без увеличения:

```powershell
docker exec lab1-redis redis-cli GET visits
docker inspect lab1-redis
docker stop lab1-redis
docker rm lab1-redis
docker run -d --name lab1-redis --network lab1-net --mount type=volume,source=lab1-redis-data,target=/data redis:7.4-alpine redis-server --appendonly yes --appendfsync always
docker exec lab1-redis redis-cli ping
docker exec lab1-redis redis-cli GET visits
```

После ответа `PONG` значение `GET visits` должно совпасть с прежним, если между измерениями не открывать главную страницу. Следующее открытие страницы увеличит его на один. Проверка демонстрирует сохранение данных после удаления и создания контейнера, а не только после перезапуска процесса. Во время остановки Redis главная страница возвращает `503`.

Volume подключается к контейнеру Redis, потому что именно он хранит состояние приложения. Python-контейнер не хранит данные и в собственном volume не нуждается.

### 6. Завершить работу

```powershell
docker stop lab1-counter-bad lab1-counter-good lab1-redis
docker rm lab1-counter-bad lab1-counter-good lab1-redis
docker network rm lab1-net
```

Volume остаётся для следующего запуска. Только если данные больше не нужны, удалить его командой `docker volume rm lab1-redis-data`: это удалит сохранённый счётчик.

## Плохие практики Dockerfile и исправления

| Плохая практика | Почему это плохо | Исправление в `Dockerfile.good` |
| --- | --- | --- |
| `FROM python:latest` | Версия Python не определена явно и может смениться при следующей загрузке базового образа. Полный образ содержит компоненты, не нужные этому приложению | `FROM python:3.12-alpine`: выбрана ветка Python и компактная база, подходящая приложению без сторонних пакетов |
| `COPY . .` | В образ попадают README и другие ненужные файлы контекста; их изменение инвалидирует слой копирования, хотя приложение не менялось | `COPY server.py ./`: копируется только необходимый исходный файл |
| Отсутствует `USER` | Процесс работает от root внутри контейнера, что даёт ему лишние права при компрометации. Это не означает автоматического получения root на хосте | `USER 10001:10001`: приложение работает без прав root; порт 8080 не требует привилегий |
| `CMD python -u server.py` в shell-форме | Команда запускается через оболочку, что может осложнить доставку сигналов и завершение процесса приложения | `CMD ["python", "-u", "server.py"]`: Python запускается непосредственно основным процессом контейнера |

`python:3.12-alpine` фиксирует ветку, но тег остаётся изменяемым: патчи Python и версия Alpine могут обновляться. Для строгой воспроизводимости необходимо дополнительно закрепить проверенный digest образа.

В обоих Dockerfile `WORKDIR /app` задаёт рабочий каталог, `EXPOSE 8080` описывает HTTP-порт. В хорошем варианте `PYTHONDONTWRITEBYTECODE=1` отключает запись файлов `.pyc`, а `PYTHONUNBUFFERED=1` обеспечивает вывод логов без буферизации. Код принадлежит root и доступен процессу приложения для чтения: выдавать ему право изменять исходники не нужно.

Общий `.dockerignore` исключает заведомо ненужные крупные и служебные файлы, но не устраняет недостаток `COPY . .`: README всё равно копируется в плохой образ. Требование о плохих практиках относится к Dockerfile; оба варианта должны оставаться функциональными.

## Две плохие практики использования контейнеров

1. Хранить данные Redis только внутри контейнера. Даже с AOF файлы в записываемом слое исчезнут при удалении контейнера.
2. Запускать веб-контейнер с `--privileged`. Счётчику нужны только HTTP-порт и соединение с Redis; расширенный доступ к устройствам и возможностям хоста ему не нужен.

Это ошибки эксплуатации, отдельные от четырёх ошибок в Dockerfile которые описаны выше.

## Два случая, когда контейнеры не стоит использовать

1. Нужна отдельная ОС с собственным ядром, например для испытания модулей ядра (как пример)
2. Нужно однократно запустить простой локальный скрипт без сложных зависимостей и требований к переносимости.


## Для сводки
| Проверка | Фактический результат |
| --- | --- |
| Контейнеры | `lab1-counter-bad`, `lab1-counter-good`, `lab1-redis` работают |
| HTTP | `/`, `/health/live`, `/health/ready` вернули `200` у обоих вариантов |
| Счётчик | Последовательные обращения показали `Visits: 1` и `Visits: 2` |
| Размер образов | bad = +- 1.1 GB, good = +- 48 MB по выводу `docker image ls` |
| Пользователь | bad UID 0, good UID 10001 |
| Файлы `/app` | good содержит только `server.py`; bad также содержит README и Dockerfile |
| Сохранность данных | `GET visits` вернул `2` до удаления Redis и `2` после создания нового контейнера с тем же volume |
| Восстановление связи | После пересоздания Redis readiness обоих приложений вернул `200` |

Для просмотра запущенной работы: плохой вариант это http://localhost:8081/, исправленный это http://localhost:8082/. Контейнеры оставлены работающими. Размеры относятся к образам при этой проверке; изменяемые теги могут дать другие результаты при последующей сборке.
