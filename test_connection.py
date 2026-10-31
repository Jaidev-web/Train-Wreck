
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("AQ.Ab8RN6KxuFbquVcICLpU9SO6Pdfu5s9Du8lCwySiczncdDBBNw")
)

try:
    response = client.models.generate_content(
        model="gemma-4-26b-a4b-it",
        contents="Reply with HELLO."
    )

    print("Gemma response:", response.text)

except Exception as e:
    print("API ERROR:", e)
