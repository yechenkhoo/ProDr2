# This file contains the blueprint components for medications.
# It includes the function to manage medications.

from flask import render_template, request, redirect, session, url_for, flash, jsonify
from . import medication_bp
from db import get_db_connection
from datetime import datetime
from bson.objectid import ObjectId, InvalidId
from db_config import DatabaseManager

def is_valid_objectid(oid):
    try:
        ObjectId(oid)
        return True
    except InvalidId:
        return False

@medication_bp.route('/medications')
def medications():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to access the Medication List.")
        return redirect(url_for('patient.patient_dashboard'))

    db = get_db_connection()
    medications_collection = db['Medications']

    search_query = request.args.get('search')

    # Get the current page (default to 1) and set number of medications per page for table
    page = request.args.get('page', 1, type=int)
    per_page = 100  # Limit the number of items displayed per page for table
    
    # Build the query for medications
    if search_query:
        query = {"name": {"$regex": search_query, "$options": "i"}}
    else:
        query = {}

    total_medications = medications_collection.count_documents(query)

    # Calculate total number of pages for pagination
    total_pages = (total_medications // per_page) + (1 if total_medications % per_page > 0 else 0)

    # Ensure the page number is within valid bounds
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages

    # Fetch the medications for the current page, limited by per_page (pagination applied here)
    medications = list(medications_collection.find(query).sort("name", 1).skip((page - 1) * per_page).limit(per_page))

    return render_template('medications.html', medications=medications, page=page, total_pages=total_pages, search=search_query)

@medication_bp.route('/search_medications')
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

# Medication quantity updates route
@medication_bp.route('/update_medication_quantity', methods=['POST'])
def update_medication_quantity():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to update medication quantities.")
        return redirect(url_for('patient.patient_dashboard'))

    # Get the form data
    medication_id = request.form.get('medication_id')
    quantity_change = request.form.get('quantity_change')

    # Check for valid medication_id and quantity
    if not medication_id or not quantity_change:
        flash('Invalid input, please try again.', 'danger')
        return redirect(url_for('medication.medications'))

    try:
        quantity_change = int(quantity_change)
    except ValueError:
        flash('Quantity change must be a number.', 'danger')
        return redirect(url_for('medication.medications'))

    if not is_valid_objectid(medication_id):
        flash('Invalid medication ID format.', 'danger')
        return redirect(url_for('medication.medications'))

    db_manager = DatabaseManager()
    db = db_manager.get_db()
    
    # Fetch current medication details
    medication = db.Medications.find_one({"_id": ObjectId(medication_id)})
    if not medication:
        flash('Medication not found.', 'danger')
        return redirect(url_for('medication.medications'))

    # Use atomic update operation
    success = db_manager.atomic_update_medication_quantity(ObjectId(medication_id), quantity_change)
    
    if success:
        # Add inventory tracking log
        db.InventoryLogs.insert_one({
            "MedID": ObjectId(medication_id),
            "change_type": 'addition' if quantity_change > 0 else 'subtract',
            "quantity_changed": abs(quantity_change),
            "date": datetime.now()
        })
        
        new_quantity = medication['quantity'] + quantity_change
        flash(f'Medication "{medication["name"]}" updated. New quantity: {new_quantity}', 'success')
    else:
        flash('Cannot update quantity. Insufficient stock or concurrent update in progress.', 'danger')

    return redirect(url_for('medication.medications'))

# Adding med route
@medication_bp.route('/manage_medication', methods=['POST'])
def manage_medication():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to add medications.")
        return redirect(url_for('patient.patient_dashboard'))

    # Get form data
    name = request.form.get('name')
    form = request.form.get('form')
    dosage = request.form.get('dosage')
    quantity = request.form.get('quantity')
    indication = request.form.get('indication')

    if not (name and form and dosage and quantity and indication):
        flash('All fields are required to add a medication.', 'danger')
        return redirect(url_for('medication.medications'))

    try:
        quantity = int(quantity)
    except ValueError:
        flash('Quantity must be a number.', 'danger')
        return redirect(url_for('medication.medications'))

    db = get_db_connection()
    medications_collection = db['Medications']

    # Fetch the last medication to determine the highest MedID
    last_medication = list(medications_collection.find().sort("MedID", -1).limit(1))
    last_med_id = last_medication[0]["MedID"] if len(last_medication) > 0 else 0
    new_med_id = last_med_id + 1

    # Insert new medication into the Medications collection
    medications_collection.insert_one({
        "MedID": new_med_id,
        "name": name,
        "form": form,
        "dosage": dosage,
        "quantity": quantity,
        "indication": indication
    })

    flash(f'Medication "{name}" added successfully with MedID {new_med_id}.', 'success')

    return redirect(url_for('medication.medications'))

# Deleting med route
@medication_bp.route('/delete_medication', methods=['POST'])
def delete_medication():
    if not session.get('is_staff') == 1:
        flash("You do not have permission to delete medications.")
        return redirect(url_for('patient.patient_dashboard'))

    medication_id = request.form.get('medication_id')

    if not medication_id:
        flash('Invalid medication ID, please try again.', 'danger')
        return redirect(url_for('medication.medications'))

    if not is_valid_objectid(medication_id):
        flash('Invalid medication ID format.', 'danger')
        return redirect(url_for('medication.medications'))

    db = get_db_connection()
    medications_collection = db['Medications']

    # Pre-check to see if medication exists
    medication = medications_collection.find_one({"_id": ObjectId(medication_id)})

    if not medication:
        flash('Medication not found.', 'danger')
        return redirect(url_for('medication.medications'))

    # Delete the medication from the collection
    medications_collection.delete_one({"_id": ObjectId(medication_id)})

    flash(f'Medication "{medication["name"]}" deleted successfully.', 'success')

    return redirect(url_for('medication.medications'))
