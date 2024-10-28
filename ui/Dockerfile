FROM node:16.20.1

RUN mkdir /application

WORKDIR /application

COPY package-lock.json package.json /application/

RUN npm install
RUN npm install -g @angular/cli

COPY . /application

CMD ng s --host 0.0.0.0
