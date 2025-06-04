from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func, extract, text, and_
from chatbot.models import ChatMessage, ChatSession, ChatbotConfig as Chatbot
from core.database import db
from users.models import User
import logging
import traceback
from users.views import get_logged_in_company_id
import re

metrics_chat_bp = Blueprint('metrics_chat', __name__)

@metrics_chat_bp.route('/dashboard', methods=['GET'])
def get_dashboard_metrics():
    """
    Endpoint to get dashboard metrics for the current user's company
    """
    try:
        print("DEBUG: Starting get_dashboard_metrics")
        
        # Get company ID from session or token
        company_id, error_response, status_code = get_logged_in_company_id()
        if error_response:
            print("DEBUG: No company ID found")
            return error_response, status_code

        print(f"DEBUG: Processing metrics for company_id: {company_id}")

        # Get all chatbots for this company
        chatbots = Chatbot.query.filter_by(company_id=company_id).all()
        total_chatbots = len(chatbots)
        print(f"DEBUG: Found {total_chatbots} chatbots")

        # Calculate satisfaction rate
        print("DEBUG: Calculating satisfaction rate")
        total_feedback = db.session.query(func.count(ChatMessage.id)).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.feedback != None
        ).scalar() or 0
        
        print(f"DEBUG: Total feedback count: {total_feedback}")
        
        positive_feedback = db.session.query(func.count(ChatMessage.id)).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.feedback == 'positive'
        ).scalar() or 0
        
        print(f"DEBUG: Positive feedback count: {positive_feedback}")
        
        # Debug: Print all messages with feedback
        messages_with_feedback = db.session.query(ChatMessage).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.feedback != None
        ).all()
        
        print(f"DEBUG: Found {len(messages_with_feedback)} messages with feedback")
        for msg in messages_with_feedback:
            print(f"DEBUG: Message ID: {msg.id}, Feedback: {msg.feedback}, Rating: {msg.rating}")
        
        satisfaction_rate = 0
        if total_feedback > 0:
            satisfaction_rate = round((positive_feedback / total_feedback) * 100, 1)
        
        print(f"DEBUG: Calculated satisfaction rate: {satisfaction_rate}%")

        # Get total conversations
        total_conversations = db.session.query(func.count(ChatSession.id)).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id
        ).scalar() or 0

        # Get monthly conversations for current year
        current_year = datetime.now().year
        monthly_conversations = [0] * 12
        for month in range(1, 13):
            count = db.session.query(func.count(ChatSession.id)).join(
                Chatbot
            ).filter(
                Chatbot.company_id == company_id,
                func.extract('year', ChatSession.created_at) == current_year,
                func.extract('month', ChatSession.created_at) == month
            ).scalar() or 0
            monthly_conversations[month-1] = count

        # Get performance data
        excellent_count = db.session.query(func.count(ChatMessage.id)).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.rating == 5
        ).scalar() or 0

        good_count = db.session.query(func.count(ChatMessage.id)).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.rating == 4
        ).scalar() or 0

        average_count = db.session.query(func.count(ChatMessage.id)).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.rating == 3
        ).scalar() or 0

        poor_count = db.session.query(func.count(ChatMessage.id)).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.rating.in_([1, 2])
        ).scalar() or 0

        # Create performance data object
        performance_data = {
            'excellent': excellent_count,
            'good': good_count, 
            'average': average_count,
            'poor': poor_count
        }

        # Get average response time
        avg_response_time = db.session.query(func.avg(ChatMessage.response_time)).join(
            ChatSession
        ).join(
            Chatbot
        ).filter(
            Chatbot.company_id == company_id,
            ChatMessage.response_time.isnot(None)
        ).scalar() or 0

        # Prepare chatbot information for display
        chatbot_info = []
        for chatbot in chatbots:
            # Calculate total messages for this chatbot on-the-fly
            total_messages = db.session.query(func.count(ChatMessage.id)).join(
                ChatSession
            ).filter(
                ChatSession.chatbot_id == chatbot.id
            ).scalar() or 0

            # Calculate feedback stats for this chatbot
            chatbot_total_feedback = db.session.query(func.count(ChatMessage.id)).join(
                ChatSession
            ).filter(
                ChatSession.chatbot_id == chatbot.id,
                ChatMessage.feedback != None
            ).scalar() or 0

            chatbot_positive_feedback = db.session.query(func.count(ChatMessage.id)).join(
                ChatSession
            ).filter(
                ChatSession.chatbot_id == chatbot.id,
                ChatMessage.feedback == 'positive'
            ).scalar() or 0

            chatbot_satisfaction_rate = 0
            if chatbot_total_feedback > 0:
                chatbot_satisfaction_rate = round((chatbot_positive_feedback / chatbot_total_feedback) * 100, 1)

            chatbot_info.append({
                'id': chatbot.id,
                'bot_name': chatbot.bot_name or 'Untitled Chatbot',
                'version': chatbot.version,
                'total_messages': total_messages,
                'satisfaction_rate': chatbot_satisfaction_rate
            })

        print("DEBUG: Returning metrics response")
        # Return the metrics with real data
        return jsonify({
            'success': True,
            'total_chatbots': total_chatbots,
            'total_conversations': total_conversations,
            'avg_response_time': round(avg_response_time, 2),
            'monthly_conversations': monthly_conversations,
            'performance_data': performance_data,
            'satisfaction_rate': satisfaction_rate,
            'chatbots': chatbot_info
        })

    except Exception as e:
        print(f"DEBUG: Error in get_dashboard_metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@metrics_chat_bp.route('/chatbot/<int:chatbot_id>', methods=['GET'])
def get_chatbot_metrics(chatbot_id):
    """
    Endpoint to get metrics for a specific chatbot
    """
    try:
        # Get user from cookie or token
        token = request.cookies.get('access_token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required'
            }), 200  # Return 200 instead of 401 to prevent redirect
            
        # Verify the token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid token'
            }), 200  # Return 200 instead of 401 to prevent redirect
        
        # Get the user from the database
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 200  # Return 200 instead of 404 to prevent redirect
        
        # Get company ID from user
        company_id = user.company_id or user.id
        
        # Verify that the chatbot belongs to the user's company
        chatbot = Chatbot.query.filter_by(id=chatbot_id, company_id=company_id).first()
        if not chatbot:
            return jsonify({
                'success': False,
                'error': 'Chatbot not found or access denied'
            }), 200  # Return 200 instead of 404 to prevent redirect
        
        # Get time period from request parameters (default: 30 days)
        days = request.args.get('days', 30, type=int)
        period_start = datetime.now() - timedelta(days=days)
        
        # Total sessions
        sessions_count = ChatSession.query.filter_by(
            chatbot_id=chatbot_id
        ).filter(
            ChatSession.created_at >= period_start
        ).count()
        
        # Total messages
        messages_count = db.session.query(func.count(ChatMessage.id)).join(
            ChatSession
        ).filter(
            ChatSession.chatbot_id == chatbot_id,
            ChatMessage.timestamp >= period_start
        ).scalar() or 0
        
        # Average messages per session
        avg_messages_per_session = 0
        if sessions_count > 0:
            avg_messages_per_session = round(messages_count / sessions_count, 2)
        
        # Average session duration
        avg_duration = db.session.query(
            func.avg(ChatSession.updated_at - ChatSession.created_at)
        ).filter(
            ChatSession.chatbot_id == chatbot_id,
            ChatSession.created_at >= period_start,
            ChatSession.updated_at.isnot(None),
            ChatSession.ended == True
        ).scalar()
        
        avg_duration_seconds = 0
        if avg_duration:
            avg_duration_seconds = avg_duration.total_seconds()
        
        return jsonify({
            'success': True,
            'sessions_count': sessions_count,
            'messages_count': messages_count,
            'avg_messages_per_session': avg_messages_per_session,
            'avg_duration_seconds': avg_duration_seconds,
            'avg_rating': 4.5,  # Mock value
            'rating_count': 10  # Mock value
        })
    
    except Exception as e:
        logging.error(f"Error getting chatbot metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve chatbot metrics'
        }), 500

