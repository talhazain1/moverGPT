# Chatbot Platform - Moving Estimate Functionality

## Overview
This document provides instructions for testing and troubleshooting the moving estimate functionality of the chatbot platform.

## Testing the Moving Estimate Feature

### Using the Test Script
1. Make sure the server is running
2. Run the test script:
```
python test_moving_estimate.py
```

### Manual Testing
1. Send a POST request to `/api/chatbot/inference` with the following payload:
```json
{
  "company_id": 23,
  "query": "I want to move from New York to Boston, a 2 bedroom apartment on 1st september 2025",
  "session_id": "<your_session_id>"
}
```

## Troubleshooting

### Common Issues

#### 1. Missing Cost Estimate in Response
If you're getting a response without a cost estimate, check the following:

- Ensure the company has MovingParameters set up in the database
- Check that the MovingParameters include rates for the specified move size
- Verify that the distance calculation is working properly

#### 2. Debugging Steps
1. Add debug logging to the `_calculate_and_return_estimate` method in `moving_chat_handler.py`
2. Check if the correct move size is being identified
3. Verify that distance calculation is returning valid results
4. Ensure the cost calculation logic is working correctly

#### 3. Testing with Fixed Parameters
You can modify `test_moving_estimate.py` to use specific parameters for testing:
```python
query = "I want to move from New York to Boston, a 2 bedroom apartment on 1st september 2025"
```

## Fixing MovingParameters

If the company doesn't have proper MovingParameters, you can add them manually:

```python
from companies.models import MovingParameters
from core.database import db

# Create parameters for company_id 23
params = MovingParameters(
    company_id=23,
    move_size_rates={
        "studio": 500,
        "1-bedroom": 700,
        "2-bedroom": 900,
        "3-bedroom": 1200,
        "4-bedroom": 1500
    },
    base_rate_per_mile=2.5,
    additional_service_costs={
        "packing": {
            "studio": 200,
            "1-bedroom": 300,
            "2-bedroom": 400,
            "3-bedroom": 500,
            "4-bedroom": 600
        },
        "storage": {
            "studio": 100,
            "1-bedroom": 150,
            "2-bedroom": 200,
            "3-bedroom": 250,
            "4-bedroom": 300
        }
    },
    rate_adjustments={
        "rural_location_rate": 0.1,
        "seasonality_rate": 0.15,
        "max_cost_multiplier": 1.2
    }
)

db.session.add(params)
db.session.commit()
``` 