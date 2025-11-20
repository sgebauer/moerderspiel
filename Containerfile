FROM codeberg.org/oneuid/debian:trixie-slim as base

FROM codeberg.org/oneuid/mkosi:latest as builder
COPY . /build/
RUN --mount=type=cache,dst=/build/mkosi.pkgcache \
    --mount=type=bind,from=base,src=/,dst=/base \
    mkosi --directory /build --output-directory /output --output rootfs --format directory \
          --base-tree /base --sandbox-tree /base/etc/dpkg/dpkg.cfg.d:/etc/dpkg/dpkg.cfg.d

FROM base
COPY --from=builder /output/rootfs/ /

VOLUME /data
VOLUME /cache

ENV PYTHONPATH=/opt/moerderspiel
ENV CACHE_DIRECTORY=/cache
ENV STATE_DIRECTORY=/data

CMD ["/usr/bin/env", "gunicorn", "moerderspiel.web:app"]
