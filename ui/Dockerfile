FROM node:18 AS build

RUN mkdir /application
WORKDIR /application

COPY package-lock.json package.json /application/
RUN npm ci

COPY . /application

# Build for production with environment.prod.ts
# To override API URL: docker build --build-arg API_URL=https://your-api.com/api
ARG API_URL
RUN if [ -n "$API_URL" ]; then \
	sed -i "s|http://158.160.17.229:8901/api|${API_URL}|g" src/environments/environment.prod.ts; \
	fi

RUN npm run build -- --configuration production

# Production stage with nginx
FROM nginx:alpine
COPY --from=build /application/dist/my-app /usr/share/nginx/html

# Copy custom nginx config if needed
# COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
