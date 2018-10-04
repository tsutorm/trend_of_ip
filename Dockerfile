FROM python:3.6-alpine as build

ENV LANG C.UTF-8

RUN apk update && apk upgrade && apk add --no-cache gzip gfortran musl-dev zlib-dev jpeg-dev
RUN apk --update add tzdata && \
    cp /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
    echo Asia/Tokyo > /etc/timezone && \
    rm -rf /var/cache/apk/*
RUN pip3 install ipaddress requests numpy asciimatics nuitka

RUN mkdir /app
WORKDIR /app
ADD . /app

RUN cd /app && python3 -m compileall trend_of_ip.py

FROM python:3.6-alpine

RUN apk update && apk upgrade && apk --update add tzdata && \
    cp /usr/share/zoneinfo/Asia/Tokyo /etc/localtime && \
    echo Asia/Tokyo > /etc/timezone && \
    rm -rf /var/cache/apk/* && \
    mkdir /app

WORKDIR /app

COPY --from=build /usr/bin /usr/bin
COPY --from=build /usr/local/lib /usr/local/lib
COPY --from=build /app /app

ENTRYPOINT ["python3", "trend_of_ip.py"]
