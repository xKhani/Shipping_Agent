# 📦 Shipping Analytics Agent

A sophisticated AI-powered shipping analytics system that combines natural language processing with database querying to provide intelligent insights into shipping and logistics data.

## 🚀 Features

- **Smart Query Routing**: Automatically detects data queries vs general knowledge questions
- **Text-to-SQL Generation**: Converts natural language to SQL queries using local LLM
- **Self-Learning System**: Improves SQL generation by learning from past queries
- **Real-time Database Integration**: Direct PostgreSQL connectivity with dynamic schema inspection
- **Modern Web Interface**: Beautiful, responsive chat interface
- **Error Handling & Recovery**: Robust error handling with self-correction capabilities

## 🏗️ Architecture

```
Frontend (Flask + HTML/CSS/JS)
    ↓
Flask API (app.py)
    ↓
Agent Router (agent/shipping_agent.py)
    ↓
┌─────────────────┬─────────────────┐
│ Text-to-SQL     │ General LLM     │
│ (tools/)        │ (llm/)          │
└─────────────────┴─────────────────┘
    ↓
PostgreSQL Database
```

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL database
- Ollama (for local LLM models)
- Required Python packages (see requirements.txt)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Shipping Agent"
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=shipnest_schema
   DB_USER=postgres
   DB_PASSWORD=your_password
   OLLAMA_API_BASE_URL=http://localhost:11434/
   GENERAL_LLM_MODEL=mistral
   ```

5. **Set up Ollama models**
   ```bash
   # Install and run the required models
   ollama run qwen3:4b
   ollama run mistral
   ```

6. **Set up database**
   - Create a PostgreSQL database named `shipnest_schema`
   - Run the database schema creation script (if available)
   - Populate with sample data:
     ```bash
     python populate_shipping_data.py
     ```

## 🚀 Running the Application

1. **Start the Flask application**
   ```bash
   python app.py
   ```

2. **Access the web interface**
   Open your browser and go to: `http://localhost:5000`

3. **API Endpoints**
   - `GET /` - Web interface
   - `POST /ask` - Send queries to the agent
   - `GET /` (JSON) - API status check

## 💬 Usage Examples

### Data Queries
- "How many shipments were made in July 2025?"
- "Which city received most shipments?"
- "Show me shipments by TCS courier"
- "List the average cost per courier"

### General Knowledge
- "What is supply chain management?"
- "Explain the shipping process"
- "What are the benefits of logistics optimization?"

## 🧪 Testing

Run the test scripts to verify functionality:

```bash
# Test the agent
python test_agent.py

# Test SQL functionality
python test_sql.py

# Test LLM connectivity
python test_llm.py
```

## 📁 Project Structure

```
Shipping Agent/
├── app.py                    # Flask application
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── populate_shipping_data.py # Database seeding
├── templates/
│   └── index.html           # Web interface
├── static/
│   ├── style.css            # Additional styles
│   └── favicon.ico          # Site icon
├── agent/
│   └── shipping_agent.py    # Main agent logic
├── tools/
│   ├── sql_tool.py          # Database operations
│   ├── text_to_sql_tool.py  # SQL generation
│   ├── schema_loader.py     # Schema inspection
│   ├── utils.py             # Utilities
│   ├── sql_history.json     # Query history
│   └── sql_negative_history.json
├── llm/
│   ├── local_llm.py         # General LLM
│   └── sqlcoder_llm.py      # SQL-specific LLM
└── frontend/
    ├── streamlit_app.py     # Alternative Streamlit UI
    └── dashboard.py         # Analytics dashboard
```

## 🔧 Configuration

### Database Configuration
The system connects to PostgreSQL using the following configuration:
- Host: `localhost` (configurable via `DB_HOST`)
- Port: `5432` (configurable via `DB_PORT`)
- Database: `shipnest_schema` (configurable via `DB_NAME`)
- User: `postgres` (configurable via `DB_USER`)
- Password: Set via `DB_PASSWORD` environment variable

### LLM Configuration
- **Primary Model**: `qwen3:4b` (for SQL generation)
- **General Model**: `mistral` (for general queries)
- **API Base URL**: `http://localhost:11434/` (Ollama)

## 🛡️ Security Features

- **Query Safety**: Only read-only SQL operations allowed
- **Input Validation**: Comprehensive input sanitization
- **Error Handling**: Graceful error handling without exposing sensitive information
- **CORS Protection**: Configured for secure cross-origin requests

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify PostgreSQL is running
   - Check database credentials in `.env`
   - Ensure database `shipnest_schema` exists

2. **Ollama Connection Error**
   - Verify Ollama is running: `ollama list`
   - Check if required models are installed
   - Verify API endpoint is accessible

3. **SQL Generation Errors**
   - Check database schema is properly loaded
   - Verify table and column names exist
   - Review SQL history for similar issues

### Debug Mode
Enable debug mode by setting `debug=True` in `app.py` for detailed error messages.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the troubleshooting section
- Review the test files for usage examples
- Examine the SQL history for query patterns

---

**Note**: This system requires a running PostgreSQL database and Ollama instance with the specified models for full functionality.
