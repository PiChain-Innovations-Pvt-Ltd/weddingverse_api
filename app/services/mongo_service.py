from pymongo import MongoClient
from pymongo.collection import Collection
from app.config import settings

# Initialize MongoDB client using settings
client = MongoClient(settings.mongo_uri)
db = client[settings.database_name]

def initialize_conversation_collection():
    """
    Initialize the conversations collection with proper indexes
    Call this function on application startup
    """
    # Create the conversations collection if it doesn't exist
    if "conversations" not in db.list_collection_names():
        db.create_collection("conversations")
    
    # Create indexes for faster querying
    conversations_collection = db["conversations"]
    
    # Create index on reference_id (user_id) for faster lookups
    if "reference_id_1" not in [idx["name"] for idx in conversations_collection.list_indexes()]:
        conversations_collection.create_index("reference_id", unique=True)
    
    # Create index on conversation_id for faster lookups
    if "conversation_id_1" not in [idx["name"] for idx in conversations_collection.list_indexes()]:
        conversations_collection.create_index("conversation_id", unique=True)
    
    # Create index on last_updated to find recent conversations
    if "last_updated_1" not in [idx["name"] for idx in conversations_collection.list_indexes()]:
        conversations_collection.create_index("last_updated")
    
    return conversations_collection