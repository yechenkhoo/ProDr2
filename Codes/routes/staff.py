# This file contains the blueprint components for the staff role.

from flask import render_template, request, redirect, session, url_for, flash, jsonify
from . import staff_bp
from db import get_db_connection
from utils import is_valid_nric, is_valid_sg_address, is_valid_sg_phone
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from bson import json_util
import logging
from db_config import DatabaseManager

# Staff Dashboard route
@staff_bp.route('/staff_dashboard', methods=['GET'])
def staff_dashboard():
    if 'is_staff' in session and session['is_staff'] == 1:
        db = get_db_connection()

        # Get values from the request (GET parameters)
        user_id = request.args.get('user_id', '')
        username = request.args.get('username', '')
        email = request.args.get('email', '')
        address = request.args.get('address', '')
        contact_number = request.args.get('contact_number', '')
        name = request.args.get('name', '')
        nric = request.args.get('nric', '')
        gender = request.args.get('gender', '')
        height = request.args.get('height', '')
        weight = request.args.get('weight', '')
        dob = request.args.get('dob', '')
        diagnosis = request.args.get('diagnosis', '')
        diagnosis_date = request.args.get('diagnosis_date', '')

        # Build the base query for non-staff users
        query = {"IsStaff": 0}

        # Add filters for User fields
        if user_id:
            try:
                query["_id"] = ObjectId(user_id)
            except Exception:
                flash("Invalid User ID format.")
                return redirect(url_for('staff.staff_dashboard'))
        if username:
            query["Username"] = {"$regex": username, "$options": "i"}
        if email:
            query["Email"] = {"$regex": email, "$options": "i"}
        if address:
            query["Address"] = {"$regex": address, "$options": "i"}
        if contact_number:
            query["ContactNumber"] = {"$regex": contact_number, "$options": "i"}

        # Fetch users who are not staff and match the criteria
        user_matches = list(db.Users.find(query))
        
        # Prepare list to store patient data with latest diagnoses
        patients = []

        for user in user_matches:
            # Find corresponding patient record
            patient_query = {"UserID": user["_id"]}

            # Add patient-specific filters
            if name:
                patient_query["PatientName"] = {"$regex": name, "$options": "i"}
            if nric:
                patient_query["NRIC"] = {"$regex": nric, "$options": "i"}
            if gender:
                gender_map = {'Male': 'M', 'Female': 'F'}
                patient_query["PatientGender"] = gender_map.get(gender, gender)
            if height:
                try:
                    patient_query["PatientHeight"] = float(height)
                except ValueError:
                    continue
            if weight:
                try:
                    patient_query["PatientWeight"] = float(weight)
                except ValueError:
                    continue
            if dob:
                try:
                    patient_query["PatientDOB"] = datetime.strptime(dob, '%Y-%m-%d')
                except ValueError:
                    continue

            patient = db.Patients.find_one(patient_query)
            
            if patient:
                # Attach user information to patient details
                patient['user'] = user

                # Fetch latest diagnosis
                diagnosis_query = {"patient_id": patient["_id"]}
                if diagnosis:
                    diagnosis_query["diagnosis"] = {"$regex": diagnosis, "$options": "i"}
                if diagnosis_date:
                    try:
                        date_obj = datetime.strptime(diagnosis_date, '%Y-%m-%d')
                        diagnosis_query["date"] = date_obj
                    except ValueError:
                        continue

                # Get the latest diagnosis
                latest_diagnosis = db.PatientHistory.find_one(
                    diagnosis_query,
                    sort=[("date", -1)]
                )

                if latest_diagnosis:
                    patient['latest_diagnosis'] = latest_diagnosis.get("diagnosis", "")
                    # Format the date if it exists
                    if 'date' in latest_diagnosis and latest_diagnosis['date']:
                        if isinstance(latest_diagnosis['date'], datetime):
                            patient['diagnosis_date'] = latest_diagnosis['date'].strftime('%Y-%m-%d')
                        else:
                            # Handle string dates
                            try:
                                date_obj = datetime.strptime(str(latest_diagnosis['date']), '%Y-%m-%d')
                                patient['diagnosis_date'] = date_obj.strftime('%Y-%m-%d')
                            except ValueError:
                                patient['diagnosis_date'] = str(latest_diagnosis['date'])
                else:
                    patient['latest_diagnosis'] = "No diagnosis"
                    patient['diagnosis_date'] = "N/A"

                patients.append(patient)

        # Format patient dates before passing to template
        for patient in patients:
            if 'PatientDOB' in patient and patient['PatientDOB']:
                if isinstance(patient['PatientDOB'], datetime):
                    patient['PatientDOB'] = patient['PatientDOB'].strftime('%Y-%m-%d')
                elif isinstance(patient['PatientDOB'], str):
                    # If it's already a string, try to parse and reformat it
                    try:
                        date_obj = datetime.strptime(patient['PatientDOB'], '%Y-%m-%d')
                        patient['PatientDOB'] = date_obj.strftime('%Y-%m-%d')
                    except ValueError:
                        pass

        return render_template('staff_dashboard.html', patients=patients)
    else:
        flash('Please login or create a new account to access our services.')
        return redirect(url_for('auth.login'))
        
