# weddingverse_api/app/services/webhook_workflow_service.py
import asyncio
import uuid
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo 
import re

import httpx
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from app.models.webhook import WebhookPayload, TranscriptMessage
from app.utils.logger import logger
from app.config import settings
from app.services.mongo_service import db, metadata_db # db and metadata_db are expected to be initialized by app startup

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
            if not settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_KEYFILE_PATH or not settings.GOOGLE_SHEET_ID:
                logger.warning("Google Sheets credentials or sheet ID missing. Google Sheets functionality will be skipped.")
                return None
            
            creds = Credentials.from_service_account_file(
                settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_KEYFILE_PATH,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            _gspread_client = gspread.authorize(creds)
            logger.info("[Google Sheets Client] gspread client authorized successfully.")
        except Exception as e:
            logger.error(f"[Google Sheets Client] Failed to authorize gspread client: {e}", exc_info=True)
            return None
    return _gspread_client

# --- Real API Call Implementations ---

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
        response.raise_for_status()
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
    
    salesforce_object_type = "Vendor_Onboarding__c"
    salesforce_post_url = f"{settings.SALESFORCE_API_BASE_URL}{salesforce_object_type}/"

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    # These fields are explicitly included for Salesforce
    payload = {
        "Call_ID__c": vendor_details.get('call_id'),
        "Vendor_Name__c": vendor_details.get('vendorName'),
        "Customer_Name__c": vendor_details.get('customerName'),
        "Phone_Number__c": vendor_details.get('phoneNumber'),
        "Vendor_Email__c": vendor_details.get('vendorEmail'),
        "Vendor_Aadhaar_Number__c": vendor_details.get('vendorAadhaarNumber'),
        "Vendor_PAN_Number__c": vendor_details.get('vendorPANNumber'),
        "Reference_ID__c": vendor_details.get('referenceID'),
        "Category__c": vendor_details.get('category'),
        "Customer_Address__c": vendor_details.get('CustomerAddress'),
        "Call_Duration_Seconds__c": vendor_details.get('call_duration_seconds'),
        "Call_Date__c": vendor_details.get('date'),
        "Call_Start_Time__c": vendor_details.get('call_start_time'),
        "Call_End_Time__c": vendor_details.get('call_end_time'),
        "Client__c": vendor_details.get('client'),
        "Full_Transcript__c": json.dumps([msg.model_dump() for msg in full_transcript])
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
    # Defensive check for db client
    if db is None:
        logger.critical("[MongoDB] 'db' client is None. MongoDB connection likely failed or not initialized during startup.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MongoDB client for vendor onboarding is not initialized. Please check server logs for MongoDB connection errors."
        )
    logger.info(f"[MongoDB] Inserting vendor onboarding data into '{settings.VENDOR_ONBOARDING_COLLECTION}' for call_id: {data.get('call_id')}")
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

async def real_mongo_insert_weddingverse_metadata(data: dict):
    """Inserts general call metadata into MongoDB."""
    # Defensive check for metadata_db client
    if metadata_db is None:
        logger.critical("[MongoDB] 'metadata_db' client is None. MongoDB connection likely failed or not initialized during startup.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MongoDB client for WeddingVerse metadata is not initialized. Please check server logs for MongoDB connection errors."
        )
    logger.info(f"[MongoDB] Inserting WeddingVerse metadata into '{settings.WEDDINGVERSE_METADATA_COLLECTION}' for call_id: {data.get('call_id')}")
    try:
        result = metadata_db[settings.WEDDINGVERSE_METADATA_COLLECTION].insert_one(data)
        logger.info(f"[MongoDB] WeddingVerse metadata inserted successfully. Doc ID: {result.inserted_id}")
        return {"status": "success", "message": "Metadata inserted into MongoDB.", "inserted_id": str(result.inserted_id)}
    except Exception as e:
        logger.error(f"[MongoDB] Error inserting WeddingVerse metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MongoDB metadata insert error: {e}"
        )

# --- Ultravox API Call Function ---
async def _get_call_details_from_ultravox(call_id: str) -> Dict[str, Any]:
    """
    Fetches call details from the Ultravox API.
    """
    logger.info(f"[Ultravox API] Fetching call details for call_id: {call_id}")
    client = await get_httpx_client()
    url = f"{settings.ULTRAVOX_BASE_URL}/calls/{call_id}"
    logger.info(url)
    headers = {
        "X-API-Key": settings.ULTRAVOX_API_KEY,
        "Accept": "application/json"
    }

    try:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        call_details = response.json()
        logger.info(f"[Ultravox API] Successfully fetched call details for {call_id}.")
        return call_details
    except httpx.HTTPStatusError as e:
        logger.error(f"[Ultravox API] HTTP error fetching call details for {call_id}: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ultravox API HTTP error: {e.response.status_code} - {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"[Ultravox API] Network error fetching call details for {call_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Ultravox API network error: {e}"
        )
    except Exception as e:
        logger.error(f"[Ultravox API] Unexpected error fetching call details for {call_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ultravox API error: {e}"
        )

# --- Data Extraction Logic ---

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

# --- Core Workflow Blocks (Modified) ---

async def code_block_logic(payload: WebhookPayload):
    """
    Performs initial processing, including extracting vendor details, fetching
    call metadata (duration, date, times) from the Ultravox API, and extracting
    the 'client' field from the webhook payload.
    This acts as the 'Code' block, preparing data for subsequent steps.
    """
    logger.info(f"[Code Block] Initializing processing for call_id: {payload.call_id}")
    
    # Step 1: Extract vendor details from the 'storevendordetails' tool call
    extracted_vendor_details = _extract_vendor_details_from_transcript(payload.transcript)
    if not extracted_vendor_details:
        logger.error(f"[Code Block] Could not extract necessary vendor details for call_id: {payload.call_id}. Halting workflow.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required vendor onboarding details not found in transcript."
        )

    # Step 2: Fetch call details from Ultravox API
    ultravox_call_details = await _get_call_details_from_ultravox(payload.call_id)

    # Step 3: Extract and calculate date, start time, end time, and duration from Ultravox response
    call_created_str = ultravox_call_details.get('created')
    call_ended_str = ultravox_call_details.get('ended')

    call_date = None
    call_start_time = None
    call_end_time = None
    call_duration_seconds = None

    if call_created_str and call_ended_str:
        try:
            created_dt = datetime.fromisoformat(call_created_str.replace('Z', '+00:00'))
            ended_dt = datetime.fromisoformat(call_ended_str.replace('Z', '+00:00'))

            call_date = created_dt.strftime("%Y-%m-%d")
            call_start_time = created_dt.strftime("%H:%M:%S")
            call_end_time = ended_dt.strftime("%H:%M:%S")
            call_duration_seconds = (ended_dt - created_dt).total_seconds()

            logger.info(f"[Code Block] Call metadata from Ultravox: Date={call_date}, Start={call_start_time}, End={call_end_time}, Duration={call_duration_seconds:.2f}s")

        except ValueError as e:
            logger.error(f"[Code Block] Error parsing Ultravox timestamps for call_id {payload.call_id}: {e}", exc_info=True)
    else:
        logger.warning(f"[Code Block] 'created' or 'ended' timestamps missing from Ultravox response for call_id: {payload.call_id}.")

    # Prepare data for WeddingVerse_metadata collection (includes all call-related metadata)
    weddingverse_metadata = {
        "call_id": payload.call_id,
        "date": call_date,
        "call_start_time": call_start_time,
        "call_end_time": call_end_time,
        "call_duration_seconds": call_duration_seconds,
        "client": payload.client,
        "full_transcript": [msg.model_dump() for msg in payload.transcript],
        "referenceID": extracted_vendor_details.get('referenceID') # Added referenceID for metadata check
    }

    # Prepare data for Vendor_Onboarding collection (filtered as per request)
    # Start with extracted_vendor_details, then add only 'date' from call metadata
    vendor_onboarding_data_for_mongo = {
        k: v for k, v in extracted_vendor_details.items()
        if k not in [
            'call_start_time', 'call_end_time', 'call_duration_seconds',
            'full_transcript', 'client', 'date' # 'date' is now explicitly excluded from vendor data
        ]
    }
    # vendor_onboarding_data_for_mongo['call_id'] = payload.call_id # Ensure call_id is always present
    # Removed: vendor_onboarding_data_for_mongo['date'] = call_date # This line is removed as per request

    # Add IST timestamp for vendor onboarding data
    ist_timezone = ZoneInfo("Asia/Kolkata")
    current_time_ist = datetime.now(ist_timezone)
    vendor_onboarding_data_for_mongo['Timestamp'] = current_time_ist.isoformat()


    # Prepare data for Salesforce (includes all extracted vendor details and call metadata)
    salesforce_processing_context = extracted_vendor_details.copy()
    # Ensure Salesforce context also has the call metadata fields
    salesforce_processing_context['date'] = call_date
    salesforce_processing_context['call_start_time'] = call_start_time
    salesforce_processing_context['call_end_time'] = call_end_time
    salesforce_processing_context['call_duration_seconds'] = call_duration_seconds
    salesforce_processing_context['client'] = payload.client
    salesforce_processing_context['full_transcript'] = [msg.model_dump() for msg in payload.transcript] # Ensure full transcript is passed for SF

    # Determine WhatsApp contact info
    whatsapp_customer_phone = extracted_vendor_details.get('phoneNumber')
    whatsapp_customer_name = extracted_vendor_details.get('customerName')

    # Google Sheets data (currently commented out but structure is here)
    google_sheets_data = extracted_vendor_details.copy() # This will contain all fields for now

    return vendor_onboarding_data_for_mongo, whatsapp_customer_phone, whatsapp_customer_name, salesforce_processing_context, google_sheets_data, weddingverse_metadata

def guardrails_block_logic(salesforce_context: dict):
    """
    Implements the 'Guardrails' block, applying business rules before Salesforce update.
    """
    logger.info(f"[Guardrails Block] Applying checks for vendor onboarding for call_id: {salesforce_context.get('call_id')}")

    if not salesforce_context.get('vendorEmail') and not salesforce_context.get('phoneNumber'):
        logger.info(f"[Guardrails Block] Essential contact info missing for {salesforce_context.get('call_id')}. Halting Salesforce path.")
        return {"can_proceed": False, "reason": "Missing vendor email and phone number."}

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
    """Handles inserting data into MongoDB (Vendor_Onboarding collection)."""
    path_results = {"status": "started", "steps": []}
    try:
        mongo_result = await real_mongo_insert_vendor_onboarding(vendor_onboarding_data)
        path_results["steps"].append({"MongoDB Vendor Onboarding Insert": mongo_result})
        path_results["status"] = "completed"
    except HTTPException as e:
        logger.error(f"❌ Error in MongoDB Vendor Onboarding insert path for {vendor_onboarding_data.get('call_id')}: {e.detail}")
        path_results["status"] = "failed"
        path_results["error_detail"] = e.detail
    except Exception as e:
        logger.error(f"❌ Unexpected error in MongoDB Vendor Onboarding insert path for {vendor_onboarding_data.get('call_id')}: {e}", exc_info=True)
        path_results["status"] = "failed"
        path_results["error_detail"] = str(e)
    return path_results

async def _run_weddingverse_metadata_insert_path(metadata_data: dict):
    """Handles inserting data into MongoDB (WeddingVerse_metadata collection)."""
    path_results = {"status": "started", "steps": []}
    try:
        mongo_result = await real_mongo_insert_weddingverse_metadata(metadata_data)
        path_results["steps"].append({"MongoDB WeddingVerse Metadata Insert": mongo_result})
        path_results["status"] = "completed"
    except HTTPException as e:
        logger.error(f"❌ Error in MongoDB WeddingVerse Metadata insert path for {metadata_data.get('call_id')}: {e.detail}")
        path_results["status"] = "failed"
        path_results["error_detail"] = e.detail
    except Exception as e:
        logger.error(f"❌ Unexpected error in MongoDB WeddingVerse Metadata insert path for {metadata_data.get('call_id')}: {e}", exc_info=True)
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

    # 1. Execute 'Code' Block to extract data and fetch call metadata
    vendor_onboarding_data_for_mongo, whatsapp_customer_phone, whatsapp_customer_name, salesforce_context, _google_sheets_data, weddingverse_metadata = \
        await code_block_logic(payload)

    reference_id = vendor_onboarding_data_for_mongo.get('referenceID')

    # Initialize flags for skipping MongoDB inserts
    skip_vendor_onboarding_insert = False
    skip_weddingverse_metadata_insert = False

    # Initialize results map with default 'not_attempted' status for all potential services
    results_map = {
        "mongodb_vendor_onboarding_summary": {"status": "not_attempted", "reason": "Task not yet processed"},
        "mongodb_weddingverse_metadata_summary": {"status": "not_attempted", "reason": "Task not yet processed"},
        "whatsapp_confirmation_summary": {"status": "not_attempted", "reason": "Task not yet processed"},
        "salesforce_onboarding_summary": {"status": "not_attempted", "reason": "Task not yet processed"},
    }

    # Defensive check: Ensure db and metadata_db are not None before attempting to use them for duplicate checks
    if db is None or metadata_db is None:
        logger.critical(f"MongoDB clients (db or metadata_db) are None for call_id {payload.call_id}. Cannot perform duplicate check. Ensure MongoDB is initialized on startup.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MongoDB clients not initialized. Cannot perform duplicate check. Please check server logs for MongoDB connection errors during application startup."
        )

    if reference_id:
        logger.info(f"Checking for existing referenceID '{reference_id}' for call_id {payload.call_id} in MongoDB collections.")
        
        # Check for existing referenceID in VENDOR_ONBOARDING_COLLECTION
        existing_vendor_data = db[settings.VENDOR_ONBOARDING_COLLECTION].find_one({"referenceID": reference_id})
        if existing_vendor_data:
            skip_vendor_onboarding_insert = True
            results_map["mongodb_vendor_onboarding_summary"] = {"status": "skipped", "reason": f"Duplicate referenceID '{reference_id}' found in '{settings.VENDOR_ONBOARDING_COLLECTION}'."}
            logger.warning(f"Skipping Vendor Onboarding insert for call_id {payload.call_id}: referenceID '{reference_id}' already exists in '{settings.VENDOR_ONBOARDING_COLLECTION}'.")
        
        # Check for existing referenceID in WEDDINGVERSE_METADATA_COLLECTION
        existing_metadata = metadata_db[settings.WEDDINGVERSE_METADATA_COLLECTION].find_one({"referenceID": reference_id})
        if existing_metadata:
            skip_weddingverse_metadata_insert = True
            results_map["mongodb_weddingverse_metadata_summary"] = {"status": "skipped", "reason": f"Duplicate referenceID '{reference_id}' found in '{settings.WEDDINGVERSE_METADATA_COLLECTION}'."}
            logger.warning(f"Skipping WeddingVerse Metadata insert for call_id {payload.call_id}: referenceID '{reference_id}' already exists in '{settings.WEDDINGVERSE_METADATA_COLLECTION}'.")
    else:
        logger.warning(f"No referenceID found for call_id {payload.call_id}. Proceeding with all MongoDB inserts.")

    # 2. Prepare tasks dynamically based on what needs to be run
    tasks_to_run = []
    # This list will keep track of the keys in the order tasks are added, for mapping results
    ordered_keys_for_results = [] 

    # Conditionally include MongoDB insert tasks
    if not skip_vendor_onboarding_insert:
        tasks_to_run.append(asyncio.create_task(_run_mongodb_insert_path(vendor_onboarding_data_for_mongo)))
        ordered_keys_for_results.append("mongodb_vendor_onboarding_summary")
    
    if not skip_weddingverse_metadata_insert:
        tasks_to_run.append(asyncio.create_task(_run_weddingverse_metadata_insert_path(weddingverse_metadata)))
        ordered_keys_for_results.append("mongodb_weddingverse_metadata_summary")

    # --- Conditional Inclusion of Other Services ---
    _ENABLE_WHATSAPP = False # Keep as False unless you want to enable
    if _ENABLE_WHATSAPP:
        tasks_to_run.append(asyncio.create_task(_run_whatsapp_confirmation_path(
            customer_phone=whatsapp_customer_phone,
            customer_name=whatsapp_customer_name,
            call_id=payload.call_id
        )))
        ordered_keys_for_results.append("whatsapp_confirmation_summary")

    _ENABLE_SALESFORCE = False # Keep as False unless you want to enable
    if _ENABLE_SALESFORCE:
        tasks_to_run.append(asyncio.create_task(_run_salesforce_onboarding_path(
            salesforce_context=salesforce_context,
            full_transcript=payload.transcript
        )))
        ordered_keys_for_results.append("salesforce_onboarding_summary")


    # Execute all prepared tasks concurrently
    if tasks_to_run:
        all_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
        
        for i, key in enumerate(ordered_keys_for_results):
            if i < len(all_results):
                result = all_results[i]
                if isinstance(result, Exception):
                    logger.error(f"Error in {key} for call_id {payload.call_id}: {result}", exc_info=True)
                    results_map[key] = {"status": "failed", "error": str(result)}
                else:
                    results_map[key] = result
            else:
                logger.warning(f"Mismatch in task results for key: {key}. Expected more results than received.")
    else:
        logger.warning(f"No tasks were enabled or all tasks were skipped for call_id: {payload.call_id}. Returning results map.")

    logger.info(f"✅ Workflow execution complete for Call ID: {payload.call_id}")

    return results_map

# Ensure the httpx client is closed when the application shuts down
async def shutdown_httpx_client():
    global _httpx_client
    if _httpx_client:
        await _httpx_client.aclose()
        logger.info("httpx client closed.")