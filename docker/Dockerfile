FROM python:3.12-slim

WORKDIR /app

# Flush stdout so container logs show the sim/HMI status lines live.
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY simulator/ simulator/
COPY config.ini .

# BACnet/IP and web HMI
EXPOSE 47808/udp 8090

# Bind to the container's primary interface and its subnet mask.
ENTRYPOINT ["python", "-m", "simulator.plc", "--ini", "config.ini", "--address", "auto"]
