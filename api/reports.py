"""
Reports API
Endpoints for creating and managing Lost/Found reports
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from pathlib import Path
import os
from datetime import datetime
from database import db_connection
from ai_matching import MatchingEngine

reports_bp = Blueprint('reports', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save uploaded file and return path"""
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        return None
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    filename = timestamp + filename
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    Path(upload_folder).mkdir(exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    
    return filepath

@reports_bp.route('', methods=['POST'])
def create_report():
    """
    Create a new Lost or Found report
    
    Form data:
    - type: 'Lost' or 'Found'
    - title: Item title
    - description: Detailed description
    - location: Location text
    - latitude: Optional latitude
    - longitude: Optional longitude
    - date_time: ISO datetime string
    - user_name: Reporter name
    - user_contact: Contact info (email/phone)
    - image: Image file
    - secret_details: Hidden details for ownership verification
    """
    try:
        # Validate required fields
        required_fields = ['type', 'title', 'description', 'location', 
                          'date_time', 'user_name', 'user_contact', 'secret_details']
        
        for field in required_fields:
            if field not in request.form:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        if request.form['type'] not in ['Lost', 'Found']:
            return jsonify({'error': 'Invalid type. Must be Lost or Found'}), 400
        
        # Handle image upload
        image_path = None
        if 'image' in request.files:
            image_path = save_uploaded_file(request.files['image'])
        
        if not image_path:
            return jsonify({'error': 'Image file required and must be valid'}), 400
        
        # Parse optional location coordinates
        latitude = None
        longitude = None
        if 'latitude' in request.form and 'longitude' in request.form:
            try:
                latitude = float(request.form['latitude'])
                longitude = float(request.form['longitude'])
            except:
                pass
        
        # Insert into database
        with db_connection(current_app) as db:
            cursor = db.cursor()
            
            cursor.execute('''
                INSERT INTO reports (
                    type, title, description, image_path, location,
                    latitude, longitude, date_time, user_name, user_contact,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request.form['type'],
                request.form['title'],
                request.form['description'],
                image_path,
                request.form['location'],
                latitude,
                longitude,
                request.form['date_time'],
                request.form['user_name'],
                request.form['user_contact'],
                'active',
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            report_id = cursor.lastrowid
            
            # Insert secret details (private verification)
            cursor.execute('''
                INSERT INTO private_verification (
                    report_id, secret_details, created_at
                ) VALUES (?, ?, ?)
            ''', (
                report_id,
                request.form['secret_details'],
                datetime.now().isoformat()
            ))
            
            # Get the created report
            cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
            report = dict(cursor.fetchone())
            
            # Find potential matches
            matches = MatchingEngine.find_matches(report, db)
            
            # Store matches in database
            for match_data in matches:
                if report['type'] == 'Lost':
                    cursor.execute('''
                        INSERT OR IGNORE INTO matches (
                            lost_report_id, found_report_id,
                            match_score, image_similarity,
                            semantic_similarity, location_similarity,
                            time_similarity, reasons, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        report_id,
                        match_data['candidate_id'],
                        match_data['score'],
                        match_data['image_similarity'],
                        match_data['semantic_similarity'],
                        match_data['location_similarity'],
                        match_data['time_similarity'],
                        ','.join(match_data['reasons']),
                        'pending',
                        datetime.now().isoformat()
                    ))
                else:  # Found
                    cursor.execute('''
                        INSERT OR IGNORE INTO matches (
                            lost_report_id, found_report_id,
                            match_score, image_similarity,
                            semantic_similarity, location_similarity,
                            time_similarity, reasons, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        match_data['candidate_id'],
                        report_id,
                        match_data['score'],
                        match_data['image_similarity'],
                        match_data['semantic_similarity'],
                        match_data['location_similarity'],
                        match_data['time_similarity'],
                        ','.join(match_data['reasons']),
                        'pending',
                        datetime.now().isoformat()
                    ))
            
            return jsonify({
                'success': True,
                'report_id': report_id,
                'message': f'Report created successfully. Found {len(matches)} potential matches.',
                'matches_count': len(matches)
            }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/<int:report_id>', methods=['GET'])
def get_report(report_id):
    """Get report details (public info only, no secret verification)"""
    try:
        with db_connection(current_app) as db:
            cursor = db.cursor()
            cursor.execute(
                'SELECT id, type, title, description, image_path, location, date_time, user_name, user_contact, status, created_at FROM reports WHERE id = ?',
                (report_id,)
            )
            report = cursor.fetchone()
            
            if not report:
                return jsonify({'error': 'Report not found'}), 404
            
            return jsonify(dict(report)), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reports_bp.route('', methods=['GET'])
def list_reports():
    """List all active reports, optionally filtered by type"""
    try:
        report_type = request.args.get('type')  # 'Lost' or 'Found'
        
        with db_connection(current_app) as db:
            cursor = db.cursor()
            
            if report_type and report_type in ['Lost', 'Found']:
                cursor.execute(
                    'SELECT id, type, title, description, location, date_time, user_name, status FROM reports WHERE type = ? AND status = ? ORDER BY created_at DESC',
                    (report_type, 'active')
                )
            else:
                cursor.execute(
                    'SELECT id, type, title, description, location, date_time, user_name, status FROM reports WHERE status = ? ORDER BY created_at DESC',
                    ('active',)
                )
            
            reports = [dict(row) for row in cursor.fetchall()]
            return jsonify(reports), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
