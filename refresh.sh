#!/bin/bash

docker compose down
docker system prune
docker volume prune
clear