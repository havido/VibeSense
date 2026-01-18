import os

from dotenv import load_dotenv
from google import genai

# Load values from .env into environment if present
load_dotenv()

# Support both GOOGLE_API_KEY and api_key entries
api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("api_key")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Explain how AI works in a few words"
)
print(response.text)
