# This file contains the blueprint components for the authentication functions.
# It also handles the registering of new users/patients.

from flask import render_template, request, redirect, session, url_for, flash
from . import auth_bp
from db import get_db_connection
from utils import is_valid_nric, is_valid_sg_address, is_valid_sg_phone
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

# User login route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Display the correct dashboard based on role
    if 'username' in session:
        if session.get('is_staff') == 1:
            return redirect(url_for('staff.staff_dashboard'))
        else:
            return redirect(url_for('patient.patient_dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Server-side validation for empty fields
        if not username or not password:
            flash('Both username and password are required.')
            return redirect(url_for('auth.login'))

        db = get_db_connection()
        user = db.Users.find_one({"Username": username})

        if user and check_password_hash(user['Password'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['Username']
            session['is_staff'] = user.get('IsStaff', 0)

            # Redirect based on whether the user is staff or patient
            if user.get('IsStaff', 0) == 1: 
                flash('Welcome, staff member!', 'success')
                return redirect(url_for('staff.staff_dashboard'))
            else:  
                flash('Welcome, patient!', 'success')
                return redirect(url_for('patient.patient_dashboard'))
        else:
            flash('Invalid login credentials.')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


# User registration route
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')  # Hash the password
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        name = request.form.get('name')
        nric = request.form.get('nric')
        gender = request.form.get('gender')
        dob = request.form.get('dob')
        is_staff = 1 if 'is_staff' in request.form else 0
        
        # Validate address
        if address and not is_valid_sg_address(address):
            flash('Invalid Singapore address. Please provide a valid address with a 6-digit postal code.')
            return redirect(url_for('auth.register'))

        # Validate phone number
        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('auth.register'))
        
        # Validate NRIC format
        if not is_valid_nric(nric):
            flash('Invalid NRIC format. It must start with S, T, F, G, or M, followed by 7 digits and one letter.')
            return redirect(url_for('auth.register'))

        db = get_db_connection()

        # Check if email or nric already exists
        user = db.Users.find_one({"Email": email})
        existing_nric = db.Patients.find_one({"NRIC": nric})

        if user:
            flash('Email already registered. Please try a different email.')
            return redirect(url_for('auth.register'))
        
        if existing_nric:
            flash('NRIC already registered. Please try a different NRIC.')
            return redirect(url_for('auth.register'))

        # Insert new user into the database
        user_data = {
            "Username": username,
            "Email": email,
            "Password": hashed_password,
            "Address": address,
            "ContactNumber": contact_number,
            "IsStaff": is_staff
        }
        user_id = db.Users.insert_one(user_data).inserted_id

        # Insert a corresponding record into the Patients collection with NULL values for height and weight
        if not is_staff:
            patient_data = {
                "UserID": user_id,
                "PatientName": name,
                "NRIC": nric,
                "PatientGender": gender,
                "PatientHeight": None,
                "PatientWeight": None,
                "PatientDOB": dob
            }
            db.Patients.insert_one(patient_data)

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

# User logout route
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

# Delete user route, only for staff member
@auth_bp.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    db = get_db_connection()
    user_id = ObjectId(session['user_id'])
    
    # Delete all records associated with the user/patient
    patient = db.Patients.find_one({"UserID": user_id})
    if patient:
        patient_id = patient['_id']
        db.Prescriptions.delete_many({"PatientID": patient_id})
        db.PatientHistory.delete_many({"PatientID": patient_id})
        db.Appointments.delete_many({"PatientID": patient_id})
        db.Patients.delete_one({"UserID": user_id})
    db.Users.delete_one({"_id": user_id})

    # Clear session and log the user out after deleting account
    session.clear()
    flash('Your account has been deleted successfully.', 'success')
    return redirect(url_for('auth.register'))