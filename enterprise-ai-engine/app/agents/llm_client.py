from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
load_dotenv()  # Load environment variables from .env file
# Initialize Groq LLM client
llm = ChatGroq(
    temperature=0,
    model_name="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)

def ask_llm(prompt: str) -> str:
    """
    Send prompt to Groq and return response text
    """
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        print(f"Error invoking LLM: {e}")
        return "Error: Unable to get response from LLM."
