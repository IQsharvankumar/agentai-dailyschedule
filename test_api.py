
import requests
import json

# Test the API endpoints
def test_api():
    base_url = "http://0.0.0.0:5000"
    
    print("Testing Schedule Optimization API")
    print("=" * 50)
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return
    
    # Get sample request
    try:
        response = requests.get(f"{base_url}/planmydaynurse/sample-request")
        sample_data = response.json()
        print("\nSample request retrieved successfully")
    except Exception as e:
        print(f"Failed to get sample request: {e}")
        return
    
    # Test optimization endpoint
    try:
        response = requests.post(
            f"{base_url}/planmydaynurse/optimize",
            json=sample_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nOptimization successful!")
            print(f"Nurse ID: {result['nurseId']}")
            print(f"Schedule Date: {result['scheduleDate']}")
            print(f"Optimization Score: {result['optimizationScore']}")
            print(f"Total Scheduled Items: {len(result['optimizedSchedule'])}")
            print(f"Unachievable Items: {len(result['unachievableItems'])}")
            
            print("\nScheduled Activities:")
            for item in result['optimizedSchedule']:
                print(f"  {item['slotStartTime']} - {item['slotEndTime']}: {item['title']} ({item['activityType']})")
                
            if result['warnings']:
                print("\nWarnings:")
                for warning in result['warnings']:
                    print(f"  - {warning}")
        else:
            print(f"Optimization failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"API test failed: {e}")

if __name__ == "__main__":
    test_api()
