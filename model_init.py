import requests
import time
import os
import sys
import json

def wait_for_ollama():
    """Wait for Ollama service to be ready"""
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    ollama_port = os.getenv("OLLAMA_PORT", "11434")
    url = f"http://{ollama_host}:{ollama_port}/api/tags"
    
    max_attempts = 60  # Increased timeout for Docker startup
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print("✅ Ollama service is ready")
                return True
        except requests.exceptions.RequestException as e:
            pass
        
        if attempt % 5 == 0:  # Print status every 25 seconds
            print(f"⏳ Waiting for Ollama service... (attempt {attempt + 1}/{max_attempts})")
        time.sleep(5)
    
    print("❌ Ollama service failed to start")
    return False

def check_model_exists(model_name):
    """Check if model already exists"""
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    ollama_port = os.getenv("OLLAMA_PORT", "11434")
    url = f"http://{ollama_host}:{ollama_port}/api/tags"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            for model in models:
                if model.get("name", "").startswith(model_name):
                    print(f"✅ Model {model_name} already exists")
                    return True
        return False
    except Exception as e:
        print(f"Error checking existing models: {e}")
        return False

def pull_model(model_name="llama3.2"):
    """Pull the specified Llama model with progress tracking"""
    
    # Check if model already exists
    if check_model_exists(model_name):
        return True
    
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    ollama_port = os.getenv("OLLAMA_PORT", "11434")
    url = f"http://{ollama_host}:{ollama_port}/api/pull"
    
    print(f"📥 Pulling {model_name} model (this may take 10-15 minutes for first time)...")
    
    try:
        response = requests.post(
            url, 
            json={"name": model_name},
            stream=True,
            timeout=1800  # 30 minute timeout
        )
        
        if response.status_code == 200:
            # Stream the response to show progress
            total_size = 0
            completed_size = 0
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        status = data.get('status', '')
                        
                        if 'total' in data and 'completed' in data:
                            total_size = data['total']
                            completed_size = data['completed']
                            if total_size > 0:
                                progress = (completed_size / total_size) * 100
                                print(f"📥 {status}: {progress:.1f}% ({completed_size}/{total_size} bytes)")
                        else:
                            print(f"📥 {status}")
                            
                    except json.JSONDecodeError:
                        print(line.decode('utf-8'))
                        
            print(f"✅ Successfully pulled {model_name}")
            return True
        else:
            print(f"❌ Failed to pull model: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout while pulling {model_name}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error pulling model: {e}")
        return False

def main():
    """Main initialization process"""
    print("🚀 Starting model initialization...")
    print("⚠️  This may take 10-15 minutes on first run to download the model")
    
    if not wait_for_ollama():
        sys.exit(1)
    
    # Try to pull llama3.2 first
    if not pull_model("llama3.2"):
        print("⚠️  Failed to pull llama3.2, trying llama3.1...")
        if not pull_model("llama3.1"):
            print("⚠️  Failed to pull llama3.1, trying llama2...")
            if not pull_model("llama2"):
                print("❌ Failed to pull any Llama model")
                sys.exit(1)
    
    print("✅ Model initialization complete!")
    print("🎉 System is ready to use!")

if __name__ == "__main__":
    main()