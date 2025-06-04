#!/usr/bin/env python3
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True)

# In-memory storage for moving parameters
MOCK_MOVING_PARAMETERS = {
    "base_rate_per_mile": 1.5,
    "move_size_rates": {
        "studio": 199,
        "1bed": 299, 
        "2bed": 399,
        "3bed": 499,
        "4bed": 599,
        "5+bed": 699
    },
    "additional_service_costs": {
        "packing": 150,
        "unpacking": 150,
        "furniture_assembly": 100,
        "furniture_disassembly": 100,
        "appliance_connection": 75,
        "appliance_disconnection": 75,
        "piano_moving": 250,
        "specialty_items": 200,
        "storage": 150,
        "cleaning": 200
    },
    "rate_adjustments": {
        "peak_season": 1.2,
        "weekend": 1.1,
        "rush_booking": 1.15,
        "distance_threshold": 50,
        "long_distance_rate": 0.9,
        "senior_discount": 0.9,
        "military_discount": 0.9,
        "repeat_customer_discount": 0.95
    },
    "email_config": {}
}

# In-memory company parameters store
COMPANY_PARAMETERS = {}

@app.route('/api/companies/<int:company_id>/moving-parameters', methods=['GET'])
def get_moving_parameters(company_id):
    """Get moving parameters for a company using in-memory storage"""
    # Return parameters from memory if they exist, otherwise return default
    return jsonify({
        "status": "success",
        "message": "Moving parameters retrieved successfully (in-memory)",
        "parameters": COMPANY_PARAMETERS.get(company_id, MOCK_MOVING_PARAMETERS)
    })

@app.route('/api/companies/<int:company_id>/moving-parameters', methods=['PUT'])
def update_moving_parameters(company_id):
    """Update moving parameters for a company using in-memory storage"""
    data = request.json
    
    # Store parameters in memory
    COMPANY_PARAMETERS[company_id] = data
    
    return jsonify({
        "status": "success",
        "message": "Moving parameters updated successfully (in-memory)",
        "parameters": data
    })

@app.route('/api/companies/save-moving-parameters', methods=['PUT'])
def save_moving_parameters():
    """Save moving parameters for a company using in-memory storage"""
    data = request.json
    company_id = data.get('company_id', 0)
    parameters = data.get('parameters', {})
    
    # Store parameters in memory
    COMPANY_PARAMETERS[company_id] = parameters
    
    return jsonify({
        "status": "success",
        "message": "Moving parameters saved successfully (in-memory)",
        "parameters": parameters
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "success",
        "message": "Moving parameters service is running"
    })

# Error handling for 404 routes
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "message": "Route not found",
        "error": str(error)
    }), 404

if __name__ == "__main__":
    # For local testing only - in production use gunicorn
    app.run(debug=True, host="0.0.0.0", port=5005)