# Edit patient records route
@staff_bp.route('/edit_patient/<string:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    if 'is_staff' not in session or session['is_staff'] != 1:
        flash('You do not have access to this page.')
        return redirect(url_for('auth.login'))

    db = get_db_connection()
    errors = {}

    # Fetch patient details
    patient = db.Patients.find_one({"_id": ObjectId(patient_id)})
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('staff.staff_dashboard'))

    # Fetch the corresponding user using UserID
    user = db.Users.find_one({"_id": ObjectId(patient['UserID'])})
    if not user:
        flash('User not found for the given patient.', 'danger')
        return redirect(url_for('staff.staff_dashboard'))
    
    # If PatientDOB exists, format it to YYYY-MM-DD
    if patient.get('PatientDOB'):
        # If it's already a string in YYYY-MM-DD format, keep it as is
        if isinstance(patient['PatientDOB'], str):
            pass
        # If it's a datetime object, format it
        else:
            patient['PatientDOB'] = patient['PatientDOB'].strftime('%Y-%m-%d')

    if request.method == 'POST':
        # Retrieve form data
        patient_name = request.form['patient_name']
        nric = request.form['nric']
        patient_gender = request.form['patient_gender']
        patient_height = request.form['patient_height']
        patient_weight = request.form['patient_weight']
        patient_dob = request.form['patient_dob']
        email = request.form['email']
        username = request.form['username']
        contact_number = request.form['contact_number']
        address = request.form['address']
        password = request.form.get('password')

        # Handle past diagnosis update or add
        diagnosis_text = []
        diagnosis_date = []
        diagnosis_notes = []
        appt_id = []

        # Collect the diagnosis form data using dynamic field names
        idx = 1
        while f"diagnosis_text_{idx}" in request.form:
            diagnosis_text.append(request.form[f"diagnosis_text_{idx}"])
            diagnosis_date.append(request.form[f"diagnosis_date_{idx}"])
            diagnosis_notes.append(request.form[f"diagnosis_notes_{idx}"])
            appt_id.append(request.form[f"appt_id_{idx}"])
            idx += 1

        # Validations
        if not is_valid_nric(nric):
            errors['nric'] = 'Invalid NRIC format. It must start with S, T, F, G, or M, followed by 7 digits and one letter.'

        if not is_valid_sg_phone(contact_number):
            errors['contact_number'] = 'Invalid phone number format. It must start with 6, 8, or 9 and be 8 digits long.'

        if not is_valid_sg_address(address):
            errors['address'] = 'Invalid address. Please include a valid 6-digit postal code.'

        # Check for existing user with the same email, contact number, or username
        existing_user = db.Users.find_one({
            "$or": [
                {"Email": email},
                {"ContactNumber": contact_number},
                {"Username": username}
            ],
            "_id": {"$ne": ObjectId(patient['UserID'])}  # Use patient's UserID to properly exclude
        })

        existing_nric = db.Patients.find_one({
            "NRIC": nric,
            "_id": {"$ne": ObjectId(patient_id)}
        })

        if existing_user:
            if existing_user['Email'] == email:
                errors['email'] = 'Email is already in use.'
            if existing_user['ContactNumber'] == contact_number:
                errors['contact_number'] = 'Contact number is already in use.'
            if existing_user['Username'] == username:
                errors['username'] = 'Username is already in use.'

        if existing_nric:
            errors['nric'] = 'NRIC is already in use.'

        # If no errors, update the patient details in the DB
        if not errors:
            patient_update = {
                "PatientName": patient_name,
                "NRIC": nric,
                "PatientGender": patient_gender,
                "PatientHeight": float(patient_height) if patient_height.strip() else None,
                "PatientWeight": float(patient_weight) if patient_weight.strip() else None,
                "PatientDOB": datetime.strptime(patient_dob, '%Y-%m-%d')
            }
            db.Patients.update_one({"_id": ObjectId(patient_id)}, {"$set": patient_update})

            user_update = {
                "Username": username,
                "Email": email,
                "ContactNumber": contact_number,
                "Address": address
            }
            if password and password.strip():
                user_update["Password"] = generate_password_hash(password, method='pbkdf2:sha256')
            db.Users.update_one({"_id": ObjectId(patient['UserID'])}, {"$set": user_update})

           # Handle diagnosis updates and inserts
            for idx, appt in enumerate(appt_id):
                # Convert appt_id to ObjectId if it's a valid string
                try:
                    appt_object_id = ObjectId(appt)  # This will raise an error if appt is not a valid ObjectId string
                except Exception as e:
                    logging.error(f"Invalid appt_id: {appt}, Error: {str(e)}")
                    flash(f"Invalid appointment ID: {appt}", 'danger')
                    return redirect(url_for('staff.staff_dashboard'))

                diagnosis_data = {
                    "diagnosis": diagnosis_text[idx],
                    "date": datetime.strptime(diagnosis_date[idx], '%Y-%m-%d'),
                    "notes": diagnosis_notes[idx],
                    "appt_id": appt_object_id  # Store as ObjectId
                }

                # Check if diagnosis already exists in PatientHistory for the given patient and appt_id
                existing_diagnosis = db.PatientHistory.find_one({
                    "patient_id": ObjectId(patient_id),  # Make sure patient_id is ObjectId
                    "appt_id": appt_object_id  # Compare with ObjectId in the query
                })

                if existing_diagnosis:
                    # If the diagnosis already exists, update it
                    db.PatientHistory.update_one(
                        {"_id": existing_diagnosis["_id"]},
                        {"$set": diagnosis_data}
                    )
                else:
                    # If the diagnosis doesn't exist, insert a new record
                    diagnosis_data["patient_id"] = ObjectId(patient_id)  # Ensure patient_id is an ObjectId
                    db.PatientHistory.insert_one(diagnosis_data)

            flash('Patient details and diagnoses updated successfully!', 'success')
            return redirect(url_for('staff.staff_dashboard'))

    # Fetch patient diagnoses
    patient_diagnoses = list(db.PatientHistory.find({"patient_id": ObjectId(patient_id)}).sort("date", -1))

    # Format diagnosis date
    for diag in patient_diagnoses:
        if diag.get('date'):
            diag['date'] = diag['date'].strftime('%Y-%m-%d')

    return render_template('edit_patient.html', patient=patient, user=user, diagnoses=patient_diagnoses, errors=errors)


