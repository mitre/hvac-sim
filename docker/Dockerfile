FROM python:3.12-slim

WORKDIR /app

# Flush stdout so container logs show the sim/HMI status lines live.
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY hvac_sim.py .
COPY hmi.py .
COPY config.ini .

# BACnet/IP and web HMI
EXPOSE 47808/udp 8090

# Headless: bind to the container's primary interface and skip the HMI.
ENTRYPOINT ["python", "hvac_sim.py", "--no-hmi", "--address", "auto"]
