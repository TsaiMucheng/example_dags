#!/usr/bin/env bash

airflow connections add test_mongo \
    --conn-type mongo \
    --conn-description testmongo \
    --conn-host 127.0.0.1 \
    --conn-schema admindb \
    --conn-login admin \
    --conn-password 123456 \
    --conn-port 27017

airflow connections add test_mysql \
    --conn-type mysql \
    --conn-description testmysql \
    --conn-host 127.0.0.1 \
    --conn-login admin \
    --conn-password 123456 \
    --conn-port 3306

airflow connections add test_mssql \
    --conn-type mssql \
    --conn-description testmssql \
    --conn-host 127.0.0.1 \
    --conn-login admin \
    --conn-password 123456 \
    --conn-port 1433

