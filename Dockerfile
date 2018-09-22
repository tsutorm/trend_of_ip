FROM python:3.6-alpine as build

ENV LANG C.UTF-8

RUN apk update && apk upgrade && apk add --no-cache gzip gfortran musl-dev
RUN apk --update add tzdata && \
    cp /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
    echo Asia/Tokyo > /etc/timezone && \
    rm -rf /var/cache/apk/*
RUN pip3 install ipaddress requests numpy nuitka

RUN mkdir /app
WORKDIR /app
ADD . /app

RUN cd /app && python3 -m nuitka --recurse-all trend_of_ip.py

FROM alpine:3.6

RUN mkdir /app
WORKDIR /app

RUN apk update && apk upgrade
RUN apk --update add tzdata && \
    cp /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
    echo Asia/Tokyo > /etc/timezone && \
    rm -rf /var/cache/apk/*

COPY --from=build /usr/bin /usr/bin
COPY --from=build /app /app

ENTRYPOINT ["./trend_of_ip.exe"]
