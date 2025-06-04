#!/usr/bin/env python3
import requests
import json

def main():
    """Initialize moving parameters for company 7"""
    print("🔧 Initializing moving parameters for company 7...")
    
    # Moving parameters for company 7
    params = {
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
    
    # First try using the save endpoint
    try:
        save_data = {
            "company_id": 7,
            "parameters": params
        }
        
        save_response = requests.put(
            "http://localhost:5005/api/companies/save-moving-parameters",
            json=save_data,
            timeout=5
        )
        
        print(f"Save response: {save_response.status_code}")
        if save_response.status_code == 200:
            print("✅ Successfully saved parameters using save endpoint")
            print(f"Response: {save_response.json()}")
            return
        
    except Exception as e:
        print(f"❌ Error using save endpoint: {str(e)}")
    
    # If save fails, try the update endpoint
    try:
        update_response = requests.put(
            "http://localhost:5005/api/companies/7/moving-parameters",
            json=params,
            timeout=5
        )
        
        print(f"Update response: {update_response.status_code}")
        if update_response.status_code == 200:
            print("✅ Successfully updated parameters using update endpoint")
            print(f"Response: {update_response.json()}")
            return
        
    except Exception as e:
        print(f"❌ Error using update endpoint: {str(e)}")
    
    print("❌ Failed to initialize parameters")

if __name__ == "__main__":
    main() 