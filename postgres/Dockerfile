FROM postgres:16

# Установка pgBackRest
RUN apt-get update && \
    apt-get install -y pgbackrest cron && \
    rm -rf /var/lib/apt/lists/*

ENV PGDATA=/var/lib/postgresql/data

# Создание директорий
RUN mkdir -p \
    /var/log/pgbackrest \
    /var/lib/pgbackrest \
    /backups \
    && chown -R postgres:postgres \
    /var/log/pgbackrest \
    /var/lib/pgbackrest \
    /backups

# БАГ ИСПРАВЛЕН: было COPY ../pgbackrest.conf — ссылка за пределы build context.
# Теперь копируем pgbackrest.conf из той же директории postgres/
COPY pgbackrest.conf /etc/pgbackrest/pgbackrest.conf

# Права
RUN chown postgres:postgres /etc/pgbackrest/pgbackrest.conf && \
    chmod 640 /etc/pgbackrest/pgbackrest.conf

USER postgres
