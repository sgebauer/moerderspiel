FROM python:3.11-bookworm

WORKDIR /opt/moerderspiel

COPY requirements.txt .
RUN apt-get update && \
    apt-get --yes --no-install-recommends install latexmk texlive-latex-extra texlive-fonts-recommended poppler-utils graphviz && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .

VOLUME /data
VOLUME /cache

ENV PYTHONPATH=/opt/moerderspiel
ENV CACHE_DIRECTORY=/cache
ENV STATE_DIRECTORY=/data
