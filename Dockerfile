FROM alpine

LABEL maintainer="David Luo <me@dsluo.dev>"

VOLUME "/var/lib/soundbert/sounds"
ENV SOUNDBERT_SOUND_PATH="/var/lib/soundbert/sounds"

ENTRYPOINT ["soundbert"]

CMD ["run"]

RUN mkdir /tmp/soundbert

# dependencies
RUN apk update \
    && apk add --no-cache \
    python3 \
    ffmpeg \
# this is for alembic
    postgresql-dev \
## build deps
    && apk add --no-cache --virtual build-deps \
    gcc \
    python3-dev \
    musl-dev \
    libffi-dev \
    make

# install soundbert python dependencies
COPY ./requirements.txt /tmp/soundbert
RUN python3 -m pip install --no-cache-dir -r /tmp/soundbert/requirements.txt

# install soundbert
COPY . /tmp/soundbert
RUN python3 -m pip install --no-cache-dir /tmp/soundbert[jishaku] \
# remove build deps
    && apk del build-deps \
    && rm -r /tmp/soundbert
