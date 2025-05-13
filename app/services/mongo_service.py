from pymongo import MongoClient
from app.config import settings

# Initialize MongoDB client using settings
client = MongoClient(settings.mongo_uri)
db = client[settings.database_name]
