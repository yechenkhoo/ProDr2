# Configuration file for DB

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key')
    
    # MongoDB connection SRV URI. See https://www.mongodb.com/docs/manual/reference/connection-string/
    MONGO_URI = os.environ.get(
        'MONGO_URI',
        "mongodb+srv://chinliong:qwerty12345@inf2003-clinicdb.ifwic.mongodb.net/clinicDB?retryWrites=true&w=majority&appName=INF2003-clinicDB"
    )
    
    # Database name for MongoDB
    DATABASE_NAME = os.environ.get('DATABASE_NAME', 'clinicDB')

