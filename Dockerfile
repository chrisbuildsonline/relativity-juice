# Judge container: Debian's ffmpeg 5.1 plus Blender 4.5.3, the versions a fresh checkout is tested against.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl xz-utils ffmpeg python3 \
 && curl -fsSL -o /tmp/blender.tar.xz https://download.blender.org/release/Blender4.5/blender-4.5.3-linux-x64.tar.xz \
 && tar -C /opt -xf /tmp/blender.tar.xz && ln -s /opt/blender-4.5.3-linux-x64/blender /usr/local/bin/blender \
 && rm /tmp/blender.tar.xz && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
ENV BLENDER=/usr/local/bin/blender
CMD ["blender", "-b", "--factory-startup", "--python-exit-code", "1", "--python", "tests/run.py"]
