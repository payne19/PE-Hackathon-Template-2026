FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .

ENV FLASK_APP=run.py
ENV FLASK_DEBUG=false

EXPOSE 5000

CMD ["uv", "run", "gunicorn", "--config", "gunicorn.conf.py", "run:app"]