# Delete patient records route. Only staff should be able to delete patient records due to how a clinic works
@staff_bp.route('/delete_patient/<string:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    if 'is_staff' not in session or session['is_staff'] != 1:
        flash('You do not have access to this page.')
        return redirect(url_for('auth.login'))

    db = get_db_connection()

    try:
        # Delete from all collections associated with patients
        db.Prescriptions.delete_many({"patient_id": ObjectId(patient_id)})
        db.PatientHistory.delete_many({"patient_id": ObjectId(patient_id)})
        db.Appointments.delete_many({"patient_id": ObjectId(patient_id)})
        db.Patients.delete_one({"_id": ObjectId(patient_id)})
        db.Users.delete_one({"_id": ObjectId(patient_id)})

        flash('Patient and associated appointments deleted successfully!', 'success')
    except Exception as err:
        flash(f'An error occurred: {err}', 'danger')

    return redirect(url_for('staff.staff_dashboard'))

# Manage appointment route
# It is for doctors to see what appointments there are for the next 7 days.
@staff_bp.route('/manage_appointment')
def manage_appointment():
    if 'is_staff' in session and session['is_staff'] == 1:
        db = get_db_connection()

        # Calculate the date range for the next 7 days
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)

        # Fetch appointments in the next 7 days sorted by earliest first
        appointments = list(db.Appointments.find({
            "appt_date": {"$gte": start_date, "$lte": end_date},
            "appt_status": "Pending"
        }).sort([("appt_date", 1), ("appt_time", 1)]))

        # Modify appointments to ensure date and time are formatted as strings
        for appointment in appointments:
            if 'appt_date' in appointment and isinstance(appointment['appt_date'], str):
                try:
                    appointment['appt_date'] = datetime.strptime(appointment['appt_date'], '%Y-%m-%d')
                except ValueError:
                    appointment['appt_date'] = None  # Handle invalid date formats

            if 'appt_time' in appointment and isinstance(appointment['appt_time'], str):
                try:
                    appointment['appt_time'] = datetime.strptime(appointment['appt_time'], '%H:%M').time()
                except ValueError:
                    appointment['appt_time'] = None  # Handle invalid time formats

        return render_template('manage_appointment.html', appointments=appointments)
    else:
        flash('Please login or create a new account to access our services.')
        return redirect(url_for('auth.login'))


