#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping University AI System...${NC}"

# Stop and remove containers
echo -e "${YELLOW}📦 Stopping Docker containers...${NC}"
docker-compose down

# Check if containers are stopped
RUNNING_CONTAINERS=$(docker ps --filter "name=university_" --format "table {{.Names}}" | grep -v NAMES | wc -l)

if [ "$RUNNING_CONTAINERS" -eq 0 ]; then
    echo -e "${GREEN}✅ All containers stopped successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Some containers may still be running${NC}"
    echo -e "${BLUE}Running containers:${NC}"
    docker ps --filter "name=university_" --format "table {{.Names}}\t{{.Status}}"
fi

echo ""
echo -e "${GREEN}✅ System shutdown complete${NC}"
echo ""
echo -e "${YELLOW}💡 Options:${NC}"
echo -e "🚀 To restart the system: ${BLUE}./startup.sh${NC}"
echo -e "🗑️  To completely clean up (remove downloaded models): ${BLUE}docker-compose down -v${NC}"
echo -e "🧹 To remove all Docker images: ${BLUE}docker system prune -a${NC}"
echo ""
echo -e "${BLUE}📋 System Status:${NC}"
echo -e "• Ollama model data: ${YELLOW}preserved${NC} (in Docker volume)"
echo -e "• Your database: ${GREEN}unchanged${NC} (external - sunway.hep88.com)"
echo -e "• Your code: ${GREEN}unchanged${NC} (local fil