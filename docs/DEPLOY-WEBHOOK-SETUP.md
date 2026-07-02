# Webhook de déploiement NEOGEN — installation (une seule fois)

Permet à Claude de déclencher `git pull && docker compose up -d --build` sur le VPS via un
simple appel HTTPS, sans jamais avoir besoin de SSH direct.

## 1. Copier les fichiers sur le VPS (depuis ta machine, PowerShell ou Git Bash)

```bash
scp C:\Netroia\VIVARIUM\docs\deploy_webhook.py root@76.13.53.162:/root/deploy_webhook.py
```

## 2. Se connecter et installer le service systemd

```bash
ssh root@76.13.53.162
```

Puis, sur le VPS :

```bash
cat > /etc/systemd/system/deploy-webhook.service << 'EOF'
[Unit]
Description=NEOGEN deploy webhook (git pull + docker rebuild sans SSH)
After=network.target docker.service

[Service]
Type=simple
Environment=DEPLOY_WEBHOOK_SECRET=__LE_SECRET_DE_credentials/neogen-deploy-webhook.env__
ExecStart=/usr/bin/python3 /root/deploy_webhook.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable deploy-webhook
systemctl start deploy-webhook
systemctl status deploy-webhook   # doit afficher "active (running)"
```

## 3. Ajouter le bloc nginx (le fichier existe déjà : /etc/nginx/sites-available/neogen)

Ouvrir le fichier :

```bash
nano /etc/nginx/sites-available/neogen
```

Ajouter ce bloc À L'INTÉRIEUR du `server { listen 443 ssl ... }`, juste après le `location / { ... }` existant (voir `docs/nginx.conf.example` mis à jour pour l'emplacement exact) :

```nginx
limit_req_zone $binary_remote_addr zone=neogen_deploy:1m rate=2r/m;
location /_deploy/ {
    limit_req zone=neogen_deploy burst=1 nodelay;
    rewrite ^/_deploy/(.*)$ /$1 break;
    proxy_pass         http://127.0.0.1:9001;
    proxy_set_header   Host $host;
    proxy_read_timeout 600s;
}
```

Puis :

```bash
nginx -t && systemctl reload nginx
```

## 4. Tester

Depuis n'importe où (moi y compris, ensuite) :

```bash
curl -X POST https://neogen.netroia.tech/_deploy/deploy \
  -H "X-Deploy-Secret: __LE_SECRET_DE_credentials/neogen-deploy-webhook.env__"
```

Réponse attendue : JSON avec `"ok": true` et le détail des étapes (git pull + docker build).
Le premier appel prend 30-90s (build Docker).

## Sécurité

- Le secret est déjà sauvegardé dans `C:\Netroia\credentials\neogen-deploy-webhook.env`.
- L'endpoint ne fait STRICTEMENT que `git pull` + `docker compose up -d --build` sur le repo
  NEOGEN — la commande est fixe dans le code, jamais construite depuis la requête. Aucune
  exécution de commande arbitraire n'est possible même si le secret fuit un jour (il faudrait
  aussi changer le code du webhook pour faire autre chose).
- Rate limit nginx à 2 appels/minute — empêche un abus/déni de service sur le rebuild.
- Écoute uniquement sur `127.0.0.1:9001` — jamais exposé directement, seulement via nginx/HTTPS.
- Si tu veux révoquer l'accès : change `DEPLOY_WEBHOOK_SECRET` dans le service systemd et
  redémarre (`systemctl restart deploy-webhook`), sans toucher au reste.
