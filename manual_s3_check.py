#!/usr/bin/env python3
"""
manual_s3_check.py

This script manually signs and sends a request to AWS S3 using SigV4 authentication
to list all buckets in the account. It supports both permanent and temporary
credentials (with session token). It loads environment variables automatically
from a .env file if present.

Dependencies:
    pip install requests python-dotenv
"""

import sys
import os
import datetime
import hashlib
import hmac
import requests
from dotenv import load_dotenv

# -------------------------------
# LOAD ENVIRONMENT
# -------------------------------
load_dotenv()  # load variables from .env if available

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")  # optional
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
SERVICE = "s3"

if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    sys.exit("❌ Missing credentials. Please check your .env or environment variables.")


# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region_name)
    k_service = sign(k_region, service_name)
    k_signing = sign(k_service, "aws4_request")
    return k_signing


# -------------------------------
# BUILD REQUEST
# -------------------------------
method = "GET"
host = "s3.amazonaws.com"
endpoint = f"https://{host}/"

# Create a timestamp
t = datetime.datetime.now(datetime.UTC)
amz_date = t.strftime("%Y%m%dT%H%M%SZ")  # e.g. 20250927T120000Z
date_stamp = t.strftime("%Y%m%d")        # e.g. 20250927

# ************* TASK 1: CREATE CANONICAL REQUEST *************
canonical_uri = "/"
canonical_querystring = ""

payload_hash = hashlib.sha256(b"").hexdigest()  # empty payload hash

canonical_headers = (
    f"host:{host}\n"
    f"x-amz-content-sha256:{payload_hash}\n"
    f"x-amz-date:{amz_date}\n"
)
if AWS_SESSION_TOKEN:
    canonical_headers += f"x-amz-security-token:{AWS_SESSION_TOKEN}\n"

signed_headers = "host;x-amz-content-sha256;x-amz-date"
if AWS_SESSION_TOKEN:
    signed_headers += ";x-amz-security-token"

canonical_request = (
    f"{method}\n{canonical_uri}\n{canonical_querystring}\n"
    f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
)

# ************* TASK 2: CREATE STRING TO SIGN *************
algorithm = "AWS4-HMAC-SHA256"
credential_scope = f"{date_stamp}/{AWS_REGION}/{SERVICE}/aws4_request"
string_to_sign = (
    f"{algorithm}\n{amz_date}\n{credential_scope}\n"
    f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
)

# ************* TASK 3: CALCULATE SIGNATURE *************
signing_key = get_signature_key(AWS_SECRET_KEY, date_stamp, AWS_REGION, SERVICE)
signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

# ************* TASK 4: ADD SIGNING INFO TO REQUEST *************
authorization_header = (
    f"{algorithm} Credential={AWS_ACCESS_KEY}/{credential_scope}, "
    f"SignedHeaders={signed_headers}, Signature={signature}"
)

headers = {
    "x-amz-date": amz_date,
    "x-amz-content-sha256": payload_hash,
    "Authorization": authorization_header,
}
if AWS_SESSION_TOKEN:
    headers["x-amz-security-token"] = AWS_SESSION_TOKEN

# -------------------------------
# SEND REQUEST
# -------------------------------
print("📡 Sending request to S3 ListBuckets API...")

response = requests.get(endpoint, headers=headers)

if response.status_code == 200:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(response.text)
    print("✅ Buckets in account:")
    for bucket in root.findall(".//{http://s3.amazonaws.com/doc/2006-03-01/}Name"):
        print(" -", bucket.text)
else:
    print("❌ Request failed:", response.status_code)
    print(response.text)