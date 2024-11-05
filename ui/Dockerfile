FROM node:18

RUN mkdir /application

WORKDIR /application

COPY package-lock.json package.json /application/

RUN npm install
RUN npm install -g @angular/cli

#test

COPY . /application

CMD ng serve --host 0.0.0.0
