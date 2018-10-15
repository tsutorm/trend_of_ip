FROM nerdwaller/pyinstaller-alpine:py3 as build

ENV LANG C.UTF-8

RUN apk update && apk upgrade && \
    apk add --no-cache git gzip gfortran musl-dev gcc libc-dev zlib-dev jpeg-dev && \
    pip3 install --upgrade pip
RUN apk --update add tzdata && \
    cp /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
    echo Asia/Tokyo > /etc/timezone && \
    rm -rf /var/cache/apk/*
RUN pip3 install six packaging ipaddress requests numpy scipy asciimatics ltsv apache-log-parser dnspython

RUN mkdir /app
WORKDIR /app
ADD . /app

RUN cd /app && pyinstaller --hidden-import six \
    --hidden-import packaging \
    --hidden-import packaging.version \
    --hidden-import packaging.specifiers \
    --hidden-import packaging.requirements \
    --clean --strip --noconfirm --onefile -n tip trend_of_ip.py

FROM alpine:3.5

RUN apk update && apk upgrade && apk --update add tzdata && \
    cp /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
    echo Asia/Tokyo > /etc/timezone && \
    rm -rf /var/cache/apk/* && \
    mkdir /app

WORKDIR /app

COPY --from=build /app/dist/tip /app/dist/tip

ENTRYPOINT ["/app/dist/tip"]
