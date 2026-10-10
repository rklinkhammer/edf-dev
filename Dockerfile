# Locally maintained EDF host environment, not AMD's unpublished Dockerfile.
ARG UBUNTU_BASE=ubuntu:22.04@sha256:b1066385161d28ddf6bc7e7b28a9170eec11484c821d1a5150d176cbde41d7f7
FROM ${UBUNTU_BASE}
ARG DEBIAN_FRONTEND=noninteractive
# Use Ubuntu's signed package repositories, including security updates.
# No pip installs, remote shell installers, SSH daemon, sudo, or VNC server.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates locales tzdata build-essential gcc-multilib g++-multilib \
    libc6-dev-i386 autoconf automake bison flex patch gawk wget curl gperf \
    git git-lfs libgl1 subversion diffstat unzip zip sysstat texinfo chrpath socat cpio \
    xz-utils lz4 zstd bmap-tools file rsync bc debianutils iproute2 iputils-ping \
    python3 python3-pip python3-pexpect python3-venv python3-virtualenv \
    python3-git python3-jinja2 python3-yaml python3-subunit pylint \
    repo tmux screen openssh-client graphviz xterm libegl1-mesa libsdl1.2-dev \
    libssl-dev libncurses-dev libacl1 acl liblz4-tool \
    && locale-gen en_US.UTF-8 \
    && groupadd --gid 1000 amd-edf \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash amd-edf \
    && install -d /usr/local/share/edf-dev \
    && dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' \
       > /usr/local/share/edf-dev/packages.tsv \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends util-linux && rm -rf /var/lib/apt/lists/*
RUN chmod 0755 /home/amd-edf && install -d -o 1000 -g 1000 /opt/edf
USER 1000:1000
WORKDIR /opt/edf
COPY config/sources.lock.xml /tmp/edf-manifest.xml
RUN git config --global user.name "EDF container" && git config --global user.email "edf@localhost" && repo init -u https://github.com/Xilinx/yocto-manifests.git -b db9ad19553f9acdd5dfc92228e5a0ca10de760db -m default-edf.xml --depth=1 \
    && cmp /tmp/edf-manifest.xml .repo/manifests/default-edf.xml \
    && repo sync -j4 \
    && repo manifest -r -o /opt/edf/source-manifest.xml
USER root
RUN find /opt/edf -name .git -prune -exec sh -c 'git config --system --add safe.directory "$(dirname "$1")"' sh {} \; && chown -R root:root /opt/edf && chmod -R a+rX /opt/edf
COPY --chmod=755 container-entrypoint.sh /usr/local/bin/container-entrypoint
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
WORKDIR /project
ENTRYPOINT ["/usr/local/bin/container-entrypoint"]
CMD ["/bin/bash", "/opt/edf-scripts/build.sh", "image"]
