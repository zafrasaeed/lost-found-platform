"""
Matching API
Endpoints for retrieving matches for a report
"""

from flask import Blueprint, jsonify, request, current_app
from database import db_connection
from datetime import datetime

matching_bp = Blueprint('matching', __name__)

@matching_bp.route('/report/<int:report_id>', methods=['GET'])
def get_matches(report_id):
    """
    Get all matches for a specific report
    Returns matches sorted by score (descending)
    """
    try:
        with db_connection(current_app) as db:
            cursor = db.cursor()
            
            # Get the report
            cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
            report = cursor.fetchone()
            
            if not report:
                return jsonify({'error': 'Report not found'}), 404
            
            report = dict(report)
            
            # Get all matches for this report
            if report['type'] == 'Lost':
                cursor.execute('''
                    SELECT m.id, m.lost_report_id, m.found_report_id,
                           m.match_score, m.image_similarity,
                           m.semantic_similarity, m.location_similarity,
                           m.time_similarity, m.reasons, m.status,
                           m.created_at,
                           f.title, f.description, f.location, f.date_time,
                           f.user_name, f.user_contact
                    FROM matches m
                    JOIN reports f ON m.found_report_id = f.id
                    WHERE m.lost_report_id = ?
                    ORDER BY m.match_score DESC
                ''', (report_id,))
            else:  # Found report
                cursor.execute('''
                    SELECT m.id, m.lost_report_id, m.found_report_id,
                           m.match_score, m.image_similarity,
                           m.semantic_similarity, m.location_similarity,
                           m.time_similarity, m.reasons, m.status,
                           m.created_at,
                           l.title, l.description, l.location, l.date_time,
                           l.user_name, l.user_contact
                    FROM matches m
                    JOIN reports l ON m.lost_report_id = l.id
                    WHERE m.found_report_id = ?
                    ORDER BY m.match_score DESC
                ''', (report_id,))
            
            rows = cursor.fetchall()
            matches = []
            
            for row in rows:
                row_dict = dict(row)
                matches.append({
                    'match_id': row_dict['id'],
                    'other_report_id': row_dict['found_report_id'] if report['type'] == 'Lost' else row_dict['lost_report_id'],
                    'title': row_dict['title'],
                    'description': row_dict['description'],
                    'location': row_dict['location'],
                    'date_time': row_dict['date_time'],
                    'user_name': row_dict['user_name'],
                    'user_contact': row_dict['user_contact'],
                    'match_score': round(row_dict['match_score'] * 100, 1),
                    'image_similarity': round(row_dict['image_similarity'] * 100, 1),
                    'semantic_similarity': round(row_dict['semantic_similarity'] * 100, 1),
                    'location_similarity': round(row_dict['location_similarity'] * 100, 1),
                    'time_similarity': round(row_dict['time_similarity'] * 100, 1),
                    'reasons': row_dict['reasons'].split(',') if row_dict['reasons'] else [],
                    'status': row_dict['status'],
                    'created_at': row_dict['created_at']
                })
            
            return jsonify({
                'report': {
                    'id': report['id'],
                    'type': report['type'],
                    'title': report['title'],
                    'description': report['description'],
                    'location': report['location'],
                    'date_time': report['date_time']
                },
                'matches': matches,
                'count': len(matches)
            }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@matching_bp.route('/<int:match_id>', methods=['GET'])
def get_match_details(match_id):
    """Get detailed information about a specific match"""
    try:
        with db_connection(current_app) as db:
            cursor = db.cursor()
            
            cursor.execute('''
                SELECT m.*, 
                       l.title as lost_title, l.description as lost_desc,
                       l.location as lost_location, l.date_time as lost_time,
                       l.user_name as lost_user,
                       f.title as found_title, f.description as found_desc,
                       f.location as found_location, f.date_time as found_time,
                       f.user_name as found_user
                FROM matches m
                JOIN reports l ON m.lost_report_id = l.id
                JOIN reports f ON m.found_report_id = f.id
                WHERE m.id = ?
            ''', (match_id,))
            
            match = cursor.fetchone()
            
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            match_dict = dict(match)
            
            return jsonify({
                'match_id': match_dict['id'],
                'match_score': round(match_dict['match_score'] * 100, 1),
                'image_similarity': round(match_dict['image_similarity'] * 100, 1),
                'semantic_similarity': round(match_dict['semantic_similarity'] * 100, 1),
                'location_similarity': round(match_dict['location_similarity'] * 100, 1),
                'time_similarity': round(match_dict['time_similarity'] * 100, 1),
                'reasons': match_dict['reasons'].split(',') if match_dict['reasons'] else [],
                'status': match_dict['status'],
                'lost_report': {
                    'id': match_dict['lost_report_id'],
                    'title': match_dict['lost_title'],
                    'description': match_dict['lost_desc'],
                    'location': match_dict['lost_location'],
                    'date_time': match_dict['lost_time'],
                    'user_name': match_dict['lost_user']
                },
                'found_report': {
                    'id': match_dict['found_report_id'],
                    'title': match_dict['found_title'],
                    'description': match_dict['found_desc'],
                    'location': match_dict['found_location'],
                    'date_time': match_dict['found_time'],
                    'user_name': match_dict['found_user']
                }
            }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
