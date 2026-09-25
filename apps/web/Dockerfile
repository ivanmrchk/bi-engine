FROM nginx:1.27-alpine

COPY index.html style.css app.js /usr/share/nginx/html/
COPY default.conf.template /etc/nginx/templates/default.conf.template

ENV API_UPSTREAM=api:8000

EXPOSE 80
