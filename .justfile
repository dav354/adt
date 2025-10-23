fmt:
    black .
    isort .

publish tag='latest':
    docker build -t ghcr.io/dav354/lobbyregister-ingestor:{{tag}} .
    docker push ghcr.io/dav354/lobbyregister-ingestor:{{tag}}
