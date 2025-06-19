# test_data_setup.py
import pymongo
from datetime import datetime
from dateutil import tz

# Update these with your actual database details
MONGODB_CONNECTION_STRING = "mongodb://localhost:27017/"  # Replace with your connection string
DATABASE_NAME = "data"  # Replace with your database name
COLLECTION_NAME = "Vison_Board"  # Replace with your collection name

def setup_test_data():
    """Insert test data into the database for testing the event endpoint"""
    
    try:
        # Connect to your database
        client = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        print("Connected to database successfully!")
        
        # Clear existing test data (optional)
        delete_result = collection.delete_many({"reference_id": "test-user-123"})
        print(f"Deleted {delete_result.deleted_count} existing test documents")
        
        # Test data documents
        test_documents = [
            {
                "reference_id": "test-user-123",
                "timestamp": "2024-12-19 14:30:00",
                "title": "Golden Dreams",
                "summary": "A vibrant Haldi ceremony with traditional elements",
                "events": ["Haldi", "Pre-Wedding"],
                "boards": [
                    {
                        "colors": ["yellow", "orange", "gold"],
                        "vendor_mappings": [
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/venues/haldi/venue1.jpg",
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42ff9')"
                            },
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/decors/haldi/decor1.jpg", 
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42ffa')"
                            },
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/fashion/haldi/outfit1.jpg",
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42ffb')"
                            }
                        ]
                    }
                ],
                "response_type": "vision_board"
            },
            {
                "reference_id": "test-user-123",
                "timestamp": "2024-12-19 15:45:00", 
                "title": "Elegant Mehendi",
                "summary": "Beautiful Mehendi ceremony with intricate designs",
                "events": ["Mehendi", "Pre-Wedding"],
                "boards": [
                    {
                        "colors": ["green", "red", "pink"],
                        "vendor_mappings": [
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/venues/mehendi/venue1.jpg",
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42ffc')"
                            },
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/decors/mehendi/decor1.jpg",
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42ffd')"
                            },
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/venues/haldi/venue1.jpg",  # Duplicate
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42ff9')"
                            }
                        ]
                    }
                ],
                "response_type": "vision_board"
            },
            {
                "reference_id": "test-user-123",
                "timestamp": "2024-12-19 16:20:00",
                "title": "Grand Wedding", 
                "summary": "Main wedding celebration with grand arrangements",
                "events": ["Wedding Celebration", "Main Event"],
                "boards": [
                    {
                        "colors": ["red", "gold", "white"],
                        "vendor_mappings": [
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/venues/wedding/venue1.jpg",
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42ffe')"
                            },
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/decors/wedding/decor1.jpg",
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df42fff')"
                            }
                        ]
                    }
                ],
                "response_type": "vision_board"
            },
            {
                "reference_id": "test-user-123",
                "timestamp": "2024-12-19 17:00:00",
                "title": "Reception Party",
                "summary": "Evening reception celebration",
                "events": ["Reception", "Party"],
                "boards": [
                    {
                        "colors": ["blue", "silver"],
                        "vendor_mappings": [
                            {
                                "image_link": "https://storage.googleapis.com/weddingverse-01/images/venues/reception/venue1.jpg",
                                "vendor_id": "ObjectId('67600fa5c4ca694f2df43000')"
                            }
                        ]
                    }
                ],
                "response_type": "vision_board"
            }
        ]
        
        # Insert test data
        result = collection.insert_many(test_documents)
        print(f"✅ Successfully inserted {len(result.inserted_ids)} test documents")
        
        # Verify insertion
        count = collection.count_documents({"reference_id": "test-user-123"})
        print(f"✅ Verified: {count} documents found with reference_id 'test-user-123'")
        
        return result.inserted_ids
        
    except Exception as e:
        print(f"❌ Error setting up test data: {e}")
        return None
    finally:
        if 'client' in locals():
            client.close()

def cleanup_test_data():
    """Remove test data after testing"""
    try:
        client = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        result = collection.delete_many({"reference_id": "test-user-123"})
        print(f"🧹 Cleaned up: Deleted {result.deleted_count} test documents")
        
    except Exception as e:
        print(f"❌ Error cleaning up test data: {e}")
    finally:
        if 'client' in locals():
            client.close()

def verify_test_data():
    """Verify test data exists in database"""
    try:
        client = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        # Check total count
        total_docs = collection.count_documents({"reference_id": "test-user-123"})
        print(f"📊 Total test documents: {total_docs}")
        
        # Check each event type
        events_to_check = ["Haldi", "Mehendi", "Wedding Celebration", "Reception"]
        for event in events_to_check:
            count = collection.count_documents({
                "reference_id": "test-user-123",
                "events": {"$in": [event]}
            })
            print(f"📋 Documents with '{event}' event: {count}")
            
        return total_docs > 0
        
    except Exception as e:
        print(f"❌ Error verifying test data: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    print("🚀 Setting up test data for event endpoint testing...")
    print(f"Database: {DATABASE_NAME}")
    print(f"Collection: {COLLECTION_NAME}")
    print("-" * 50)
    
    # Setup test data
    result = setup_test_data()
    
    if result:
        print("\n" + "=" * 50)
        print("✅ TEST DATA SETUP COMPLETE!")
        print("=" * 50)
        print("\n🧪 You can now test the event endpoint:")
        print("1. Haldi: GET /vision-board/test-user-123/event/haldi")
        print("2. Mehendi: GET /vision-board/test-user-123/event/mehendi") 
        print("3. Wedding Celebration: GET /vision-board/test-user-123/event/wedding%20celebration")
        print("4. Reception: GET /vision-board/test-user-123/event/reception")
        print("\n🧹 Run cleanup_test_data() when testing is complete")
        print("\n📊 Verifying data...")
        verify_test_data()
    else:
        print("\n❌ TEST DATA SETUP FAILED!")
        print("Please check your database connection and try again.")