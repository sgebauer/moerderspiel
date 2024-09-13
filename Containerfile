FROM python:3.11-bookworm

WORKDIR /opt/moerderspiel

COPY requirements.txt .
RUN apt-get update && \
    apt-get --yes --no-install-recommends install latexmk texlive-latex-extra texlive-fonts-recommended texlive-luatex fonts-noto-core poppler-utils graphviz wngerman && \
    luaotfload-tool --update --force && \
    pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install gunicorn~=22.0.0

COPY moerderspiel moerderspiel

VOLUME /data
VOLUME /cache

ENV PYTHONPATH=/opt/moerderspiel
ENV CACHE_DIRECTORY=/cache
ENV STATE_DIRECTORY=/data

CMD ["/usr/bin/env", "gunicorn", "moerderspiel.web:app"]
