# Debussy on Hetzner CX33 — Setup Guide

Server: CX33 (4 vCPU x86, 8 GB RAM, 80 GB disk), Ubuntu 24.04

## 1. System packages

```bash
ssh debussy
apt update && apt upgrade -y
apt install -y git tmux python3 python3-pip python3-venv pipx build-essential
```

## 2. Install Node.js

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
```

## 3. Install CLI tools

```bash
npm install -g @anthropic-ai/claude-code
npm install -g vercel
curl -sSL https://supabase.com/install.sh | bash
```

## 4. Install bd (beads CLI)

```bash
apt install -y golang-go
go install github.com/steveyegge/beads/cmd/bd@latest
echo 'export PATH=$PATH:~/go/bin' >> ~/.bashrc
source ~/.bashrc
```

## 5. Install Playwright

```bash
npx playwright install --with-deps chromium
```

## 6. GitHub SSH access

```bash
ssh-keygen -t ed25519 -C "debussy-hetzner-github" -f ~/.ssh/github -N ""
cat ~/.ssh/github.pub
```

Add the public key to GitHub: Settings > SSH and GPG keys > New SSH key

```bash
git config --global user.name "Debussy Agent"
git config --global user.email "your-email@example.com"

cat >> ~/.ssh/config << 'EOF'
Host github.com
    IdentityFile ~/.ssh/github
EOF
```

## 7. Clone projects

```bash
mkdir -p ~/projects
cd ~/projects
git clone git@github.com:tsturo/debussy.git
git clone git@github.com:tsturo/piklr.git
```

## 8. Install Debussy

```bash
pipx install -e ~/projects/debussy
```

## 9. Environment variables

```bash
cat >> ~/.bashrc << 'EOF'
export ANTHROPIC_API_KEY=sk-ant-...
export PATH=$PATH:~/go/bin
EOF
source ~/.bashrc
```

## 10. Log into services

```bash
vercel login
supabase login
```

## 11. Initialize project

```bash
cd ~/projects/piklr
bd init
mkdir -p .debussy
debussy config base_branch master
debussy config max_total_agents 4
```

## 12. Start Debussy

```bash
cd ~/projects/piklr
tmux new -s debussy
debussy start
```

## Running persistently

Debussy runs inside tmux so it survives SSH disconnects:

- Detach: `Ctrl+B, D`
- Reattach: `ssh debussy` then `tmux attach -t debussy`
