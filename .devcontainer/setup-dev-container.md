# Development Container
Ensures consistency of the development environment for all Agentic development

## Prerequisites
Docker Desktop:
- [Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [MacOS](https://docs.docker.com/desktop/setup/install/mac-install/)
- [Linux](https://docs.docker.com/desktop/setup/install/linux/)

For automatic setup on [Visual Studio Code](https://code.visualstudio.com/), you need the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension.

## Automatic Setup
Visual Studio Code should be aware of our custom Docker container environment will prompt you to open this project inside of a dev container when you open it, where VS Code will automatically create a volume and Docker container for you to work in using our own [development Dockerfile](dev.Dockerfile).

## Responding to Dev Container Changes
If there are changes to the dev container Dockerfile or configuration after syncing your local repository with remote, you should promptly recreate your dev container to reflect those changes. The dev container extension should notify you when this happens.

## Manual Setup
Run the following commands from the repo root:

1. Ensure Docker Desktop or Docker Engine is running, because the actual work required to run Docker containers is handled by the Docker daemon, not the CLI or GUI application.

2. Build the Docker image.
```bash
docker build \
  -f .devcontainer/dev.Dockerfile \
  -t autosec-devcontainer \
  ..
```

3. Start a new Docker container using the new image and mount the working directory to the container.
```bash
docker run -it --rm \
  --name autosec-dev \
  --init \
  --group-add=0 \
  -v "$(pwd):/workspaces/autosec" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e HOST_WORKSPACE="$(pwd)" \
  -w /workspaces/autosec \
  --user vscode \
  autosec-devcontainer
```

4. Exiting the container. Simply run `exit` in the TTY to exit the container, which will stop and delete the container as well. Alternatively, you can use Docker CLI or Docker Desktop to stop the container, which will terminate any shell session still attached to the container.

### Subsequent Startup
Now that you have built the Docker image, you do not need to redo those steps. Simply run a new container with the existing Docker image.
```bash
docker run -it --rm \
  --name autosec-dev \
  --init \
  --group-add=0 \
  -v "$(pwd):/workspaces/autosec" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e HOST_WORKSPACE="$(pwd)" \
  -w /workspaces/autosec \
  --user vscode \
  autosec-devcontainer
```
Attach to this container by following its [respective instructions](#attaching-to-a-running-container).

### Attaching to a Running Container
If you made your own Docker container manually or detached from a running container, you can attach to the container again using the VS Code Dev Containers extension. Open the Command Palette *F1, or Ctrl + Shift + P*, and run `Dev Containers: Attach to Running Container`. 

## Rebuilding the Docker Image
Should you need to rebuild the Docker image if you made your own to start a Docker container manually. It may be wise to retag the old image before building the new image so that the old image is not untagged by the new image. New images will untag old images with the same tag.

You can retag the old image through the following.
```sh
docker tag autosec-devcontainer:latest autosec-devcontainer:old
```
Use the command described in the [manual setup section](#manual-setup) to build the new image. 