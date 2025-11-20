FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

WORKDIR /app

COPY ./mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./mcp ./app
COPY ./mongo ./mongo