# This file is used to connect to the cloud MongoDB.

from pymongo import MongoClient
from config import Config
from db_config import DatabaseManager
import certifi

def get_db_connection():
    """Get thread-safe database connection"""
    db_manager = DatabaseManager()
    return db_manager.get_db()
