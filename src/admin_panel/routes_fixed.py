"""
Fixed version of the create_ticket function to handle foreign key violations
"""

@support.route('/tickets', methods=['POST'])
def create_ticket():
    try:
        token = request.cookies.get('access_token')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
            
        payload = verify_jwt(token)
        if not payload or 'user_id' not in payload:
            return jsonify({'error': 'Invalid token'}), 401
            
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        # Check if user has a valid company_id
        if not user.company_id:
            return jsonify({'error': 'Your account is not properly associated with a company. Please contact support.'}), 400
            
        # Verify the company exists
        company = Company.query.get(user.company_id)
        if not company:
            return jsonify({'error': 'Company not found. Please contact support.'}), 400
            
        # Handle form data with file upload
        subject = request.form.get('subject')
        topic = request.form.get('topic')
        details = request.form.get('details')
        
        if not subject or not topic or not details:
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Create the ticket
        try:
            ticket = SupportTicket(
                company_id=user.company_id,
                user_id=user.id,
                subject=subject,
                topic=topic,
                details=details,
                status='open'
            )
            
            db.session.add(ticket)
            db.session.commit()
            
            # Handle file upload if present
            if 'media' in request.files:
                file = request.files['media']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{user.id}_{uuid.uuid4().hex}_{filename}"
                    
                    # Create uploads directory if it doesn't exist
                    uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'support')
                    if not os.path.exists(uploads_dir):
                        os.makedirs(uploads_dir)
                    
                    file_path = os.path.join(uploads_dir, unique_filename)
                    file.save(file_path)
                    
                    # Use a relative path for storage in the database
                    relative_path = f"/static/uploads/support/{unique_filename}"
                    
                    attachment = MessageAttachment(
                        ticket_id=ticket.id,
                        file_path=relative_path,
                        file_name=filename,
                        file_type=file.content_type
                    )
                    
                    db.session.add(attachment)
                    db.session.commit()
            
            return jsonify({
                'success': True,
                'ticket': {
                    'id': ticket.id,
                    'ticket_number': ticket.ticket_number,
                    'remarks': ticket.remarks,
                    'subject': ticket.subject,
                    'topic': ticket.topic,
                    'status': ticket.status,
                    'created_at': ticket.created_at.isoformat(),
                    'details': ticket.details
                }
            }), 201
        except Exception as db_error:
            db.session.rollback()
            current_app.logger.error(f"Database error creating ticket: {str(db_error)}")
            raise db_error
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating support ticket: {str(e)}")
        
        # Check for foreign key violation
        if 'ForeignKeyViolation' in str(e):
            if 'company_id' in str(e):
                return jsonify({'error': 'Your account is not properly associated with a company. Please contact support for assistance.'}), 400
            elif 'user_id' in str(e):
                return jsonify({'error': 'User account validation failed. Please contact support for assistance.'}), 400
            else:
                return jsonify({'error': 'Database constraint error. Please contact support and provide this error message.'}), 400
        
        return jsonify({'error': 'An error occurred while submitting your ticket. Please try again later.'}), 400