# View patient details
@staff_bp.route('/view_patient/<string:patient_id>/<string:appt_id>', methods=['GET', 'POST'])
def view_patient(patient_id, appt_id):
    db = get_db_connection()

    # Convert patient_id to ObjectId
    try:
        patient_object_id = ObjectId(patient_id)
    except Exception as e:
        flash(f"Error converting patient_id to ObjectId: {e}", "danger")
        return redirect(url_for('staff.staff_dashboard'))

    # Check if POST for adding medication or diagnosis
    if request.method == 'POST':
        if 'medication' in request.form:
            # Handle medication prescription
            medication_name = request.form['medication']
            med_name_only = medication_name.split(' (')[0]
            duration = request.form['duration']
            notes = request.form['notes']

            med = db.Medications.find_one({"name": med_name_only})

            if med:
                med_id = med['_id']
                current_quantity = med['quantity']
                requested_dosage = int(duration)

                if current_quantity >= requested_dosage:
                    # Insert prescription
                    db.Prescriptions.insert_one({
                        "patient_id": patient_object_id,
                        "appt_id": ObjectId(appt_id),
                        "med_id": med_id,
                        "dosage": requested_dosage,
                        "date": datetime.now(),
                        "notes": notes
                    })
                    # Update quantity
                    db.Medications.update_one({"_id": med_id}, {"$inc": {"quantity": -requested_dosage}})

                    # Insert inventory log
                    db.InventoryLogs.insert_one({
                        "med_id": med_id,
                        "change_type": 'subtract',
                        "quantity_changed": requested_dosage,
                        "date": datetime.now()
                    })

                    flash('Prescription added successfully!', 'success')
                else:
                    flash('Not enough medication in stock!', 'danger')
            else:
                flash('Medication not found!', 'danger')
        else:
            # Handle patient history addition
            diagnosis = request.form['diagnosis']
            notes = request.form['notes']
            date = datetime.now()

            db.PatientHistory.insert_one({
                "patient_id": patient_object_id,
                "appt_id": ObjectId(appt_id),
                "diagnosis": diagnosis,
                "notes": notes,
                "date": date
            })

            flash('Patient history updated successfully!', 'success')

    # Fetch patient information
    patient_info = db.Patients.find_one({"_id": patient_object_id})
    if not patient_info:
        flash(f"Patient not found for patient_id: {patient_id}", "danger")
        return redirect(url_for('staff.staff_dashboard'))

    # Fetch patient history
    patient_history = list(db.PatientHistory.find({"patient_id": patient_object_id}))

    # Format dates in patient history
    for record in patient_history:
        if 'date' in record:
            if isinstance(record['date'], datetime):
                record['date'] = record['date'].strftime('%Y-%m-%d')
            elif isinstance(record['date'], str):
                try:
                    # Try to parse the string date and format it
                    date_obj = datetime.strptime(record['date'], '%Y-%m-%d')
                    record['date'] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    record['date'] = record['date']  # Keep original string if parsing fails

    # Fetch past prescriptions
    past_prescriptions = list(db.Prescriptions.aggregate([
        {"$match": {"patient_id": patient_object_id}},
        {"$lookup": {
            "from": "Medications",
            "localField": "med_id",
            "foreignField": "_id",
            "as": "medication_details"
        }},
        {"$unwind": "$medication_details"},
        {"$project": {
            "prescription_id": "$_id",
            "medication_name": "$medication_details.name",
            "dosage": 1,
            "date": 1,
            "notes": 1
        }}
    ]))

    # Format dates in prescriptions
    for prescription in past_prescriptions:
        if 'date' in prescription:
            if isinstance(prescription['date'], datetime):
                prescription['date'] = prescription['date'].strftime('%Y-%m-%d')
            elif isinstance(prescription['date'], str):
                try:
                    # Try to parse the string date and format it
                    date_obj = datetime.strptime(prescription['date'], '%Y-%m-%d')
                    prescription['date'] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    prescription['date'] = prescription['date']  # Keep original string if parsing fails

    return render_template('view_patient.html', 
                         patient=patient_info, 
                         history=patient_history, 
                         prescriptions=past_prescriptions, 
                         appt_id=appt_id)

