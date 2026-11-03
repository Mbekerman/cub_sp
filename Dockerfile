FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV CUB_PASTA_PDFS=/tmp/dados
CMD ["cub-sp", "coletar"]
