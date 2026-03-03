FROM eclipse-mosquitto:2

COPY entrypoint.sh /usr/local/bin/maximun-mqtt-entrypoint.sh
RUN chmod +x /usr/local/bin/maximun-mqtt-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/maximun-mqtt-entrypoint.sh"]

