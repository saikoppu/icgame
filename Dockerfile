FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["bet-sizing-server", "--host", "0.0.0.0", "--port", "8000"]
