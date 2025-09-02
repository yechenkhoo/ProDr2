# This file contains the blueprint components for the staff role.

from flask import render_template, request, redirect, session, url_for, flash
from . import patient_bp
from db import get_db_connection
from utils import is_valid_sg_address, is_valid_sg_phone
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from db_config import DatabaseManager

# Patient Dashboard route
@patient_bp.route('/patient_dashboard')
def patient_dashboard():
    if 'is_staff' in session and session['is_staff'] == 0:
        db = get_db_connection()
        
        # Fetch user details
        user = db.Users.find_one({"_id": ObjectId(session['user_id'])})
        if user is None:
            flash('User not found. Please log in again.', 'danger')
            return redirect(url_for('auth.login'))

        # Fetch patient details
        patient = db.Patients.find_one({"UserID": ObjectId(session['user_id'])})
        if patient is None:
            flash('Patient details not found. Please contact support.', 'danger')
            return redirect(url_for('auth.login'))

        # Fetch appointments for patient
        appointments = list(db.Appointments.find({"patient_id": patient['_id']}).sort([("appt_date", -1), ("appt_time", -1)]))

        return render_template('patient_dashboard.html', user=user, patient=patient, appointments=appointments)
    else:
        flash('Please login or create a new account to access our services.')
        return redirect(url_for('auth.login'))


# Update account route
@patient_bp.route('/update_account', methods=['GET', 'POST'])
def update_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    db = get_db_connection()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')

        # Validation checks
        if address and not is_valid_sg_address(address):
            flash('Invalid Singapore address. Please provide a valid address with a 6-digit postal code.')
            return redirect(url_for('patient.update_account'))

        if contact_number and not is_valid_sg_phone(contact_number):
            flash('Invalid Singapore phone number. Please provide a valid 8-digit number starting with 6, 8, or 9.')
            return redirect(url_for('patient.update_account'))

        # Check if email already exists for another user
        existing_user = db.Users.find_one({"Email": email, "_id": {"$ne": ObjectId(session['user_id'])}})

        if existing_user:
            flash('Email is already in use by another account.')
            return redirect(url_for('patient.update_account'))

        # Fetch current user to get existing password
        user = db.Users.find_one({"_id": ObjectId(session['user_id'])})
        existing_hashed_password = user['Password']

        # Check if there is new password, if not keep the old one
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256') if password.strip() else existing_hashed_password

        # Update new details into the DB
        db.Users.update_one(
            {"_id": ObjectId(session['user_id'])},
            {"$set": {
                "Username": username,
                "Email": email,
                "Password": hashed_password,
                "Address": address,
                "ContactNumber": contact_number
            }}
        )

        # Update session data with new username
        session['username'] = username
        flash('Account updated successfully!', 'success')
        return redirect(url_for('patient.update_account'))

    # Fetch the current user's data
    user = db.Users.find_one({"_id": ObjectId(session['user_id'])})
    
    # Only fetch patient data if user is not staff
    patient = None
    if not session.get('is_staff'):
        patient = db.Patients.find_one({"UserID": ObjectId(session['user_id'])})

    return render_template('update_account.html', user=user, patient=patient, is_staff=session.get('is_staff', 0))



# Book and view appointment(s) route
@patient_bp.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session:
        flash('Please log in to book an appointment.')
        return redirect(url_for('auth.login'))

    if session.get('is_staff') == 1:
        flash('Staff members cannot book appointments.')
        return redirect(url_for('staff.staff_dashboard'))

    # Get the current date and the date one week from now
    today = datetime.now().date()
    one_week_later = today + timedelta(days=7)

    if request.method == 'POST':
        appt_date = request.form.get('appt_date')
        appt_time = request.form.get('appt_time')
        appt_reason = request.form.get('appt_reason')

        # Validation
        if not appt_date or not appt_time or not appt_reason:
            flash('All fields are required.')
            return redirect(url_for('patient.book_appointment'))

        try:
            appt_date_obj = datetime.strptime(appt_date, '%Y-%m-%d').date()
            appt_time_obj = datetime.strptime(appt_time, '%H:%M').time()

            if appt_time_obj.minute not in [0, 30]:
                flash('Appointments must be booked at 30-minute intervals.')
                return redirect(url_for('patient.book_appointment'))
                
            if appt_date_obj < datetime.today().date():
                flash('Appointment date must be in the future.')
                return redirect(url_for('patient.book_appointment'))

            if appt_date_obj < today or appt_date_obj > one_week_later:
                flash('Appointments can only be booked within the next 7 days.')
                return redirect(url_for('patient.book_appointment'))

        except ValueError:
            flash('Invalid date or time format.')
            return redirect(url_for('patient.book_appointment'))

        try:
            # Get database manager instance for atomic operations
            db_manager = DatabaseManager()
            db = db_manager.get_db()
            
            # Fetch PatientID
            patient = db.Patients.find_one({"UserID": ObjectId(session['user_id'])})
            if not patient:
                flash('Patient record not found. Please contact support.')
                return redirect(url_for('patient.patient_dashboard'))

            # Convert date/time for MongoDB
            appt_date_datetime = datetime.combine(appt_date_obj, datetime.min.time())
            appt_time_str = appt_time_obj.strftime('%H:%M')

            # Prepare appointment data
            appointment_data = {
                "patient_id": patient['_id'],
                "appt_date": appt_date_datetime,
                "appt_time": appt_time_str,
                "appt_status": 'Pending',
                "appt_reason": appt_reason
            }

            # Use atomic booking operation
            if db_manager.atomic_book_appointment(appointment_data):
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('patient.patient_dashboard'))
            else:
                flash('This appointment slot is already taken. Please choose another time.')
                return redirect(url_for('patient.book_appointment'))

        except Exception as e:
            flash(f'An error occurred while booking the appointment: {str(e)}', 'danger')
            return redirect(url_for('patient.book_appointment'))

    # For GET request, render the booking form
    return render_template('book_appointment.html', min_date=today, max_date=one_week_later)
