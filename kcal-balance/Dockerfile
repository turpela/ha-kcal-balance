FROM python:3.11-alpine

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache tzdata \
 && pip install --no-cache-dir requests requests-oauthlib

COPY fatsecret.py /
CMD ["python3", "/fatsecret.py"]
