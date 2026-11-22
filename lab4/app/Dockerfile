FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY server.py wait_for_redis.py ./

USER 10001:10001
EXPOSE 8080
CMD ["python", "-u", "server.py"]