# Advanced search routes
# Search feature for staff only using different parameters to find patients
@staff_bp.route('/advanced_search', methods=['POST'])
def advanced_search():
    if 'is_staff' not in session or session['is_staff'] != 1:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_db_connection()

    pipeline = [
        {
            '$lookup': {
                'from': 'Users',
                'localField': 'UserID',
                'foreignField': '_id',
                'as': 'user'
            }
        },
        {
            '$unwind': '$user'
        },
        # Add PatientHistory lookup by default
        {
            '$lookup': {
                'from': 'PatientHistory',
                'let': { 'patient_id': '$_id' },
                'pipeline': [
                    {
                        '$match': {
                            '$expr': { '$eq': ['$patient_id', '$$patient_id'] }
                        }
                    },
                    {
                        '$sort': { 'date': -1 }
                    },
                    {
                        '$limit': 1
                    }
                ],
                'as': 'latest_history'
            }
        },
        {
            '$addFields': {
                'latest_diagnosis': {
                    '$cond': {
                        'if': { '$gt': [{ '$size': '$latest_history' }, 0] },
                        'then': { '$arrayElemAt': ['$latest_history.diagnosis', 0] },
                        'else': 'No diagnosis'
                    }
                },
                'diagnosis_date': {
                    '$cond': {
                        'if': { '$gt': [{ '$size': '$latest_history' }, 0] },
                        'then': { '$arrayElemAt': ['$latest_history.date', 0] },
                        'else': None
                    }
                }
            }
        }
    ]

    # Build match conditions
    match_conditions = {
        'user.IsStaff': 0
    }

    # Get form data for all fields
    username = request.form.get('username', '')
    email = request.form.get('email', '')
    address = request.form.get('address', '')
    contact_number = request.form.get('contact_number', '')
    patient_name = request.form.get('patient_name', '')
    nric = request.form.get('nric', '')
    gender = request.form.get('gender', '')
    dob = request.form.get('dob', '')
    height = request.form.get('height', '')
    weight = request.form.get('weight', '')
    diagnosis = request.form.get('diagnosis', '')
    diagnosis_date = request.form.get('diagnosis_date', '')

    # Add filter conditions
    if username:
        match_conditions['user.Username'] = {'$regex': username, '$options': 'i'}
    if email:
        match_conditions['user.Email'] = {'$regex': email, '$options': 'i'}
    if address: 
        match_conditions['user.Address'] = {'$regex': address, '$options': 'i'}
    if patient_name:
        match_conditions['PatientName'] = {'$regex': patient_name, '$options': 'i'}
    if contact_number:  
        match_conditions['user.ContactNumber'] = {'$regex': contact_number, '$options': 'i'}
    if nric:
        match_conditions['NRIC'] = {'$regex': nric, '$options': 'i'}
    if gender:
        if gender in ['Male', 'Female']:
            gender_map = {'Male': 'M', 'Female': 'F'}
            match_conditions['PatientGender'] = gender_map[gender]
    if height:
        try:
            match_conditions['PatientHeight'] = float(height)
        except ValueError:
            pass
    if weight:
        try:
            match_conditions['PatientWeight'] = float(weight)
        except ValueError:
            pass
    if dob:
        try:
            match_conditions['PatientDOB'] = datetime.strptime(dob, '%Y-%m-%d')
        except ValueError:
            pass
    if diagnosis:
        match_conditions['latest_diagnosis'] = {'$regex': diagnosis, '$options': 'i'}
    if diagnosis_date:
        try:
            diag_date = datetime.strptime(diagnosis_date, '%Y-%m-%d')
            match_conditions['diagnosis_date'] = diag_date
        except ValueError:
            pass

    # Add match conditions to pipeline
    if match_conditions:
        pipeline.append({'$match': match_conditions})

    try:
        patients = list(db.Patients.aggregate(pipeline))
        
        # Format dates and convert ObjectIds to strings
        for patient in patients:
            # Convert ObjectId to string
            patient['_id'] = str(patient['_id'])
            patient['UserID'] = str(patient['UserID'])
            
            # Convert user ObjectId
            if 'user' in patient:
                patient['user']['_id'] = str(patient['user']['_id'])
            
            # Format dates
            if 'PatientDOB' in patient and patient['PatientDOB']:
                if isinstance(patient['PatientDOB'], datetime):
                    patient['PatientDOB'] = patient['PatientDOB'].strftime('%Y-%m-%d')
                    
            if 'diagnosis_date' in patient and patient['diagnosis_date']:
                if isinstance(patient['diagnosis_date'], datetime):
                    patient['diagnosis_date'] = patient['diagnosis_date'].strftime('%Y-%m-%d')
                else:
                    patient['diagnosis_date'] = 'N/A'
            else:
                patient['diagnosis_date'] = 'N/A'

            # Clean up the temporary latest_history field
            if 'latest_history' in patient:
                del patient['latest_history']

        return json_util.dumps(patients)
    except Exception as e:
        print("Error occurred:", str(e))
        return jsonify({'error': str(e)}), 500

