#
# Build with:
# docker build --compress	--target build -t tsutorm/trend_of_ip-build:aws .
#
# docker run  --name trend_of_ip-build-aws -it tsutorm/trend_of_ip-build:aws /app/dist/tip -h
# docker cp trend_of_ip-build-aws:/app/dist/tip dist/tip.aws
#

FROM amazonlinux:2018.03 as build

ENV LANG en_US.UTF-8
ENV PYSHORT 3.6
ENV PYTHONVER 3.6.1

RUN yum -y update && \
    yum groupinstall -y "Development tools" && yum groupinstall -y "Development Libraries" && \
    yum install -y zlib-devel bzip2-devel openssl-devel ncurses-devel readline-devel tk-devel lapack-devel atlas-devel \
        libpcap-devel xz-devel libjpeg-devel wget git

WORKDIR /tmp

RUN wget --no-check-certificate https://www.python.org/ftp/python/${PYTHONVER}/Python-${PYTHONVER}.tgz
RUN tar -zxvf Python-${PYTHONVER}.tgz

WORKDIR /tmp/Python-${PYTHONVER}
RUN ./configure --prefix=/usr/local LDFLAGS="-Wl,-rpath /usr/local/lib" --with-ensurepip=install --enable-shared
RUN make && make altinstall
RUN rm -r /tmp/Python-${PYTHONVER}
RUN ln -sf /usr/local/bin/python3.6 /usr/bin/python3 && \
    ln -sf /usr/local/bin/pip3.6 /usr/bin/pip3 && \
    pip3 install --upgrade pip setuptools
RUN pip3 install six pycrypto packaging ipaddress requests numpy asciimatics ltsv apache-log-parser dnspython
RUN pip3 install scipy
RUN pip3 install pyinstaller

RUN mkdir /app
WORKDIR /app
ADD . /app

RUN cd /app && pyinstaller --hidden-import six \
    --hidden-import packaging \
    --hidden-import packaging.version \
    --hidden-import packaging.specifiers \
    --hidden-import packaging.requirements \
    --hidden-import tkinter \
    --strip --noconfirm --onefile --clean -n tip trend_of_ip.py

FROM amazonlinux:2018.03

RUN yum -y update

WORKDIR /app

COPY --from=build /app/dist/tip /app/dist/tip

ENTRYPOINT ["/app/dist/tip"]
