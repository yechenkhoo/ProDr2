# This file creates the initial document into the [Users] collection.
# It is the only account that has the staff view.
# This file was used in the inital setup of the DB. It is no longer in use.

from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import certifi

# Connect to MongoDB
client = MongoClient("mongodb+srv://chinliong:qwerty12345@inf2003-clinicdb.ifwic.mongodb.net/clinicDB?retryWrites=true&w=majority&appName=INF2003-clinicDB", tlsCAFile=certifi.where())
db = client["clinicDB"]

# New staff user data
new_staff_user = {
    "username": "staff",
    "email": "staff@gmail.com",
    "password": generate_password_hash("staff"),
    "address": "18 Tai Seng St, #01-07/08, Singapore 539775",
    "contact_number": "62453537",
    "is_staff": 1  # Set to 1 to make this user a staff member
}

# Insert the new staff user
db.Users.insert_one(new_staff_user)
print("New staff user added.")
