# app/utils/initialize_db.py

import logging
from app.services.mongo_service import db, initialize_conversation_collection
from app.utils.logger import logger

def init_database():
    """Initialize database collections and indexes"""
    logger.info("Initializing conversation database...")
    
    # Initialize conversations collection
    conversations = initialize_conversation_collection()
    logger.info(f"Conversation collection initialized with indexes: {list(conversations.index_information().keys())}")
    
    # Check if we want to create a sample conversation for testing
    # Only do this in dev/local environments, not production
    from app.config import settings
    if settings.env != "prod" and not db["conversations"].find_one({"reference_id": "USER456"}):
        logger.info("Creating sample conversation...")
        
        sample_conversation = {
            "reference_id": "USER456",
            "conversation_id": "USER456-CONV-001",
            "start_time": "2025-05-21T09:00:00Z",
            "last_updated": "2025-05-21T09:20:00Z",
            "conversation": [
                {
                    "timestamp": "2025-05-21T09:01:00Z",
                    "question": "What are all the wedding venues in Bangalore?",
                    "answer": [
                        {
                            "venue_name": "The Tamarind Tree",
                            "location": "JP Nagar",
                            "capacity": 500
                        },
                        {
                            "venue_name": "The Leela Palace",
                            "location": "Old Airport Road",
                            "capacity": 300
                        }
                    ]
                },
                {
                    "timestamp": "2025-05-21T09:05:00Z",
                    "question": "Show me venues under 200 guests capacity.",
                    "answer": [
                        {
                            "venue_name": "La Marvella",
                            "location": "Jayanagar",
                            "capacity": 150
                        }
                    ]
                },
                {
                    "timestamp": "2025-05-21T09:10:00Z",
                    "question": "Do they provide catering?",
                    "answer": [
                        {
                            "venue_name": "La Marvella",
                            "catering_available": True
                        },
                        {
                            "venue_name": "The Tamarind Tree",
                            "catering_available": False
                        }
                    ]
                }
            ]
        }
        
        db["conversations"].insert_one(sample_conversation)
        logger.info("Sample conversation created")
    
    logger.info("Database initialization complete")