# prepare
sudo apt upgrade -y

# deps
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg

# remove any old installs
sudo apt-get remove -y docker docker-engine docker.io containerd runc

# download
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# set repo
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# install
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# verify install
sudo docker run hello-world

# setup sudoless
sudo groupadd docker

# add user
sudo usermod -aG docker $USER

# apply
newgrp docker

# verify sudoless
docker run hello-world
