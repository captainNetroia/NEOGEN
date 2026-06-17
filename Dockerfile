# VIVARIUM - service API
# Conteneur de NOTRE service (de confiance). Le code genere par l'IA, lui, tourne
# dans des conteneurs durcis SEPARES (sibling containers via le socket Docker monte).
# A deployer sur une MACHINE DEDIEE uniquement, jamais sur le VPS de production.

FROM python:3.12-slim

# Client Docker (CLI seul, pas le demon) : le service lance des conteneurs durcis
# sur le demon de l'hote, via le socket monte au runtime.
ARG DOCKER_CLI_VERSION=27.3.1
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" -o /tmp/docker.tgz \
 && tar -xzf /tmp/docker.tgz -C /tmp \
 && cp /tmp/docker/docker /usr/local/bin/docker \
 && rm -rf /tmp/docker.tgz /tmp/docker \
 && apt-get purge -y curl && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# La cle Claude est passee au runtime via la variable d'environnement ANTHROPIC_API_KEY
# (jamais copiee dans l'image). generator._load_api_key la lit en priorite.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
