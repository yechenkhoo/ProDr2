# This file creates the indexes for the collections in our DB.

from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import OperationFailure
from threading import Lock
import certifi
from config import Config
import logging

class DatabaseManager:
    _instance = None
    _lock = Lock()  
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.client = MongoClient(Config.MONGO_URI, tlsCAFile=certifi.where())
        self.db = self.client[Config.DATABASE_NAME]
        self._connection_lock = Lock() 
        self._initialized = True
        self.setup_indexes()

    # Create indexes for optimising queries for all of the collections
    def setup_indexes(self):

        try:
            # [Users] collection indexes
            self.db.Users.create_index([("Username", ASCENDING)], unique=True)
            self.db.Users.create_index([("Email", ASCENDING)], unique=True)
            self.db.Users.create_index([("ContactNumber", ASCENDING)])

            # [Patients] collection indexes
            self.db.Patients.create_index([("NRIC", ASCENDING)], unique=True)
            self.db.Patients.create_index([("PatientName", TEXT)])  # Text index for name searches
            self.db.Patients.create_index([("UserID", ASCENDING)])

            # [Appointments] collection indexes
            self.db.Appointments.create_index([
                ("appt_date", ASCENDING),
                ("appt_time", ASCENDING)
            ])
            self.db.Appointments.create_index([("patient_id", ASCENDING)])
            self.db.Appointments.create_index([("appt_status", ASCENDING)])

            # [Medications] collection indexes
            self.db.Medications.create_index([("name", TEXT)])  # Text index for medication searches
            self.db.Medications.create_index([("quantity", ASCENDING)])

            # [PatientHistory] collection indexes
            self.db.PatientHistory.create_index([("patient_id", ASCENDING)])
            self.db.PatientHistory.create_index([("date", DESCENDING)])  # Decending index to sorting by latest
            self.db.PatientHistory.create_index([("diagnosis", TEXT)])  # Text index for diagnosis searches

            # [Prescriptions] collection indexes
            self.db.Prescriptions.create_index([
                ("patient_id", ASCENDING),
                ("date", DESCENDING)
            ])

            logging.info("Successfully created database indexes")
        except OperationFailure as e:
            logging.error(f"Failed to create indexes: {str(e)}")

    # Thread-safe method to get database connection
    def get_db(self):
        with self._connection_lock:
            return self.db

    #Thread-safe atomic update for medication quantities
    #Returns True if update is successful, False if insufficient quantity
    def atomic_update_medication_quantity(self, medication_id, quantity_change):
        with self._connection_lock:
            # Find the medication and check quantity in one atomic operation
            result = self.db.Medications.find_one_and_update(
                {
                    "_id": medication_id,
                    "quantity": {"$gte": abs(quantity_change) if quantity_change < 0 else 0}
                },
                {"$inc": {"quantity": quantity_change}},
                return_document=True
            )
            return result is not None

    # Thread-safe atomic operation for booking appointments
    # Returns True if booking is successful, False if slot has been taken
    def atomic_book_appointment(self, appointment_data):
        with self._connection_lock:
            # Check if slot is available and book in one atomic operation
            existing = self.db.Appointments.find_one({
                "appt_date": appointment_data["appt_date"],
                "appt_time": appointment_data["appt_time"]
            })
            
            if existing:
                return False
                
            self.db.Appointments.insert_one(appointment_data)
            return True

from db_config import DatabaseManager

# Get thread-safe database connection
def get_db_connection():
    db_manager = DatabaseManager()
    return db_manager.get_db()