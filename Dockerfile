FROM python:3.13.2

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    zip \
    unzip \
    p7zip-full \
    file \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p zipper

# Environment variables
ENV BOT_TOKEN=""
ENV API_ID=""
ENV API_HASH=""
ENV BOT_USERNAME=""
ENV MONGO_URL=""

# Command to run the bot
CMD ["python", "main.py"]