@metrics_chat_bp.route('/analysis', methods=['POST'])
def get_chat_analysis():
    """
    Endpoint to get chat analysis data including bookings, complaints, and potential clients
    """
    try:
        # Get company ID from session or token
        company_id, error_response, status_code = get_logged_in_company_id()
        if error_response:
            print("DEBUG: No company ID found for chat analysis")
            return error_response, status_code

        print(f"DEBUG: Processing chat analysis for company_id: {company_id}")
        
        data = request.json or {}
        
        # Get filter parameters
        chat_type = data.get('chatType', 'all')
        date_range = data.get('dateRange', 'all')
        search_query = data.get('searchQuery', '')
        
        # Determine date filter based on range
        date_filter = None
        if date_range != 'all':
            days = int(date_range)
            date_filter = datetime.utcnow() - timedelta(days=days)
        
        # Query chat sessions for the company (fetch sessions only)
        session_query = db.session.query(ChatSession).join(
            Chatbot, ChatSession.chatbot_id == Chatbot.id
        ).filter(
            Chatbot.company_id == company_id
        )
        if date_filter:
            session_query = session_query.filter(ChatSession.created_at >= date_filter)
        chat_sessions = session_query.order_by(ChatSession.created_at.desc()).all()
        
        # Initialize counters
        total_chats = len(chat_sessions)
        total_bookings = 0
        total_complaints = 0
        potential_clients = 0
        
        # Initialize chat list
        chats = []
        
        # Process each chat session
        for session in chat_sessions:
            # Get all messages for this session
            messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.timestamp.asc()).all()
            
            # Skip empty sessions
            if not messages:
                continue
                
            # Determine chat type and status by analyzing messages
            chat_type_result = classify_chat(messages)
            
            # Apply chat type filter if specified
            if chat_type != 'all' and chat_type_result['type'] != chat_type:
                continue
                
            # Apply search filter if specified
            if search_query and not message_contains_search(messages, search_query):
                continue
                
            # Update counters
            if chat_type_result['type'] == 'booking':
                total_bookings += 1
            elif chat_type_result['type'] == 'complaint':
                total_complaints += 1
            elif chat_type_result['type'] == 'potential':
                potential_clients += 1
                
            # Get customer info if available
            customer_name = None
            user = None
            try:
                # Try to find user details in messages
                for msg in messages:
                    if msg.sender == 'user' and hasattr(msg, 'user_id') and msg.user_id:
                        user = User.query.get(msg.user_id)
                        if user:
                            customer_name = user.user_name
                            break
            except Exception as e:
                print(f"DEBUG: Error getting customer info: {str(e)}")
                
            # Create chat preview based on the first user message
            first_user = None
            for msg in messages:
                if msg.sender == 'user':
                    first_user = msg
                    break
            if first_user:
                preview_source = first_user.message
            else:
                preview_source = messages[0].message
            preview = (preview_source[:50] + '...') if len(preview_source) > 50 else preview_source
            
            # Add to chat list
            chats.append({
                'id': session.id,
                'timestamp': session.created_at.isoformat(),
                'type': chat_type_result['type'],
                'status': chat_type_result['status'],
                'customer': customer_name,
                'preview': preview,
                'message_count': len(messages)
            })
            
        return jsonify({
            'success': True,
            'totalChats': total_chats,
            'totalBookings': total_bookings,
            'totalComplaints': total_complaints,
            'potentialClients': potential_clients,
            'chats': chats
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_chat_analysis: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@metrics_chat_bp.route('/<int:chat_id>/detail', methods=['GET'])
def get_chat_detail(chat_id):
    """
    Endpoint to get detailed information about a specific chat session
    """
    try:
        # Get company ID from session or token
        company_id, error_response, status_code = get_logged_in_company_id()
        if error_response:
            print("DEBUG: No company ID found for chat detail")
            return error_response, status_code
            
        print(f"DEBUG: Getting chat detail for chat_id: {chat_id}, company_id: {company_id}")
        
        # Get the chat session
        session = ChatSession.query.join(
            Chatbot, ChatSession.chatbot_id == Chatbot.id
        ).filter(
            ChatSession.id == chat_id,
            Chatbot.company_id == company_id
        ).first()
        
        if not session:
            return jsonify({
                'success': False,
                'error': 'Chat session not found'
            }), 404
            
        # Get all messages for this session
        messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.timestamp.asc()).all()
        
        # Determine chat type by analyzing messages
        chat_info = classify_chat(messages)
        
        # Get customer info if available
        customer_info = None
        try:
            # Try to find user details in messages
            for msg in messages:
                if msg.sender == 'user' and hasattr(msg, 'user_id') and msg.user_id:
                    user = User.query.get(msg.user_id)
                    if user:
                        customer_info = {
                            'name': user.user_name,
                            'email': user.user_email,
                            'phone': getattr(user, 'user_phone', None)
                        }
                        break
                        
            # If we didn't find customer info in messages, try to get it from the booking
            if not customer_info and chat_info['type'] == 'booking':
                try:
                    from chatbot.moving_models import MovingBooking
                    # Convert session.id to integer explicitly for proper type handling
                    booking = MovingBooking.query.filter_by(session_id=session.id).first()
                    if booking:
                        customer_info = {
                            'name': booking.customer_name,
                            'email': booking.customer_email,
                            'phone': booking.customer_phone
                        }
                except Exception as e:
                    print(f"DEBUG: Error getting customer info from booking: {str(e)}")
                
        except Exception as e:
            print(f"DEBUG: Error getting customer info: {str(e)}")
            
        # If still no customer_info and this is a complaint, fetch from stored conversation state
        if not customer_info and chat_info.get('type') == 'complaint':
            try:
                from chatbot.moving_models import MovingConversationState
                # session_id stored as string in state table
                state_rec = MovingConversationState.query.filter_by(session_id=str(session.id)).order_by(MovingConversationState.updated_at.desc()).first()
                if state_rec:
                    comp_info = state_rec.collected_info.get('complaint_info', {}) or {}
                    if comp_info:
                        customer_info = {
                            'name': comp_info.get('customer_name'),
                            'email': comp_info.get('customer_email'),
                            'phone': comp_info.get('customer_phone')
                        }
            except Exception as e:
                print(f"DEBUG: Error getting customer info from conversation state: {e}")
        
        # Get booking details if this is a booking
        booking_details = None
        if chat_info['type'] == 'booking':
            try:
                from chatbot.moving_models import MovingBooking
                from core.database import db
                
                # Ensure clean transaction state
                db.session.rollback()
                
                # Use a column-specific query to avoid schema issues
                try:
                    # Query only the specific columns we need
                    booking = db.session.query(
                        MovingBooking.booking_reference,
                        MovingBooking.move_date,
                        MovingBooking.origin,
                        MovingBooking.destination,
                        MovingBooking.move_size,
                        MovingBooking.total_min_cost,
                        MovingBooking.total_max_cost,
                        MovingBooking.distance_miles,
                        MovingBooking.has_packing,
                        MovingBooking.has_storage,
                        MovingBooking.status,
                        MovingBooking.created_at
                    ).filter(MovingBooking.session_id == session.id).first()
                    
                    if booking:
                        # Format costs as currency
                        total_min_cost = f"${booking.total_min_cost:.2f}" if booking.total_min_cost else "N/A"
                        total_max_cost = f"${booking.total_max_cost:.2f}" if booking.total_max_cost else "N/A"
                        total_cost = f"{total_min_cost} - {total_max_cost}"
                        
                        # Format services info
                        services = []
                        if booking.has_packing:
                            services.append("Packing")
                        if booking.has_storage:
                            services.append("Storage")
                        
                        services_text = ", ".join(services) if services else "None"
                        
                        booking_details = {
                            'booking_reference': booking.booking_reference,
                            'move_date': booking.move_date.isoformat() if booking.move_date else None,
                            'origin': booking.origin,
                            'destination': booking.destination,
                            'move_size': booking.move_size,
                            'total_cost': total_cost,
                            'distance_miles': f"{booking.distance_miles:.1f} miles" if booking.distance_miles else "N/A",
                            'services': services_text,
                            'status': booking.status,
                            'created_at': booking.created_at.isoformat() if booking.created_at else None
                        }
                    else:
                        print(f"DEBUG: No booking found for session_id={session.id}")
                        
                except Exception as query_error:
                    print(f"DEBUG: Error in ORM query for booking: {query_error}")
                    db.session.rollback()
                    
                    # Fallback to raw SQL query
                    try:
                        sql = """
                        SELECT booking_reference, move_date, origin, destination, move_size, 
                               total_min_cost, total_max_cost, distance_miles, has_packing, 
                               has_storage, status, created_at
                        FROM moving_bookings
                        WHERE session_id = :session_id
                        """
                        with db.engine.connect() as conn:
                            result = conn.execute(text(sql), {"session_id": session.id})
                            raw_booking = result.first()
                        
                        if raw_booking:
                            # Format costs as currency
                            total_min_cost = f"${raw_booking[5]:.2f}" if raw_booking[5] else "N/A"
                            total_max_cost = f"${raw_booking[6]:.2f}" if raw_booking[6] else "N/A"
                            total_cost = f"{total_min_cost} - {total_max_cost}"
                            
                            # Format services info
                            services = []
                            if raw_booking[8]:  # has_packing
                                services.append("Packing")
                            if raw_booking[9]:  # has_storage
                                services.append("Storage")
                            
                            services_text = ", ".join(services) if services else "None"
                            
                            booking_details = {
                                'booking_reference': raw_booking[0],
                                'move_date': raw_booking[1].isoformat() if raw_booking[1] else None,
                                'origin': raw_booking[2],
                                'destination': raw_booking[3],
                                'move_size': raw_booking[4],
                                'total_cost': total_cost,
                                'distance_miles': f"{raw_booking[7]:.1f} miles" if raw_booking[7] else "N/A",
                                'services': services_text,
                                'status': raw_booking[10],
                                'created_at': raw_booking[11].isoformat() if raw_booking[11] else None
                            }
                        else:
                            print(f"DEBUG: No booking found in SQL query for session_id={session.id}")
                    except Exception as sql_error:
                        print(f"DEBUG: Error in fallback SQL query for booking: {sql_error}")
                        db.session.rollback()
                        
                        # Try querying from the view as a last resort
                        try:
                            sql = """
                            SELECT booking_reference, move_date, origin, destination, move_size, 
                                   total_min_cost, total_max_cost, distance_miles, has_packing, 
                                   has_storage, status, created_at
                            FROM moving_bookings_with_metadata
                            WHERE session_id = :session_id
                            """
                            with db.engine.connect() as conn:
                                result = conn.execute(text(sql), {"session_id": session.id})
                                raw_booking = result.first()
                            
                            if raw_booking:
                                # Format costs as currency
                                total_min_cost = f"${raw_booking[5]:.2f}" if raw_booking[5] else "N/A"
                                total_max_cost = f"${raw_booking[6]:.2f}" if raw_booking[6] else "N/A"
                                total_cost = f"{total_min_cost} - {total_max_cost}"
                                
                                # Format services info
                                services = []
                                if raw_booking[8]:  # has_packing
                                    services.append("Packing")
                                if raw_booking[9]:  # has_storage
                                    services.append("Storage")
                                
                                services_text = ", ".join(services) if services else "None"
                                
                                booking_details = {
                                    'booking_reference': raw_booking[0],
                                    'move_date': raw_booking[1].isoformat() if raw_booking[1] else None,
                                    'origin': raw_booking[2],
                                    'destination': raw_booking[3],
                                    'move_size': raw_booking[4],
                                    'total_cost': total_cost,
                                    'distance_miles': f"{raw_booking[7]:.1f} miles" if raw_booking[7] else "N/A",
                                    'services': services_text,
                                    'status': raw_booking[10],
                                    'created_at': raw_booking[11].isoformat() if raw_booking[11] else None
                                }
                                print(f"DEBUG: Successfully retrieved booking details from view")
                            else:
                                print(f"DEBUG: No booking found in view for session_id={session.id}")
                        except Exception as view_error:
                            print(f"DEBUG: Error querying view for booking: {view_error}")
                            db.session.rollback()
            except Exception as e:
                print(f"DEBUG: Error getting booking details: {str(e)}")
                traceback.print_exc()
                # Make sure to rollback any failed transaction
                try:
                    db.session.rollback()
                except Exception:
                    pass
        
        # Override customer name for complaints if the stored name is not plausible
        if chat_info['type'] == 'complaint' and customer_info:
            stored_name = customer_info.get('name') or ''
            # Check for at least two capitalized words (e.g., 'John Doe')
            if not re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)+$', stored_name):
                for msg in messages:
                    if msg.sender == 'user':
                        candidate = msg.message.strip()
                        # Match names like 'First Last' with capitalized words
                        if re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)+$', candidate):
                            customer_info['name'] = candidate
                            break
        
        # Format messages for response
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'sender': msg.sender,
                'message': msg.message,
                'timestamp': msg.timestamp.isoformat(),
                'feedback': msg.feedback,
                'rating': msg.rating
            })
            
        return jsonify({
            'success': True,
            'id': session.id,
            'timestamp': session.created_at.isoformat(),
            'type': chat_info['type'],
            'status': chat_info['status'],
            'customer': customer_info,
            'booking': booking_details,
            'complaint': None,
            'messages': message_list
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_chat_detail: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@metrics_chat_bp.route('/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """
    Endpoint to delete a chat session and its messages for the current company
    """
    # Get company ID from session or token
    company_id, error_response, status_code = get_logged_in_company_id()
    if error_response:
        return error_response, status_code

    # Verify that the chat session belongs to the user's company
    session = ChatSession.query.join(
        Chatbot, ChatSession.chatbot_id == Chatbot.id
    ).filter(
        ChatSession.id == chat_id,
        Chatbot.company_id == company_id
    ).first()
    if not session:
        return jsonify({'success': False, 'error': 'Chat session not found or access denied'}), 404

    try:
        # Delete associated user details if they exist
        if getattr(session, 'user_details', None):
            db.session.delete(session.user_details)
        # Delete the chat session (messages cascade via relationship)
        db.session.delete(session)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting chat session: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper function to classify chat type based on message content
def classify_chat(messages):
    """
    Analyze chat messages to determine the type and status of conversation
    """
    # Default classification
    classification = {
        'type': 'general',
        'status': 'completed'
    }
    
    # Pre-scan for complaint keywords: prioritize complaint classification
    complaint_triggers = [
        'complain', 'unhappy', 'dissatisfied', 'disappointed', 'issue', 'problem',
        'terrible', 'awful', 'bad service', 'poor service', 'not satisfied',
        'unacceptable', 'frustrated', 'complaint', 'wrong', 'damaged', 'late',
        'lost my', 'missing', 'failed to', 'never showed', 'never arrived', 'didnt show'
    ]
    for msg in messages:
        text = msg.message.lower()
        if any(keyword in text for keyword in complaint_triggers):
            # Found a complaint keyword, classify as complaint
            return {'type': 'complaint', 'status': 'open'}
    
    # Extract chat session ID from first message if available
    session_id = None
    if messages and len(messages) > 0:
        session_id = messages[0].session_id
    
    # Check if there's a booking record for this session
    if session_id:
        try:
            from chatbot.moving_models import MovingBooking
            from core.database import db
            
            # First, ensure we have a clean transaction state
            db.session.rollback()
            
            try:
                # Try a simpler query that doesn't select all columns
                booking = db.session.query(
                    MovingBooking.id,
                    MovingBooking.status
                ).filter(MovingBooking.session_id == session_id).first()
                
                if booking:
                    # We found an actual booking, so this is definitely a booking conversation
                    classification['type'] = 'booking'
                    classification['status'] = booking.status
                    # Return early since we've confirmed the type from database
                    db.session.rollback()  # Clean up transaction
                    return classification
            except Exception as query_error:
                # Log the error and rollback the transaction
                print(f"DEBUG: Error querying booking by session_id: {query_error}")
                db.session.rollback()
                
                # Try a raw SQL query as fallback
                try:
                    with db.engine.connect() as conn:
                        result = conn.execute(
                            text("SELECT id, status FROM moving_bookings WHERE session_id = :session_id"), 
                            {"session_id": session_id}
                        )
                        booking_data = result.first()
                    if booking_data:
                        classification['type'] = 'booking'
                        classification['status'] = booking_data[1]  # status is the second column
                        return classification
                except Exception as sql_error:
                    print(f"DEBUG: Error in fallback SQL query: {sql_error}")
                    db.session.rollback()
                    
                    # Try querying from the view as a last resort
                    try:
                        with db.engine.connect() as conn:
                            result = conn.execute(
                                text("SELECT id, status FROM moving_bookings_with_metadata WHERE session_id = :session_id"), 
                                {"session_id": session_id}
                            )
                            booking_data = result.first()
                        if booking_data:
                            classification['type'] = 'booking'
                            classification['status'] = booking_data[1]  # status is the second column
                            return classification
                    except Exception as view_error:
                        print(f"DEBUG: Error querying view: {view_error}")
                        db.session.rollback()
        except Exception as e:
            print(f"DEBUG: Error checking for booking record: {str(e)}")
            # Make sure to rollback any failed transaction
            try:
                from core.database import db
                db.session.rollback()
            except Exception:
                pass
    
    # Check if this is a booking conversation
    booking_keywords = ['book', 'reservation', 'schedule', 'appointment', 'moving date', 'confirm', 'booking']
    booking_confirmed_keywords = ['confirmed', 'booked', 'scheduled', 'appointment confirmed', 'reservation confirmed', 
                                'booking reference', 'thank you for your booking', 'booking is confirmed']
    
    # Check if this is a complaint (extended triggers)
    complaint_keywords = ['complain', 'unhappy', 'dissatisfied', 'disappointed', 'issue', 'problem',
                          'terrible', 'awful', 'bad service', 'poor service', 'not satisfied',
                          'unacceptable', 'frustrated', 'complaint', 'wrong', 'damaged', 'late',
                          'lost my', 'missing', 'failed to', 'never showed', 'never arrived', 'didnt show']
    
    # Check if this is a potential client (showed interest but didn't book)
    potential_keywords = ['price', 'cost', 'quote', 'estimate', 'how much', 'interested', 'considering', 'thinking about']
    
    # Initialize counters
    booking_score = 0
    complaint_score = 0
    potential_score = 0
    
    # Check last message from bot to determine status
    last_bot_message = None
    for message in reversed(messages):
        if message.sender == 'bot':
            last_bot_message = message.message.lower()
            break
    
    # Analyze messages
    for message in messages:
        message_text = message.message.lower()
        
        # Check for booking confirmation in bot messages
        if message.sender == 'bot':
            for keyword in booking_confirmed_keywords:
                if keyword in message_text:
                    booking_score += 3  # Stronger signal when bot confirms
                    break
        
        # Check for booking keywords in user messages
        if message.sender == 'user':
            # Check for booking keywords
            for keyword in booking_keywords:
                if keyword in message_text:
                    booking_score += 1
                    
            # Check for complaint keywords
            for keyword in complaint_keywords:
                if keyword in message_text:
                    complaint_score += 1
                    
            # Check for potential client keywords
            for keyword in potential_keywords:
                if keyword in message_text:
                    potential_score += 1
    
    # Determine the type based on scores
    if booking_score > complaint_score and booking_score > potential_score:
        classification['type'] = 'booking'
        
        # Check if booking was confirmed
        if last_bot_message:
            for keyword in booking_confirmed_keywords:
                if keyword in last_bot_message:
                    classification['status'] = 'confirmed'
                    break
            else:
                classification['status'] = 'pending'
    elif complaint_score > booking_score and complaint_score > potential_score:
        classification['type'] = 'complaint'
        classification['status'] = 'open'
    elif potential_score > 0 and booking_score < 3:  # Some interest but not enough booking signals
        classification['type'] = 'potential'
    
    return classification

# Helper function to check if any message contains the search query
def message_contains_search(messages, search_query):
    """
    Check if any message in the conversation contains the search query
    """
    search_query = search_query.lower()
    for message in messages:
        if search_query in message.message.lower():
            return True
    return False
