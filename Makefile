.PHONY: help deploy build push
help: ## Show this help message
	@grep -E '^[a-zA-Z_./-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

._container.cid: Containerfile requirements.txt $(shell find moerderspiel -type f)
	podman build -t moerderspiel -f Containerfile . --iidfile ._container.cid

build: ._container.cid ## Build the container image
	@echo "Container built with ID: $$(cat ._container.cid)"

._container_push.cid: ._container.cid
	podman push moerderspiel ghcr.io/tionis/moerderspiel:latest
	cp ._container.cid ._container_push.cid

push: ._container_push.cid ## Push the container to the registry
	@echo "Container pushed to ghcr.io/tionis/moerderspiel:latest"

deploy: ._container_push.cid ## Build, Push and Deploy the container
	ssh root@makoma.bitmap-ev.org -- bash -c 'podman pull ghcr.io/tionis/moerderspiel:latest && systemctl stop moerderspiel && rm /run/moerderspiel.cid && systemctl start moerderspiel && echo "New Version was deployed"'

dev: ._container.cid ## Start the container in development mode
	mkdir -p ._cache ._data
	podman run --rm -it -p 8080:8080 -v "$$(pwd)/._data:/data" -v "$$(pwd)/._cache:/cache" -e BASE_URL=http://localhost:8080 -e SECRET_KEY=secret -e PORT=8080 -e ADMIN_PASSWORD=admin "$$(cat ._container.cid)"