# Staff only feature: edit appointments for patients
@staff_bp.route('/edit_appointment/<string:appt_id>', methods=['GET', 'POST'])
def edit_appointment(appt_id):
    db = get_db_connection()

    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']
        status = request.form['status']
        reason = request.form['reason']

        db.Appointments.update_one({"_id": ObjectId(appt_id)}, {"$set": {
            "appt_date": datetime.strptime(date, '%Y-%m-%d'),
            "appt_time": time,
            "appt_status": status,
            "appt_reason": reason
        }})

        flash('Appointment updated successfully!', 'success')
        return redirect(url_for('staff.manage_appointment'))

    appointment = db.Appointments.find_one({"_id": ObjectId(appt_id)})
    return render_template('edit_appointment.html', appointment=appointment)

@staff_bp.route('/staff_book_appointment', methods=['GET', 'POST'])
def staff_book_appointment():
    if 'user_id' not in session:
        flash('Please log in as staff to book an appointment.')
        return redirect(url_for('auth.login'))

    # Get the current date and the date one week from now
    today = datetime.now().date()
    one_week_later = today + timedelta(days=7)

    if request.method == 'POST':
        nric = request.form.get('patient_nric')
        appt_date = request.form.get('appt_date')
        appt_time = request.form.get('appt_time')
        appt_reason = request.form.get('appt_reason')

        # Validation
        if not all([nric, appt_date, appt_time, appt_reason]):
            flash('All fields are required.')
            return redirect(url_for('staff.staff_book_appointment'))

        try:
            appt_date_obj = datetime.strptime(appt_date, '%Y-%m-%d').date()
            appt_time_obj = datetime.strptime(appt_time, '%H:%M').time()
            
            if appt_time_obj.minute not in [0, 30]:
                flash('Appointments must be booked at 30-minute intervals.')
                return redirect(url_for('staff.staff_book_appointment'))
                
            if appt_date_obj < today or appt_date_obj > one_week_later:
                flash('Appointments can only be booked within the next 7 days.')
                return redirect(url_for('staff.staff_book_appointment'))

        except ValueError:
            flash('Invalid date or time format.')
            return redirect(url_for('staff.staff_book_appointment'))

        try:
            # Get database manager instance for atomic operations
            db_manager = DatabaseManager()
            db = db_manager.get_db()

            # Find the patient by NRIC
            patient = db.Patients.find_one({"NRIC": nric})
            if not patient:
                flash('Patient NRIC not found. Please contact support.')
                return redirect(url_for('staff.staff_book_appointment'))

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
                return redirect(url_for('staff.staff_dashboard'))
            else:
                flash('This appointment slot is already taken. Please choose another time.')
                return redirect(url_for('staff.staff_book_appointment'))

        except Exception as e:
            flash(f'An error occurred while booking the appointment: {str(e)}', 'danger')
            return redirect(url_for('staff.staff_book_appointment'))

    # For GET request, render the booking form
    return render_template('staff_book_appointment.html', min_date=today, max_date=one_week_later)

