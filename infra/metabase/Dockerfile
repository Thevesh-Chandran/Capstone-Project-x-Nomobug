FROM metabase/metabase:v0.65.2@sha256:b62ac14872e9992d28218a2264d99484e0707064aae9fb594d8fbb3bc1518a9e
ENV MB_DB_TYPE=postgres MB_JETTY_HOST=0.0.0.0 MB_JETTY_PORT=3000 PORT=3000 MB_ANON_TRACKING_ENABLED=false MB_CHECK_FOR_UPDATES=false
ENV JAVA_OPTS="-Xms128m -Xmx384m -Xss512k -XX:+UseSerialGC -XX:ActiveProcessorCount=1 -XX:MaxMetaspaceSize=512m -XX:ReservedCodeCacheSize=64m -XX:MaxDirectMemorySize=64m"
RUN apk add --no-cache python3
COPY start.sh /cp2/start.sh
COPY proxy.py /cp2/proxy.py
ENTRYPOINT ["/bin/sh", "/cp2/start.sh"]
