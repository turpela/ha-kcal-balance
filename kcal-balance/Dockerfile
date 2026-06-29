FROM python:3.11-alpine

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache tzdata \
 && pip install --no-cache-dir requests requests-oauthlib flask

COPY app.py fatsecret.py ha.py store.py /

CMD ["python3", "/app.py"]
