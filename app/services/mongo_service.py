from pymongo import MongoClient
from app.config import settings

# Initialize MongoDB client using settings
try:
    client = MongoClient(settings.mongo_uri)
except:
    client = MongoClient("mongodb://localhost:27017")
db = client[settings.database_name]
