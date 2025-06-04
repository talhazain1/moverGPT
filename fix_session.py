"""
Fix session management issues for moving parameters
"""

from flask import Flask, request, jsonify, make_response
import os
import sys
import jwt
import datetime

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your actual secret key

@app.route('/debug/session', methods=['GET'])
def debug_session():
    """Debug endpoint to check session cookies and headers."""
    auth_header = request.headers.get('Authorization')
    cookies = {key: value for key, value in request.cookies.items()}
    
    # Create a test token
    test_token = jwt.encode(
        {
            'user_id': 1,
            'company_id': 1,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
        },
        app.secret_key,
        algorithm='HS256'
    )
    
    # Create response with debug info
    response = make_response(jsonify({
        'received': {
            'auth_header': auth_header,
            'cookies': cookies,
            'headers': dict(request.headers)
        },
        'test_token': test_token
    }))
    
    # Set test cookie
    response.set_cookie(
        'debug_token',
        test_token,
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
        secure=False,
        samesite='Lax',
        path='/'
    )
    
    return response

@app.route('/debug/set_token/<token>', methods=['GET'])
def set_token(token):
    """Set a specific token in a cookie for testing."""
    response = make_response(jsonify({
        'message': f'Set token cookie with value: {token}'
    }))
    
    response.set_cookie(
        'access_token',
        token,
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
        secure=False,
        samesite='Lax',
        path='/'
    )
    
    return response

if __name__ == '__main__':
    # Run on port 5006 to match the main application
    app.run(host='0.0.0.0', port=5007, debug=True) 