import requests
import json
from collections import Counter

# --- Configuration ---
BASE_URL = "http://127.0.0.1:8000/api/v1/budget-planner"
# Replace with a valid reference_id that has a budget plan
REFERENCE_ID = "Test-8" # Example from your database output
# Replace with a valid category_name that has multiple vendors in your location
CATEGORY_NAME = "mehendi" # Or 'photographers', 'catering', etc.
# The number of items per page you're testing (should match your API's default or chosen limit)
PAGE_LIMIT = 10 
# Replace with a valid JWT token obtained from your /login endpoint
# This token will expire, so regenerate it if you run this script much later
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxNzQ4ODYxMzMwfQ.17_WLSoNjFKbefz78u7NX-voWAKrDVN5nEzAKtzLKTM" 

# --- Verification Logic ---

def verify_vendor_pagination(ref_id: str, category: str, limit: int, token: str):
    print(f"--- Verifying Pagination for Category: '{category}' (Plan: '{ref_id}') ---")
    print(f"Page Limit: {limit} vendors per page\n")

    all_fetched_vendor_ids = []
    current_page = 1
    total_pages = 1 # Initialize to at least 1 to enter the loop

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        while current_page <= total_pages:
            url = f"{BASE_URL}/{ref_id}/category/{category}/explore-vendors?page={current_page}&limit={limit}"
            print(f"Fetching: {url}")

            response = requests.get(url, headers=headers)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

            data = response.json()

            # Update total_pages from the first response, or if it changed for some reason
            if current_page == 1:
                total_pages = data.get('total_pages', 1)
                total_vendors_count = data.get('total_vendors', 0)
                print(f"Total Vendors Found: {total_vendors_count}")
                print(f"Calculated Total Pages: {total_pages}\n")
                if total_vendors_count == 0:
                    print("No vendors found for this category and location. Cannot perform pagination test.")
                    return

            vendors_on_page = data.get('vendors', [])
            
            if not vendors_on_page and current_page <= total_pages:
                print(f"WARNING: Page {current_page} returned no vendors, but total_pages suggests there should be more. This might indicate an issue with data consistency or pagination logic.")
                # Break to prevent infinite loop if total_pages is wrong or no more items
                break

            current_page_ids = [vendor['vendor_id'] for vendor in vendors_on_page]
            all_fetched_vendor_ids.extend(current_page_ids)

            print(f"  - Page {current_page} fetched {len(current_page_ids)} vendors.")
            
            # Check for duplicates within the current page (shouldn't happen with our sorting)
            if len(current_page_ids) != len(set(current_page_ids)):
                print(f"  !!! CRITICAL ERROR: Duplicates found WITHIN page {current_page} !!!")
                page_id_counts = Counter(current_page_ids)
                page_duplicates = [id for id, count in page_id_counts.items() if count > 1]
                print(f"  Repeated IDs on this page: {page_duplicates}")
                return # Stop test if internal page duplicates are found

            current_page += 1

        print("\n--- Final Verification ---")
        unique_ids_set = set(all_fetched_vendor_ids)

        if len(all_fetched_vendor_ids) == len(unique_ids_set):
            print(f"\n✅ SUCCESS: All {len(all_fetched_vendor_ids)} vendor IDs across all {total_pages} pages are unique. No repetitions found.")
        else:
            print(f"\n❌ FAILURE: Duplicates found across pages!")
            print(f"Total IDs collected: {len(all_fetched_vendor_ids)}")
            print(f"Unique IDs collected: {len(unique_ids_set)}")
            
            id_counts = Counter(all_fetched_vendor_ids)
            duplicates_across_pages = [id for id, count in id_counts.items() if count > 1]
            print(f"Repeated IDs across pages: {duplicates_across_pages}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR: API request failed: {e}")
        if e.response:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
    except json.JSONDecodeError:
        print(f"\n❌ ERROR: Failed to decode JSON response. Raw response: {response.text}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    verify_vendor_pagination(REFERENCE_ID, CATEGORY_NAME, PAGE_LIMIT, JWT_TOKEN)