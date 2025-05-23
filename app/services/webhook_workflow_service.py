# weddingverse_api/app/services/webhook_workflow_service.py
import asyncio
import uuid
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import re # Import re for parsing time strings

import httpx # For asynchronous HTTP requests
import gspread # For Google Sheets API
from google.oauth2.service_account import Credentials # For Google Sheets auth
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from app.models.webhook import WebhookPayload, TranscriptMessage # Import TranscriptMessage
from app.utils.logger import logger
from app.config import settings # Import settings
from app.services.mongo_service import db # Import MongoDB client

# --- Initialize external clients (singleton pattern) ---

_httpx_client: httpx.AsyncClient = None

async def get_httpx_client() -> httpx.AsyncClient:
    """Returns a singleton httpx.AsyncClient instance."""
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(timeout=30.0)
        logger.info("[HTTPX Client] New httpx.AsyncClient initialized.")
    return _httpx_client

_gspread_client = None

def get_gspread_client():
    """Returns a singleton gspread client instance."""
    global _gspread_client
    if _gspread_client is None:
        try:
            # Check if required config is present, but allow partial if not for commented-out services
            if not settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_KEYFILE_PATH or not settings.GOOGLE_SHEET_ID:
                logger.warning("Google Sheets credentials or sheet ID missing. Google Sheets functionality will be skipped.")
                # This doesn't raise an error, allowing the app to start even if GSheets config is incomplete.
                # The real_google_sheets_append function will handle the error if it's called.
                return None
            
            creds = Credentials.from_service_account_file(
                settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_KEYFILE_PATH,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            _gspread_client = gspread.authorize(creds)
            logger.info("[Google Sheets Client] gspread client authorized successfully.")
        except Exception as e:
            logger.error(f"[Google Sheets Client] Failed to authorize gspread client: {e}", exc_info=True)
            # Re-raise to halt startup only if client cannot be initialized AND it's critical
            # For optional services, a warning is enough, and the function will return None or raise in its own context
            return None # Return None or raise, depending on how critical GSheets is for startup
    return _gspread_client

# --- Real API Call Implementations ---

# This function is commented out as per requirement 4
async def real_google_sheets_append(data: dict):
    """Appends data to a Google Sheet using gspread."""
    logger.info(f"[Google Sheets] Attempting to append data for call_id: {data.get('call_id')}")
    gc = get_gspread_client()
    if not gc: # Check if client was successfully initialized
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Google Sheets client not initialized.")
    try:
        # gspread is synchronous, so run it in a separate thread to not block the event loop
        def _append_sync():
            spreadsheet = gc.open_by_id(settings.GOOGLE_SHEET_ID)
            worksheet = spreadsheet.worksheet("Sheet1") # Assuming "Sheet1" or specify dynamically
            # Map your extracted fields to Google Sheet columns
            # Adjust this list to match the order of columns in your Google Sheet
            row_data = [
                data.get('call_id', ''),
                data.get('timestamp', ''),
                data.get('vendorName', ''),
                data.get('customerName', ''),
                data.get('phoneNumber', ''),
                data.get('vendorEmail', ''),
                data.get('vendorAadhaarNumber', ''),
                data.get('vendorPANNumber', ''),
                data.get('referenceID', ''),
                data.get('category', ''),
                data.get('CustomerAddress', ''),
                data.get('call_duration_seconds', ''),
                data.get('date', ''),
                data.get('call_start_time', ''),
                data.get('call_end_time', ''),
                json.dumps(data.get('full_transcript', {})) # Store full transcript as JSON string
            ]
            worksheet.append_row(row_data)
            return {"status": "success", "message": "Data appended to Google Sheet."}

        result = await asyncio.to_thread(_append_sync)
        logger.info(f"[Google Sheets] {result['message']}")
        return result
    except Exception as e:
        logger.error(f"[Google Sheets] Error appending data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google Sheets API error: {e}"
        )

async def real_whatsapp_send_message(to_number: str, message_body: str):
    """Sends a message via WhatsApp Business Cloud using httpx."""
    logger.info(f"[WhatsApp Business Cloud] Attempting to send message to {to_number}: '{message_body[:50]}...'")
    client = await get_httpx_client()
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_body}
    }
    try:
        response = await client.post(settings.WHATSAPP_BUSINESS_API_URL, json=payload, headers=headers)
        response.raise_for_status() # Raises an HTTPStatusError for 4xx/5xx responses
        whatsapp_response_data = response.json()
        logger.info(f"[WhatsApp Business Cloud] Message sent successfully. WhatsApp message ID: {whatsapp_response_data.get('messages', [{}])[0].get('id')}")
        return {"status": "success", "response": whatsapp_response_data}
    except httpx.HTTPStatusError as e:
        logger.error(f"[WhatsApp Business Cloud] HTTP error sending message: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"WhatsApp API HTTP error: {e.response.status_code} - {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"[WhatsApp Business Cloud] Network error sending message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"WhatsApp API network error: {e}"
        )
    except Exception as e:
        logger.error(f"[WhatsApp Business Cloud] Unexpected error sending message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"WhatsApp API error: {e}"
        )

async def real_salesforce_auth_token():
    """Gets an authentication token from Salesforce using Username-Password flow with httpx."""
    logger.info("[Salesforce Auth] Attempting to get auth token from Salesforce...")
    client = await get_httpx_client()
    # Check for required Salesforce auth config
    if not all([settings.SALESFORCE_USERNAME, settings.SALESFORCE_PASSWORD, settings.SALESFORCE_CLIENT_ID, settings.SALESFORCE_CLIENT_SECRET, settings.SALESFORCE_AUTH_URL]):
        raise ValueError("Missing one or more Salesforce authentication environment variables (USERNAME, PASSWORD, CLIENT_ID, CLIENT_SECRET, AUTH_URL).")

    password_with_token = f"{settings.SALESFORCE_PASSWORD}{settings.SALESFORCE_SECURITY_TOKEN}" if settings.SALESFORCE_SECURITY_TOKEN else settings.SALESFORCE_PASSWORD
    
    data = {
        "grant_type": "password",
        "client_id": settings.SALESFORCE_CLIENT_ID,
        "client_secret": settings.SALESFORCE_CLIENT_SECRET,
        "username": settings.SALESFORCE_USERNAME,
        "password": password_with_token
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = await client.post(settings.SALESFORCE_AUTH_URL, data=data, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        if "access_token" not in token_data:
            raise ValueError("Salesforce auth response missing access_token.")
        logger.info("[Salesforce Auth] Token received successfully.")
        return token_data
    except httpx.HTTPStatusError as e:
        logger.error(f"[Salesforce Auth] HTTP error getting token: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Salesforce Auth HTTP error: {e.response.status_code} - {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"[Salesforce Auth] Network error getting token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Salesforce Auth network error: {e}"
        )
    except Exception as e:
        logger.error(f"[Salesforce Auth] Unexpected error getting token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Salesforce Auth error: {e}"
        )

async def real_salesforce_post_vendor_onboarding_data(auth_token: str, vendor_details: dict, full_transcript: List[TranscriptMessage]):
    """Posts vendor onboarding data to Salesforce."""
    logger.info(f"[Salesforce POST] Posting vendor onboarding data for {vendor_details.get('vendorName')} (Call ID: {vendor_details.get('call_id')})...")
    client = await get_httpx_client()
    
    # Define your Salesforce Custom Object API Name for Vendor Onboarding
    salesforce_object_type = "Vendor_Onboarding__c" # <--- IMPORTANT: Configure this in Salesforce!
    salesforce_post_url = f"{settings.SALESFORCE_API_BASE_URL}{salesforce_object_type}/"

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    # Map extracted data to Salesforce custom fields.
    payload = {
        "Call_ID__c": vendor_details.get('call_id'),
        "Vendor_Name__c": vendor_details.get('vendorName'),
        "Customer_Name__c": vendor_details.get('customerName'), # Name of the person from the vendor
        "Phone_Number__c": vendor_details.get('phoneNumber'),
        "Vendor_Email__c": vendor_details.get('vendorEmail'),
        "Vendor_Aadhaar_Number__c": vendor_details.get('vendorAadhaarNumber'),
        "Vendor_PAN_Number__c": vendor_details.get('vendorPANNumber'),
        "Reference_ID__c": vendor_details.get('referenceID'),
        "Category__c": vendor_details.get('category'),
        "Customer_Address__c": vendor_details.get('CustomerAddress'),
        "Call_Duration_Seconds__c": vendor_details.get('call_duration_seconds'),
        "Call_Date__c": vendor_details.get('date'),
        "Call_Start_Time__c": vendor_details.get('call_starting_time'),
        "Call_End_Time__c": vendor_details.get('call_ending_time'),
        "Full_Transcript__c": json.dumps([msg.model_dump() for msg in full_transcript]) # Store full transcript as JSON string
    }
    
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        response = await client.post(salesforce_post_url, json=payload, headers=headers)
        response.raise_for_status()
        salesforce_response_data = response.json()
        logger.info(f"[Salesforce POST] Vendor onboarding data posted successfully. Record ID: {salesforce_response_data.get('id')}")
        return {"status": "success", "response": salesforce_response_data}
    except httpx.HTTPStatusError as e:
        logger.error(f"[Salesforce POST] HTTP error posting data: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Salesforce API HTTP error: {e.response.status_code} - {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"[Salesforce POST] Network error posting data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Salesforce API network error: {e}"
        )
    except Exception as e:
        logger.error(f"[Salesforce POST] Unexpected error posting data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Salesforce API error: {e}"
        )

async def real_mongo_insert_vendor_onboarding(data: dict):
    """Inserts vendor onboarding data into MongoDB."""
    logger.info(f"[MongoDB] Inserting vendor onboarding data for call_id: {data.get('call_id')}")
    try:
        result = db[settings.VENDOR_ONBOARDING_COLLECTION].insert_one(data)
        logger.info(f"[MongoDB] Vendor onboarding data inserted successfully. Doc ID: {result.inserted_id}")
        return {"status": "success", "message": "Data inserted into MongoDB.", "inserted_id": str(result.inserted_id)}
    except Exception as e:
        logger.error(f"[MongoDB] Error inserting vendor onboarding data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MongoDB insert error: {e}"
        )

# --- Data Extraction Logic ---

def _parse_time_string_to_seconds(time_str: str) -> float:
    """Parses a time string like '3.500s' into seconds (float)."""
    match = re.match(r"(\d+\.?\d*)s", time_str)
    if match:
        return float(match.group(1))
    logger.warning(f"Could not parse time string: {time_str}")
    return 0.0

def _calculate_call_duration(transcript: List[TranscriptMessage]) -> Optional[float]:
    """
    Calculates the total duration of the call from the transcript's timespans.
    Returns duration in seconds.
    """
    if not transcript:
        return None

    first_start_time = None
    last_end_time = None

    # Sort transcript by message index to ensure correct order, though usually it's ordered
    sorted_transcript = sorted(transcript, key=lambda msg: msg.callStageMessageIndex)

    for message in sorted_transcript:
        if message.timespan:
            start_s = _parse_time_string_to_seconds(message.timespan.start)
            end_s = _parse_time_string_to_seconds(message.timespan.end)

            if first_start_time is None or start_s < first_start_time:
                first_start_time = start_s
            
            if last_end_time is None or end_s > last_end_time:
                last_end_time = end_s
    
    if first_start_time is not None and last_end_time is not None:
        return last_end_time - first_start_time
    
    logger.warning("Could not determine call duration from transcript timespans.")
    return None

def _extract_vendor_details_from_transcript(transcript: List[TranscriptMessage]) -> Optional[Dict[str, Any]]:
    """
    Parses the transcript messages to find and extract vendor details from
    the 'storevendordetails' tool call.
    """
    for message in transcript:
        if message.role == "MESSAGE_ROLE_TOOL_CALL" and message.toolName == "storevendordetails":
            try:
                if message.text:
                    details = json.loads(message.text)
                    logger.info(f"[Extraction] Successfully extracted vendor details from tool call: {details.keys()}")
                    return details
                else:
                    logger.warning("[Extraction] Tool call 'storevendordetails' found but text field is empty or None.")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"[Extraction] Failed to decode JSON from tool call text for 'storevendordetails': {e}", exc_info=True)
                return None
            except Exception as e:
                logger.error(f"[Extraction] Unexpected error during tool call text parsing for 'storevendordetails': {e}", exc_info=True)
                return None
    logger.warning("[Extraction] 'storevendordetails' tool call not found in transcript.")
    return None

# --- Core Workflow Blocks (Adjusted for extraction and new DB step) ---

def code_block_logic(payload: WebhookPayload):
    """
    Performs initial processing, including extracting vendor details and call duration from the transcript.
    This acts as the 'Code' block, preparing data for subsequent steps.
    """
    logger.info(f"[Code Block] Initializing processing for call_id: {payload.call_id}")
    
    # Step 1: Extract vendor details from the transcript
    extracted_vendor_details = _extract_vendor_details_from_transcript(payload.transcript)
    if not extracted_vendor_details:
        logger.error(f"[Code Block] Could not extract necessary vendor details for call_id: {payload.call_id}. Halting workflow.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required vendor onboarding details not found in transcript."
        )

    # Step 2: Calculate call duration
    call_duration = _calculate_call_duration(payload.transcript)
    if call_duration is not None:
        extracted_vendor_details['call_duration_seconds'] = call_duration
        logger.info(f"[Code Block] Call duration calculated: {call_duration:.2f} seconds.")
    else:
        logger.warning(f"[Code Block] Call duration could not be determined for call_id: {payload.call_id}.")
        extracted_vendor_details['call_duration_seconds'] = None # Explicitly set to None if not found

    # Add call_id and full transcript to the extracted details for persistence and other steps
    extracted_vendor_details['call_id'] = payload.call_id
    extracted_vendor_details['full_transcript'] = [msg.model_dump() for msg in payload.transcript]
    
    # Determine the customer's actual phone number and name for WhatsApp, preferring extracted ones
    whatsapp_customer_phone = extracted_vendor_details.get('phoneNumber')
    whatsapp_customer_name = extracted_vendor_details.get('customerName')

    # For Salesforce, the context is the extracted details
    salesforce_processing_context = extracted_vendor_details.copy()

    # Google Sheets data (currently commented out but structure is here)
    google_sheets_data = extracted_vendor_details.copy()
    
    return extracted_vendor_details, whatsapp_customer_phone, whatsapp_customer_name, salesforce_processing_context, google_sheets_data

def guardrails_block_logic(salesforce_context: dict):
    """
    Implements the 'Guardrails' block, applying business rules before Salesforce update.
    """
    logger.info(f"[Guardrails Block] Applying checks for vendor onboarding for call_id: {salesforce_context.get('call_id')}")

    # Example Guardrail 1: Ensure essential contact info is present
    if not salesforce_context.get('vendorEmail') and not salesforce_context.get('phoneNumber'):
        logger.info(f"[Guardrails Block] Essential contact info missing for {salesforce_context.get('call_id')}. Halting Salesforce path.")
        return {"can_proceed": False, "reason": "Missing vendor email and phone number."}

    # Example Guardrail 2: Basic validation of Aadhaar/PAN (simplified)
    aadhaar = str(salesforce_context.get('vendorAadhaarNumber', ''))
    if aadhaar and (len(aadhaar) != 12 or not aadhaar.isdigit()):
        logger.info(f"[Guardrails Block] Invalid Aadhaar number format for {salesforce_context.get('call_id')}. Halting Salesforce path.")
        return {"can_proceed": False, "reason": "Invalid Aadhaar number format."}
    
    logger.info(f"[Guardrails Block] All guardrail checks passed for call_id: {salesforce_context.get('call_id')}.")
    return {"can_proceed": True, "reason": "All checks passed"}

def set_transcript_summary_logic(full_transcript: List[TranscriptMessage]):
    """
    Generates a summary of the transcript. This could be used for Salesforce description.
    """
    logger.info("[Set Transcript Summary Block] Generating summary...")
    
    conversation_text = " ".join([msg.text or '' for msg in full_transcript if msg.role in ["MESSAGE_ROLE_USER", "MESSAGE_ROLE_AGENT"]])
    
    if len(conversation_text) > 200:
        summary = f"Call summary: Vendor onboarding details collected. Conversation highlights: {conversation_text[:150]}... [truncated]"
    elif len(conversation_text) > 50:
        summary = f"Call summary: Vendor onboarding initiated. Key conversation points: {conversation_text[:50]}..."
    else:
        summary = f"Call summary: {conversation_text}"
    
    return summary

# --- Workflow Orchestration Functions ---

async def _run_mongodb_insert_path(vendor_onboarding_data: dict):
    """Handles inserting data into MongoDB."""
    path_results = {"status": "started", "steps": []}
    try:
        mongo_result = await real_mongo_insert_vendor_onboarding(vendor_onboarding_data)
        path_results["steps"].append({"MongoDB Insert": mongo_result})
        path_results["status"] = "completed"
    except HTTPException as e:
        logger.error(f"❌ Error in MongoDB insert path for {vendor_onboarding_data.get('call_id')}: {e.detail}")
        path_results["status"] = "failed"
        path_results["error_detail"] = e.detail
    except Exception as e:
        logger.error(f"❌ Unexpected error in MongoDB insert path for {vendor_onboarding_data.get('call_id')}: {e}", exc_info=True)
        path_results["status"] = "failed"
        path_results["error_detail"] = str(e)
    return path_results


async def _run_whatsapp_confirmation_path(customer_phone: str, customer_name: str, call_id: str):
    """Handles sending the WhatsApp confirmation message."""
    path_results = {"status": "started", "steps": []}
    if not customer_phone:
        logger.warning(f"Skipping WhatsApp confirmation: customer phone number not provided for call_id {call_id}.")
        path_results["status"] = "skipped"
        path_results["reason"] = "Customer phone number not available."
        return path_results
    
    try:
        whatsapp_message = f"Hello {customer_name},\n Thank you for joining the WeddingVerse platform. To complete your verification, please share clear, legible images of your Aadhaar card and PAN card at your earliest convenience."
        whatsapp_result = await real_whatsapp_send_message(customer_phone, whatsapp_message)
        path_results["steps"].append({"WhatsApp Confirmation": whatsapp_result})
        path_results["status"] = "completed"
    except HTTPException as e:
        logger.error(f"❌ Error in WhatsApp confirmation path for {call_id}: {e.detail}")
        path_results["status"] = "failed"
        path_results["error_detail"] = e.detail
    except Exception as e:
        logger.error(f"❌ Unexpected error in WhatsApp confirmation path for {call_id}: {e}", exc_info=True)
        path_results["status"] = "failed"
        path_results["error_detail"] = str(e)
    return path_results


async def _run_salesforce_onboarding_path(salesforce_context: dict, full_transcript: List[TranscriptMessage]):
    """Handles the Salesforce authentication and vendor data posting path."""
    path_results = {"status": "started", "steps": []}
    
    try:
        # Step: Get Auth Token (Salesforce)
        auth_token_response = await real_salesforce_auth_token()
        salesforce_auth_token = auth_token_response.get("access_token")
        path_results["steps"].append({"Get Auth Token": {"status": "success" if salesforce_auth_token else "failed"}})

        if not salesforce_auth_token:
            raise ValueError("Salesforce authentication failed: No token received.")

        # Step: Guardrails
        guardrails_check = guardrails_block_logic(salesforce_context)
        path_results["steps"].append({"Guardrails": guardrails_check})

        if not guardrails_check["can_proceed"]:
            path_results["status"] = "skipped"
            path_results["reason"] = guardrails_check["reason"]
            return path_results

        # Step: Set Transcript Summary (manual/AI) for Salesforce description
        transcript_summary = set_transcript_summary_logic(full_transcript)
        path_results["steps"].append({"Set Transcript Summary": {"summary_length": len(transcript_summary)}})
        
        # Step: Salesforce POST (vendor onboarding data)
        salesforce_post_result = await real_salesforce_post_vendor_onboarding_data(
            auth_token=salesforce_auth_token, 
            vendor_details=salesforce_context,
            full_transcript=full_transcript
        )
        path_results["steps"].append({"Salesforce POST": salesforce_post_result})
        
        path_results["status"] = "completed"

    except HTTPException as e:
        logger.error(f"❌ Error in Salesforce path for {salesforce_context.get('call_id')}: {e.detail}")
        path_results["status"] = "failed"
        path_results["error_detail"] = e.detail
    except ValueError as e:
        logger.error(f"❌ Data/Authentication error in Salesforce path for {salesforce_context.get('call_id')}: {e}")
        path_results["status"] = "failed"
        path_results["error_detail"] = str(e)
    except Exception as e:
        logger.error(f"❌ Unexpected error in Salesforce path for {salesforce_context.get('call_id')}: {e}", exc_info=True)
        path_results["status"] = "failed"
        path_results["error_detail"] = str(e)
    return path_results


async def process_webhook_workflow(payload: WebhookPayload) -> dict:
    """
    Orchestrates the entire vendor onboarding flowchart workflow from the incoming webhook payload.
    This function coordinates the execution of parallel and sequential steps.
    """
    logger.info(f"Initiating workflow for call_id: {payload.call_id}")

    # 1. Execute 'Code' Block to extract data
    # This block also raises HTTPException if critical data is missing.
    extracted_vendor_details, whatsapp_customer_phone, whatsapp_customer_name, salesforce_context, _google_sheets_data = \
        code_block_logic(payload)

    # 2. Prepare tasks dynamically based on what you want to run
    tasks = []
    results_map = {} # To store results keyed by service name

    # Always include MongoDB insert as it's the primary persistence
    tasks.append(asyncio.create_task(_run_mongodb_insert_path(extracted_vendor_details)))
    results_map["mongodb_insert_summary"] = None # Placeholder

    # --- Conditional Inclusion of Other Services ---
    # To enable/disable a service, uncomment/comment its corresponding lines below.

    # WhatsApp Confirmation
    _ENABLE_WHATSAPP = False # Set to False to disable WhatsApp
    if _ENABLE_WHATSAPP:
        tasks.append(asyncio.create_task(_run_whatsapp_confirmation_path(
            customer_phone=whatsapp_customer_phone,
            customer_name=whatsapp_customer_name,
            call_id=payload.call_id
        )))
        results_map["whatsapp_confirmation_summary"] = None

    # Salesforce Onboarding
    _ENABLE_SALESFORCE = False # Set to False to disable Salesforce
    if _ENABLE_SALESFORCE:
        tasks.append(asyncio.create_task(_run_salesforce_onboarding_path(
            salesforce_context=salesforce_context,
            full_transcript=payload.transcript
        )))
        results_map["salesforce_onboarding_summary"] = None

    # Google Sheets (Already commented out its real implementation, keep this here for structure)
    _ENABLE_GOOGLE_SHEETS = False # Set to True if you uncomment real_google_sheets_append
    if _ENABLE_GOOGLE_SHEETS:
        tasks.append(asyncio.create_task(real_google_sheets_append(_google_sheets_data)))
        results_map["google_sheets_summary"] = None

    # Execute all prepared tasks concurrently
    if tasks:
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Populate results_map based on the order of tasks
        result_index = 0
        if "mongodb_insert_summary" in results_map:
            results_map["mongodb_insert_summary"] = all_results[result_index]
            result_index += 1
        if _ENABLE_WHATSAPP and "whatsapp_confirmation_summary" in results_map:
            results_map["whatsapp_confirmation_summary"] = all_results[result_index]
            result_index += 1
        if _ENABLE_SALESFORCE and "salesforce_onboarding_summary" in results_map:
            results_map["salesforce_onboarding_summary"] = all_results[result_index]
            result_index += 1
        if _ENABLE_GOOGLE_SHEETS and "google_sheets_summary" in results_map:
            results_map["google_sheets_summary"] = all_results[result_index]
            result_index += 1

        # Log any exceptions that occurred in parallel tasks
        for service_name, result in results_map.items():
            if isinstance(result, Exception):
                logger.error(f"Error in {service_name} for call_id {payload.call_id}: {result}", exc_info=True)
                # Optionally, you could modify the result in results_map to indicate failure more clearly
                results_map[service_name] = {"status": "failed", "error": str(result)}

    else:
        logger.warning(f"No tasks were enabled for call_id: {payload.call_id}. Returning empty results.")


    logger.info(f"✅ Workflow execution complete for Call ID: {payload.call_id}")

    return results_map

# Ensure the httpx client is closed when the application shuts down
async def shutdown_httpx_client():
    global _httpx_client
    if _httpx_client:
        await _httpx_client.aclose()
        logger.info("httpx client closed.")