# Use the latest, more secure Python image
FROM python:3.11.9-slim-bookworm

# Ensure all system packages are upgraded to latest versions to patch vulnerabilities
RUN apt-get update && apt-get upgrade -y && apt-get dist-upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Upgrade system packages to patch vulnerabilities
RUN apt-get update && apt-get upgrade -y && apt-get clean

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Run the bot
CMD ["python", "main.py"]
