#!/bin/bash

# Update package lists
sudo apt-get update

# Install Git, Docker, and Docker Compose
sudo apt-get install -y git
sudo apt-get install -y docker.io docker-compose

# Start and enable Docker to run on boot
sudo systemctl start docker
sudo systemctl enable docker

# Add the current user to the 'docker' group to run Docker commands without sudo
sudo usermod -aG docker $USER
newgrp docker

# Set the Airflow User ID for Docker container permissions
export AIRFLOW_UID=5000

# Clone the project repository
git clone https://github.com/NyliStanwood/fundamentos-de-bigdata-pcreativa.git
cd fundamentos-de-bigdata-pcreativa

# The following lines appear to be redundant, removing and re-cloning the same repository.
# You may want to remove these lines if they are not needed.
cd ..
sudo rm -rf fundamentos-de-bigdata-pcreativa
git clone https://github.com/NyliStanwood/fundamentos-de-bigdata-pcreativa.git
cd fundamentos-de-bigdata-pcreativa

# Execute the script to download necessary data
resources/download_data.sh
