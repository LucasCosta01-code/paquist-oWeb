FROM ubuntu:22.04

# Evita perguntas durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# Instala Node.js (20), Python 3 e compiladores necessários
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    python-is-python3 \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

WORKDIR /app

# Copia e instala pacotes do Node.js
COPY package*.json ./
RUN npm install

# Copia e instala bibliotecas do Python
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# Copia todo o resto do projeto
COPY . .

EXPOSE 3000

# O comando npm start vai rodar o Node e o Python juntos
CMD ["npm", "start"]
