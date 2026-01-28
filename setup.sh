#!/bin/bash

# Multi-Agent Setup Script
# Run this in your project root to set up the multi-agent workflow

set -e

echo "🚀 Setting up multi-agent workflow..."

# Check if beads is installed
if ! command -v bd &> /dev/null; then
    echo "❌ Beads (bd) is not installed."
    echo "   Install with: brew install beads"
    echo "   Or: curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash"
    exit 1
fi

# Initialize beads if not already done
if [ ! -d ".beads" ]; then
    echo "📦 Initializing Beads..."
    bd init
else
    echo "✓ Beads already initialized"
fi

# Setup Claude Code integration
echo "🔧 Setting up Claude Code integration..."
bd setup claude 2>/dev/null || echo "  (Claude setup may already be configured)"

# Create directories
echo "📁 Creating directory structure..."
mkdir -p .claude/subagents
mkdir -p docs/adr
mkdir -p scripts
mkdir -p logs
mkdir -p config

# Make scripts executable
if [ -f "scripts/handoff-watcher.sh" ]; then
    chmod +x scripts/handoff-watcher.sh
    echo "✓ handoff-watcher.sh ready"
fi

if [ -f "scripts/handoff.sh" ]; then
    chmod +x scripts/handoff.sh
    echo "✓ handoff.sh ready"
fi

# Copy files (these would be the actual files in real usage)
echo ""
echo "📝 Setup complete!"
echo ""
echo "Directory structure created:"
echo "  .claude/subagents/  - Agent definitions"
echo "  scripts/            - Automation scripts"
echo "  logs/               - Handoff logs"
echo "  config/             - Pipeline config"
echo "  docs/adr/           - Architecture decisions"
echo ""
echo "Next steps:"
echo "1. Copy CLAUDE.md to your project root"
echo "2. Copy subagent files to .claude/subagents/"
echo "3. Copy scripts to scripts/"
echo "4. Run 'bd ready' to see available tasks"
echo ""
echo "Quick start:"
echo "  # Create first task"
echo "  bd create \"My first feature\" -t feature -p 1"
echo ""
echo "  # Start handoff watcher (Terminal 1)"
echo "  ./scripts/handoff-watcher.sh watch"
echo ""
echo "  # Start coordinator (Terminal 2)"
echo "  claude"
echo "  # Then: 'Run as @coordinator. Check bd ready and assign tasks.'"
echo ""
echo "  # Start workers (Terminals 3+)"
echo "  claude --resume"
echo "  # Then: 'Run as @developer. Check bd ready for my tasks.'"
