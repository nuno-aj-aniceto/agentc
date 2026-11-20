# ==============================================================================
# Containerfile - agentc compiler and polyglot toolchain environment
# Multi-stage OCI image compatible with Podman, Buildah, and Docker
# ==============================================================================

# Stage 1: Build native Bison/Flex parser using Make (no CMake required)
FROM docker.io/library/alpine:3.23 AS parser-builder
RUN apk add --no-cache g++ make bison flex
WORKDIR /build
COPY compiler/ compiler/
COPY Makefile .
RUN make BUILD_SYSTEM=make parser-make

# Stage 2: Full polyglot agentc toolchain runtime
FROM docker.io/library/alpine:3.23

RUN apk add --no-cache \
    python3 \
    g++ \
    make \
    cmake \
    openjdk21-jdk \
    maven \
    libstdc++ \
    bash

WORKDIR /opt/agentc
COPY . .
COPY --from=parser-builder /build/bin/agentc-parser /opt/agentc/bin/agentc-parser

ENV PATH="/opt/agentc/bin:${PATH}"
ENV JAVA_HOME="/usr/lib/jvm/java-21-openjdk"

ENTRYPOINT ["/opt/agentc/bin/agentc"]
CMD ["--help"]
