# Baked Minecraft game image.
#
# The vanilla server jar is fetched at BUILD time and baked in, so running pods
# NEVER download from Mojang's CDN at startup. The container runtime then caches
# this image once per node, and the registry dedups it across clusters — turning
# "N pods x N clusters each pulling ~90MB from a throttled CDN" into a single
# build + per-node image pull. Run config (TYPE=CUSTOM) points itzg at the baked
# jar; the world still persists to the /data PVC.
#
# Built by .github/workflows/game-images.yml from deploy/game-versions.json:
#   docker build -t ghcr.io/<owner>/quetzel-game-minecraft:1.20.4 \
#     --build-arg MC_VERSION=1.20.4 \
#     --build-arg SERVER_URL=<piston-data url> \
#     --build-arg SERVER_SHA1=<sha1> game-images/minecraft
ARG JAVA_TAG=java21
FROM itzg/minecraft-server:${JAVA_TAG}

ARG MC_VERSION
ARG SERVER_URL
ARG SERVER_SHA1

# Fetch + integrity-check the server jar at build time (fast on CI networks).
RUN test -n "$SERVER_URL" || (echo "SERVER_URL build-arg required" && exit 1) \
 && mkdir -p /opt/minecraft \
 && curl -fSL --retry 5 --retry-delay 5 "$SERVER_URL" -o /opt/minecraft/server.jar \
 && if [ -n "$SERVER_SHA1" ]; then echo "$SERVER_SHA1  /opt/minecraft/server.jar" | sha1sum -c -; fi \
 && chmod 644 /opt/minecraft/server.jar

# itzg runs the baked jar directly — no runtime download, no paperclip patch step.
ENV TYPE=CUSTOM \
    CUSTOM_SERVER=/opt/minecraft/server.jar \
    EULA=TRUE

LABEL org.opencontainers.image.title="quetzel-game-minecraft" \
      org.opencontainers.image.description="Minecraft server with the server jar baked in (no runtime CDN download)" \
      org.opencontainers.image.version="${MC_VERSION}"
