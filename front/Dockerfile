# Dockerfile for React (Vite) frontend
FROM node:20-alpine as build

WORKDIR /app

COPY package.json package-lock.json ./
ENV NODE_ENV=development
RUN npm ci --include=dev

COPY . .
RUN npm run build

# Production image
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
