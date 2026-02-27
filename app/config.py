import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Sponsor APIs
YUTORI_API_KEY = os.getenv("YUTORI_API_KEY")
REKA_API_KEY = os.getenv("REKA_API_KEY")
FASTINO_API_KEY = os.getenv("FASTINO_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
