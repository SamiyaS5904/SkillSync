from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import datetime
import uuid
import os

class MongoDBHelper:
    def __init__(self):
        # 🟢 FIX: Load URI from environment variable
        MONGO_URI = os.getenv("MONGO_URI") 
        if not MONGO_URI:
            raise EnvironmentError("MONGO_URI environment variable not set.")
            
        self.client = MongoClient(
            MONGO_URI, # 🟢 USE THE VARIABLE HERE
            server_api=ServerApi('1')
        )

        
            

    def select_db(self, db_name='SkillSyncDB', collection='playlists'):
        """
        Select database and collection.
        Default: SkillSyncDB > playlists
        """
        self.db = self.client[db_name]
        self.collection = self.db[collection]
        print(f'[MongoDBHelper] ✅ DB "{db_name}" Collection "{collection}" Selected')

    def insert_document(self, data: dict):
        """
        Insert any type of document into current collection.
        """
        data["created_at"] = datetime.datetime.utcnow()
        result = self.collection.insert_one(data)
        print(f'[MongoDBHelper] 📌 Document inserted into "{self.collection.name}"')
        return result.inserted_id

    def insert_chat(self, session_id: str, role: str, message: str):
        """
        Special helper for chat storage.
        """
        doc = {
            "session_id": session_id,
            "role": role,
            "message": message,
            "timestamp": datetime.datetime.utcnow()
        }
        return self.insert_document(doc)

    def fetch_documents(self, query: dict = {}, limit=20, sort_field="created_at", ascending=True):
        """
        Fetch documents from current collection.
        """
        order = 1 if ascending else -1
        documents = list(
            self.collection.find(query)
                           .sort(sort_field, order)
                           .limit(limit)
        )
        print(f'[MongoDBHelper] 📂 {len(documents)} docs fetched from "{self.collection.name}"')
        return documents

    def update_document(self, query: dict, update_data: dict):
        """
        Update single document based on query.
        """
        result = self.collection.update_one(query, {"$set": update_data})
        print(f'[MongoDBHelper] ✏️ Document update matched={result.matched_count}, modified={result.modified_count}')
        return result.modified_count

    def get_new_session_id(self):
        """
        Generate unique session IDs (useful for user tracking).
        """
        return str(uuid.uuid4())
