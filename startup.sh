# startup.sh

#!/bin/bash

echo "🚀 Starting University AI System (Option 1 - Fully Self-Contained)..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${BLUE}📁 Creating backend directory structure...${NC}"
mkdir -p backend/{constants,database,llm,logic,routes,utils}

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating default...${NC}"
    cat > .env << EOF
# Database Configuration (Real credentials)
CASSANDRA_HOST=sunway.hep88.com
CASSANDRA_PORT=9042
CASSANDRA_USERNAME=planusertest
CASSANDRA_PASSWORD=Ic7cU8K965Zqx
CASSANDRA_KEYSPACE=subjectplanning

# LLM Configuration (Docker Ollama)
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
LLAMA_MODEL=llama3.2

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=true

# Frontend Configuration
REACT_APP_API_URL=http://localhost:8000
EOF
fi

# Stop any existing containers
echo -e "${BLUE}🛑 Stopping any existing containers...${NC}"
docker-compose down 2>/dev/null

# Build and start the services
echo -e "${BLUE}📦 Building and starting Docker containers...${NC}"
docker-compose up -d --build

# Wait for services to initialize
echo -e "${YELLOW}⏳ Waiting for services to initialize...${NC}"

# Wait for Ollama (longer timeout for first-time setup)
echo -e "${BLUE}🤖 Waiting for Ollama service...${NC}"
for i in {1..60}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama service is ready${NC}"
        break
    fi
    echo -e "${YELLOW}⏳ Ollama starting... (${i}/60)${NC}"
    sleep 5
done

# Wait for model initialization
echo -e "${BLUE}📥 Waiting for model to download (this may take a while for first run)...${NC}"
docker logs -f university_model_init 2>/dev/null &
MODEL_LOG_PID=$!
sleep 60  # Give model time to download
kill $MODEL_LOG_PID 2>/dev/null

# Wait for backend
echo -e "${BLUE}🔧 Waiting for backend service...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend service is ready${NC}"
        break
    fi
    echo -e "${YELLOW}⏳ Backend starting... (${i}/30)${NC}"
    sleep 5
done

# Wait for frontend
echo -e "${BLUE}🎨 Waiting for frontend service...${NC}"
for i in {1..20}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Frontend service is ready${NC}"
        break
    fi
    echo -e "${YELLOW}⏳ Frontend starting... (${i}/20)${NC}"
    sleep 3
done

# Final service health check
echo -e "${BLUE}🔍 Final service health check...${NC}"

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama service is running${NC}"
    OLLAMA_STATUS="✅"
else
    echo -e "${RED}❌ Ollama service failed to start${NC}"
    OLLAMA_STATUS="❌"
fi

# Check Backend
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend service is running${NC}"
    BACKEND_STATUS="✅"
else
    echo -e "${RED}❌ Backend service failed to start${NC}"
    BACKEND_STATUS="❌"
fi

# Check Frontend
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend service is running${NC}"
    FRONTEND_STATUS="✅"
else
    echo -e "${RED}❌ Frontend service failed to start${NC}"
    FRONTEND_STATUS="❌"
fi

# Database connectivity check
echo -e "${BLUE}🗄️  Checking database connectivity to existing database...${NC}"
DB_CHECK=$(curl -s http://localhost:8000/health | grep -o '"database":"[^"]*"' | cut -d'"' -f4)
if [[ "$DB_CHECK" == healthy* ]]; then
    echo -e "${GREEN}✅ Database connection is healthy: $DB_CHECK${NC}"
    DB_STATUS="✅"
elif [[ "$DB_CHECK" == *unhealthy* ]]; then
    echo -e "${RED}❌ Database connection failed: $DB_CHECK${NC}"
    DB_STATUS="❌"
else
    echo -e "${YELLOW}⚠️  Database status unclear: $DB_CHECK${NC}"
    DB_STATUS="⚠️"
fi

echo ""
echo -e "${GREEN}🎉 System startup complete!${NC}"
echo ""
echo -e "${BLUE}================== SERVICE STATUS ==================${NC}"
echo -e "Ollama (LLM):     $OLLAMA_STATUS  http://localhost:11434"
echo -e "Backend (API):    $BACKEND_STATUS  http://localhost:8000"
echo -e "Frontend (UI):    $FRONTEND_STATUS  http://localhost:3000"
echo -e "Database:         $DB_STATUS  sunway.hep88.com:9042 (existing data)"
echo -e "${BLUE}===================================================${NC}"
echo ""
echo -e "${GREEN}🚀 Ready to use!${NC}"
echo -e "📱 Open your browser and go to: ${BLUE}http://localhost:3000${NC}"
echo -e "🔧 API documentation available at: ${BLUE}http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo -e "• Login as admin with username: admin, password: admin"
echo -e "• Login as student with your student ID as both username and password"
echo -e "• Try asking: 'What are my programming results?' or 'Show me Computer Science students'"
echo ""
echo -e "${BLUE}📋 To stop the system, run: ./stop.sh${NC}"
