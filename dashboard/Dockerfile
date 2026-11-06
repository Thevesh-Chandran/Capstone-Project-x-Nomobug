# Static Evidence build served by nginx. The build folder holds private extracts
# (customer names), so this image is only deployed behind Google IAP.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY build /usr/share/nginx/html
EXPOSE 8080
