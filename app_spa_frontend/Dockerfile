# Этап сборки
FROM node:20-alpine AS build
WORKDIR /app

# Явно устанавливаем npm и зависимости, чтобы избежать ошибки "npm: not found"
RUN apk add --no-cache nodejs npm

# Копируем файлы зависимостей
COPY package*.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем исходный код и собираем проект
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Этап раздачи статики (Nginx)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