# Delete appointments route
@staff_bp.route('/delete_appointment/<string:appt_id>', methods=['POST'])
def delete_appointment(appt_id):
    db = get_db_connection()
    db.Appointments.delete_one({"_id": ObjectId(appt_id)})

    flash('Appointment deleted successfully!', 'success')
    return redirect(url_for('staff.manage_appointment'))

# Update ApptStatus route
@staff_bp.route('/complete_appointment/<string:appt_id>', methods=['POST'])
def complete_appointment(appt_id):
    db = get_db_connection()

    try:
        db.Appointments.update_one({"_id": ObjectId(appt_id)}, {"$set": {"appt_status": 'Completed'}})
        flash('Appointment completed successfully!', 'success')
    except Exception as e:
        flash('Error completing the appointment: {}'.format(str(e)), 'danger')

    return redirect(url_for('staff.manage_appointment'))

# Search medications route. Same feature as medications.
@staff_bp.route('/search_medications')
def search_medications():
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify([])  # Return empty if no query is provided

    db = get_db_connection()
    medications_collection = db['Medications']

    # Perform a case-insensitive search using regex and limit to 8 results
    medications = list(medications_collection.find({
        "name": {"$regex": query, "$options": "i"}
    }).limit(20))  # Adjust limit as necessary

    # Only return the name field for each medication
    results = [{"name": medication['name']} for medication in medications]

    return jsonify(results)