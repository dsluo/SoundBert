FROM alpine

LABEL maintainer="David Luo <me@dsluo.dev>"

COPY . /tmp/soundbert

# dependencies
RUN apk update \
    && apk add --no-cache \
    python3 \
    ffmpeg \
## build deps
    && apk add --no-cache --virtual build-deps \
    gcc \
    python3-dev \
    musl-dev \
    libffi-dev \
    make \
# install soundbert
    && python3 -m pip install --no-cache-dir /tmp/soundbert[uvloop] \
# remove build deps
    && apk del build-deps \
    && rm -r /tmp/soundbert

VOLUME "/var/lib/soundbert/sounds"
VOLUME "/etc/soundbert"

ENTRYPOINT ["soundbert", "--config", "/etc/soundbert/settings.toml"]

CMD ["run"]