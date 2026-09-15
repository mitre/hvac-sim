FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY hvac_sim.py .
COPY config.ini .

# BACnet/IP
EXPOSE 47808/udp

# Headless: bind to the container's primary interface and skip the HMI.
ENTRYPOINT ["python", "hvac_sim.py", "--no-hmi", "--address", "auto"]
