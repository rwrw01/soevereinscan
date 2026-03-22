FROM python:3.12-alpine

RUN adduser -D -u 1001 appuser
WORKDIR /srv
COPY index.html .

USER 1001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/ || exit 1

CMD ["python", "-m", "http.server", "8080"]
