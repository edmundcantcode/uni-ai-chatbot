# University AI Assistant

An intelligent chatbot system for university data queries with natural language processing, powered by Llama LLM and designed for real-time student and administrative data access.

## Features

### Smart Query Processing
- Natural Language Understanding: Ask questions like "What are my Programming results?" or "Show me Computer Science students"
- Interactive Confirmation Loop: AI clarifies ambiguous queries until you confirm understanding
- Fuzzy Matching: Automatically handles variations in subject/program names

### Role-Based Access Control
- Student Access: Secure access to personal academic records only
- Admin Access: Full database access with comprehensive reporting capabilities
- Authentication: Simple login system with demo credentials

### Advanced Data Intelligence
- Real-time Database Queries: Connects to live Cassandra database
- Smart CQL Generation: Converts natural language to optimized database queries  
- Export Functionality: Download results as CSV files
- Visual Data Display: Clean tables with interactive features

### Modern Technology Stack
- Frontend: React.js with responsive UI
- Backend: FastAPI with async processing
- LLM: Llama 3.2 running locally via Ollama
- Database: Cassandra with existing university data
- Deployment: Fully containerized with Docker

## Quick Start

### Prerequisites
- Docker Desktop installed and running
- Git for cloning the repository
- 8GB+ RAM recommended for LLM processing

### One-Command Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/uni-ai-chatbot.git
cd uni-ai-chatbot

# Start the entire system (this may take 10-15 minutes on first run)
./startup.sh
```

The startup script will:
1. Build and start all Docker containers
2. Download the Llama 3.2 model (first time only)
3. Connect to the university database
4. Launch the React frontend
5. Show you a status dashboard

### Access the System
- Web Interface: http://localhost:3000
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Login Credentials

### Admin Access
- Username: admin
- Password: admin
- Capabilities: View all student data, generate reports, access analytics

### Student Access
- Username: Your student ID (integer)
- Password: Same as your student ID
- Example: Username: 12345, Password: 12345
- Capabilities: View personal academic records only

## Example Queries

### For Students
- "What are my Programming Principles results?"
- "Show me my CGPA for this semester"
- "What subjects did I take in 2024?"
- "How did I perform in Database Fundamentals?"

### For Admins
- "How many students are in Computer Science?"
- "Show me all students from Malaysia"  
- "What's the average CGPA for Information Technology students?"
- "List all students who took Artificial Intelligence"

## System Architecture

```
React Frontend (Port 3000) <--> FastAPI Backend (Port 8000) <--> Cassandra Database
                                        |
                                        v
                                 Llama 3.2 LLM (Ollama/Docker)
```

### Phase 1: Query Understanding
1. User Input: Natural language query received
2. LLM Processing: Llama interprets the query intent  
3. Clarification Loop: Interactive confirmation until user says "yes"
4. Context Building: Role-based permissions and data access rules applied

### Phase 2: Data Retrieval
1. CQL Generation: Smart query builder with fuzzy matching
2. Database Execution: Optimized queries against live university data
3. Result Processing: Clean, formatted data with export options
4. UI Display: Beautiful tables with interactive features

## Project Structure

```
uni-ai-chatbot/
├── startup.sh                     # One-command system startup
├── stop.sh                       # Clean system shutdown
├── docker-compose.yml            # Multi-container orchestration
├── .env                         # Environment configuration
├── Dockerfile.*                  # Container definitions
├── frontend/                     # React application
│   ├── src/Chatbot.jsx             # Main chat interface
│   ├── src/LoginPage.jsx           # Authentication UI
│   └── src/api.js                   # API integration
├── backend/                      # Python FastAPI backend
│   ├── constants/                   # Database schema definitions
│   ├── database/                    # Cassandra connection
│   ├── llm/                        # Llama integration
│   ├── logic/                       # Query processing engine
│   ├── routes/                      # API endpoints
│   └── utils/                       # Data normalization & fuzzy matching
├── main.py                       # FastAPI application
└── model_init.py                 # Llama model initialization
```

## Configuration

### Database Settings (.env)
```bash
CASSANDRA_HOST=sunway.hep88.com
CASSANDRA_PORT=9042  
CASSANDRA_USERNAME=planusertest
CASSANDRA_PASSWORD=Ic7cU8K965Zqx
CASSANDRA_KEYSPACE=subjectplanning
```

### LLM Settings (.env)
```bash
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
LLAMA_MODEL=llama3.2
```

## Available Commands

### Start System
```bash
./startup.sh
```

### Stop System  
```bash
./stop.sh
```

### Check Status
```bash
docker ps
curl http://localhost:8000/health
```

### View Logs
```bash
docker logs university_backend
docker logs university_ollama
docker logs university_frontend
```

### Clean Reset
```bash
docker-compose down -v
./startup.sh
```

## Troubleshooting

### Docker Issues
- Ensure Docker Desktop is running
- Check available disk space (5GB+ required)
- Restart Docker Desktop if containers fail to start

### Model Download Issues
- First run takes 10-15 minutes to download Llama model
- Check internet connection for model download
- View progress: `docker logs university_model_init`

### Database Connection Issues
- Verify VPN connection if required for database access
- Check database credentials in .env file
- Test connection: `curl http://localhost:8000/health`

### Frontend Issues
- Clear browser cache and reload
- Check backend is running: `curl http://localhost:8000`
- View browser console for JavaScript errors

## Development

### Making Changes
1. Edit files in backend/ or frontend/ directories
2. Changes are automatically reloaded in development mode
3. View logs to monitor changes: `docker logs -f university_backend`

### Adding New Features
1. Backend changes: Edit files in backend/ directory
2. Frontend changes: Edit files in frontend/src/ directory
3. Database changes: Update schema in backend/constants/
4. New dependencies: Add to requirements.txt or package.json

## Performance Optimization

### For Better Performance
- Use GPU acceleration if available (uncomment GPU section in docker-compose.yml)
- Increase Docker memory allocation to 8GB+
- Use SSD storage for better I/O performance
- Close unnecessary applications during first-time model download

### For Production Deployment
- Use smaller Llama model for faster responses (llama3.2:1b)
- Enable database connection pooling
- Add Redis for caching frequent queries
- Use nginx for load balancing and static file serving

## Security Notes

- This is a demo system with simplified authentication
- Student authentication uses ID as password (change for production)
- Database credentials are in .env file (use secrets management in production)
- API has CORS enabled for localhost (restrict for production)

## Support

### Getting Help
- Check logs: `docker logs university_backend`
- Verify all containers are running: `docker ps`
- Test API endpoints: http://localhost:8000/docs
- Check database connectivity: http://localhost:8000/health

### Common Issues
- Port conflicts: Stop other services using ports 3000, 8000, 11434
- Memory issues: Ensure 8GB+ RAM available for Docker
- Network issues: Check firewall settings for Docker containers

## License

This project is for educational and demonstration purposes.

## Contributors

- AI-powered query processing with Llama 3.2
- Modern React frontend with real-time chat interface
- FastAPI backend with async processing
- Cassandra database integration with fuzzy matching
- Docker containerization for easy deployment