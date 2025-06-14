# FILE: email_handler.py

import os
import base64
import logging
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Optional
from config import CREDENTIALS_PATH, TOKEN_PATH, GMAIL_SCOPES, USER_EMAIL, AURA_EMAIL

logger = logging.getLogger(__name__)

def _get_service():
    """Authenticates and builds the Gmail API service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, GMAIL_SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def get_latest_email() -> Optional[dict]:
    """Fetches the latest unread email from the specified user."""
    try:
        service = _get_service()
        query = f'is:unread from:{USER_EMAIL} in:inbox'
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])

        if not messages:
            return None

        msg_id = messages[0]['id']
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        return msg

    except HttpError as error:
        logger.error("Gmail API error while fetching email: %s", error)
        return None

def parse_email_body(msg: dict) -> str:
    """Extracts the plain text body from an email message object."""
    body = ""
    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part['body'].get('data')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
    if not body: # Fallback for simple emails
        data = msg['payload']['body'].get('data')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8')
    return body.strip()

def send_reply(original_msg: dict, reply_text: str):
    """Sends a reply to an original email, maintaining the thread."""
    try:
        service = _get_service()
        headers = {h['name']: h['value'] for h in original_msg['payload']['headers']}
        
        to = headers.get('From', '')
        subject = headers.get('Subject', '(no subject)')
        message_id = headers.get('Message-ID', '')
        thread_id = original_msg['threadId']

        reply = MIMEText(reply_text)
        reply['To'] = to
        reply['Subject'] = 'Re: ' + subject
        reply['In-Reply-To'] = message_id
        reply['References'] = message_id
        
        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        body = {'raw': raw, 'threadId': thread_id}
        
        service.users().messages().send(userId='me', body=body).execute()
        logger.info("Reply sent to thread %s.", thread_id)

    except HttpError as error:
        logger.error("An error occurred sending reply: %s", error)

def archive_email(msg_id: str):
    """Marks an email as read and archives it by removing the INBOX label."""
    try:
        service = _get_service()
        body = {'removeLabelIds': ['UNREAD', 'INBOX']}
        service.users().messages().modify(userId='me', id=msg_id, body=body).execute()
        logger.info("Email %s marked as read and archived.", msg_id)
    except HttpError as error:
        logger.error("An error occurred archiving email: %s", error)

def send_system_email(subject: str, body_text: str):
    """Sends a new email from Aura to the user, not as a reply."""
    try:
        service = _get_service()
        message = MIMEText(body_text)
        message['to'] = USER_EMAIL
        message['from'] = AURA_EMAIL
        message['subject'] = subject

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw_message}
        
        service.users().messages().send(userId='me', body=body).execute()
        logger.info("System email sent to %s with subject: '%s'", USER_EMAIL, subject)

    except HttpError as error:
        logger.error("An error occurred sending system email: %s", error)