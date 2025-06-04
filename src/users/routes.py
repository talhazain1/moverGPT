@users_bp.route('/refresh_token', methods=['POST'])
def refresh_token():
    """Refresh the user's access token if they are authenticated."""
    try:
        # Check if the user is logged in via Flask-Login
        try:
            from flask_login import current_user
            if current_user.is_authenticated:
                user = User.query.get(current_user.id)
                if user:
                    # Generate a new JWT token
                    from core.utils import generate_jwt
                    token = generate_jwt({"user_id": user.id, "company_id": user.company_id})
                    
                    # Create response with token
                    response = jsonify({
                        "success": True,
                        "message": "Token refreshed successfully",
                        "token": token,
                        "user": {
                            "id": user.id,
                            "user_name": user.user_name,
                            "user_email": user.user_email,
                            "company_id": user.company_id
                        }
                    })
                    
                    # Set token cookie
                    response.set_cookie(
                        "access_token",
                        token,
                        max_age=30 * 24 * 60 * 60,  # 30 days
                        httponly=True,
                        secure=False,  # Set to True in production with HTTPS
                        samesite="Lax",
                        path="/"
                    )
                    
                    return response
        except Exception as e:
            print(f"Error checking current_user: {e}")
        
        # If Flask-Login didn't work, try getting from JWT token
        # Get token from Authorization header or cookies
        token = None
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.cookies.get("access_token")
        
        if not token:
            return jsonify({"error": "No token found"}), 401
        
        # Verify token
        from core.utils import verify_jwt
        payload = verify_jwt(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        # Get user from token
        user = User.query.get(payload.get("user_id"))
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Generate a new JWT token
        from core.utils import generate_jwt
        new_token = generate_jwt({"user_id": user.id, "company_id": user.company_id})
        
        # Create response with token
        response = jsonify({
            "success": True,
            "message": "Token refreshed successfully",
            "token": new_token,
            "user": {
                "id": user.id,
                "user_name": user.user_name,
                "user_email": user.user_email,
                "company_id": user.company_id
            }
        })
        
        # Set token cookie
        response.set_cookie(
            "access_token",
            new_token,
            max_age=30 * 24 * 60 * 60,  # 30 days
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="Lax",
            path="/"
        )
        
        return response
    except Exception as e:
        print(f"Error refreshing token: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error refreshing token: {str(e)}"}), 500 