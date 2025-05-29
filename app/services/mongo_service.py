from pymongo import MongoClient
from app.config import settings

# Initialize MongoDB client using settings
try:
    client = MongoClient(settings.mongo_uri)
    metadata_client = MongoClient(settings.meta_data_mongo_uri)
except:
    client = MongoClient("mongodb://ww-dev:ww-dev%40321@35.188.230.3:27017")
    metadata_client = MongoClient("mongodb://superadmin:V0%21c3%40G3nt_123%23Secure@34.93.222.178:27017")
db = client[settings.database_name]
metadata_db = metadata_client[settings.meta_data_database_name]