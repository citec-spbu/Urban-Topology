FROM python:3.9.6-slim

ENV JAVA_HOME=/opt/java/openjdk
COPY --from=eclipse-temurin:11 $JAVA_HOME $JAVA_HOME
ENV PATH="${JAVA_HOME}/bin:${PATH}"

COPY /requirements.txt /requirements.txt

RUN apt-get -y update \
 && apt-get install wget unzip zip -y

RUN apt-get install postgresql-client -y

# RUN python -m pip install fiona

RUN wget https://github.com/openstreetmap/osmosis/releases/download/0.48.3/osmosis-0.48.3.tgz \
&& mkdir osmosis && mv osmosis-0.48.3.tgz osmosis \
&& cd osmosis && tar xvfz osmosis-0.48.3.tgz \
&& rm osmosis-0.48.3.tgz && chmod a+x bin/osmosis

# эта строчка нужня для сборки на маке под m1
RUN apt-get install -y gdal-bin libgdal-dev g++ 

RUN pip install --upgrade pip && pip install -r /requirements.txt

#ADD ./fastapi_service /app/fastapi_service

WORKDIR /app/fastapi_service/

ENTRYPOINT [ "python", "main.py" ]