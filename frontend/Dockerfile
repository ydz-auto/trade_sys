FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ENV API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_WS_URL=ws://localhost:8000

EXPOSE 3000

CMD ["npm", "run", "dev"]
