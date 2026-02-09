import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from chromadb import Client
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# Suppress warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.getLogger("chromadb").setLevel(logging.ERROR)

class MemoryManager:
    """
    Manages long-term conversation memory using ChromaDB and SentenceTransformers.
    Stores and retrieves message embeddings to provide context awareness.
    """
    
    def __init__(self, persist_dir: str = "D:/College/AI Assistant/memory_store", collection_name: str = "chat_history"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        
        # Ensure directory exists
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # Initialize Vector Store
        try:
            self.client = Client(Settings(persist_directory=self.persist_dir, is_persistent=True))
            self.collection = self.client.get_or_create_collection(self.collection_name)
        except Exception as e:
            print(f"[MEMORY ERROR] Failed to initialize ChromaDB: {e}")
            self.collection = None

        # Initialize Embedding Model
        # Using a lightweight model for speed
        try:
            self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[MEMORY ERROR] Failed to load embedding model: {e}")
            self.embedder = None

    def add_memory(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add a single message to the memory store.
        """
        if not self.collection or not self.embedder or not content.strip():
            return

        try:
            # Generate embedding
            embedding = self.embedder.encode([content]).tolist()[0]
            
            # Prepare data
            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            combined_metadata = {
                "role": role,
                "timestamp": timestamp,
            }
            if metadata:
                combined_metadata.update(metadata)

            # Add to ChromaDB
            self.collection.add(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[combined_metadata]
            )
            # print(f"[MEMORY] Stored {role}: {content[:30]}...") # Debug log
            
        except Exception as e:
            print(f"[MEMORY ERROR] Failed to add memory: {e}")

    def get_relevant_context(self, query: str, limit: int = 5) -> str:
        """
        Retrieve relevant past messages based on semantic similarity.
        Returns a formatted string of context.
        """
        if not self.collection or not self.embedder or not query.strip():
            return ""

        try:
            # Generate query embedding
            query_embedding = self.embedder.encode([query]).tolist()[0]
            
            # Query the database
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit
            )
            
            # Parse results
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            
            if not documents:
                return ""
                
            # Flatten lists (Chroma returns list of lists)
            flat_docs = documents[0]
            flat_metas = metadatas[0]
            
            context_entries = []
            
            # Combine into a readable format, sorted by something? 
            # Chroma sorts by similarity, which is what we want for relevance.
            # But for chat context, time might also matter. 
            # For now, we trust similarity and just prepend "Past Conversation:"
            
            for doc, meta in zip(flat_docs, flat_metas):
                role = meta.get("role", "unknown")
                # timestamp = meta.get("timestamp", "") # Could use this to show date
                context_entries.append(f"[{role.upper()}]: {doc}")
            
            return "\n".join(context_entries)
            
        except Exception as e:
            print(f"[MEMORY ERROR] Failed to retrieve context: {e}")
            return ""

    def clear_memory(self):
        """Clears all stored memories."""
        if self.collection:
            try:
                self.client.delete_collection(self.collection_name)
                self.collection = self.client.create_collection(self.collection_name)
                print("[MEMORY] Memory cleared.")
            except Exception as e:
                print(f"[MEMORY ERROR] Failed to clear memory: {e}")
