# Changes to Fix Moving Estimate Functionality

## Issues Fixed

1. **Origin/Destination Extraction**: Fixed the extraction of origin and destination locations from user messages.
   - Added better regex patterns to correctly identify origin and destination
   - Enhanced the OpenAI prompt to be more specific about distinguishing origin and destination
   - Added a fallback extraction function for when the OpenAI API is not available

2. **Move Size Recognition**: Improved the normalization of move size formats.
   - Added support for various formats like "2 bedroom", "2-bedroom", "2 br", "2br", etc.
   - Added support for text-based numbers like "two bedroom"

3. **Distance Calculation**: Enhanced the distance calculation for common city pairs.
   - Added a database of known distances between major US cities
   - Improved the fallback estimation for when the Google Maps API is not available

4. **Error Handling**: Added better error handling for missing API keys and other issues.
   - Added specific error messages for missing OpenAI API key
   - Created fallback functionality for when APIs are not available

## Files Changed

1. `/src/utils/openai_utils.py`:
   - Enhanced `extract_moving_information` function
   - Added `_extract_moving_info_fallback` function for regex-based extraction

2. `/src/utils/google_maps_utils.py`:
   - Improved `_estimate_distance` function with known city pairs

3. `/src/chatbot/moving_chat_handler.py`:
   - Enhanced move size normalization
   - Added better error handling for missing API keys

4. `/src/chatbot/model_inference.py`:
   - Added specific error handling for moving-related queries

## Testing Tools Created

1. `setup_moving_params.py`: Script to set up MovingParameters for a company
2. `debug_moving_estimate.py`: Script to debug the moving estimate functionality
3. `test_standalone.py`: Standalone test script for the moving estimate functionality
4. `mock_db.py`: Mock database module for testing

## How to Test

1. Set up MovingParameters for your company:
   ```
   python setup_moving_params.py [company_id]
   ```

2. Test the moving estimate functionality:
   ```
   python test_standalone.py
   ```

3. Debug issues with the moving estimate:
   ```
   python debug_moving_estimate.py [company_id] [query]
   ```

## Common Issues

1. **Missing MovingParameters**: Make sure your company has MovingParameters set up in the database.
2. **Invalid Move Size**: Ensure the move size format is recognized and exists in the MovingParameters.
3. **API Keys**: Set the OPENAI_API_KEY environment variable for best results.

## Next Steps

1. Monitor the moving estimate functionality in production
2. Collect feedback from users to further improve the extraction accuracy
3. Add more known city pairs to the distance calculation database 