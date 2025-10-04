#!/usr/bin/env python3
"""
ec2_instance_creator.py

Challenge 2: Create an EC2 instance using boto3.
- Interactive (choose OS) and non-interactive (--ami, --name) modes.
- Credentials/region read from `.env` or environment variables.
- Uses SSM Parameter Store when available, with fallback to describe_images.
- Prints basic info after instance creation.

Dependencies:
    pip install boto3 python-dotenv
"""

import os
import sys
import argparse
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    sys.exit("❌ Missing AWS credentials. Please set them in .env or environment variables.")

# SSM Parameter paths (may not exist in all regions for Linux distros)
SSM_AMI_PATHS = {
    "debian-12": "/aws/service/debian/debian-12/amd64/stable/current/hvm/ebs-gp2/ami-id",
    "ubuntu-24.04": "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id",
    "windows-2022": "/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base",
}


def parse_args():
    parser = argparse.ArgumentParser(description="EC2 Instance Creator")
    parser.add_argument("--ami", type=str, help="AMI ID to use (skips OS selection if provided)")
    parser.add_argument("--name", type=str, help="Instance name (tag)")
    parser.add_argument("--region", type=str, default=AWS_REGION, help=f"AWS region (default: {AWS_REGION})")
    parser.add_argument("--instance-type", type=str, default="t3.micro", help="EC2 instance type (default: t3.micro)")
    parser.add_argument("--wait", action="store_true", help="Wait for instance to enter running state")
    return parser.parse_args()


def create_session(region):
    """Create a boto3 session using credentials from env/.env"""
    try:
        return boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN,
            region_name=region,
        )
    except NoCredentialsError:
        sys.exit("❌ No valid AWS credentials available.")
    except Exception as e:
        sys.exit(f"❌ Failed to create boto3 session: {e}")


def get_latest_ami(session, os_choice):
    """Get the latest AMI ID using SSM (preferred) or describe_images (fallback)."""
    ssm = session.client("ssm")
    ec2_client = session.client("ec2")

    # Try SSM first
    if os_choice in SSM_AMI_PATHS:
        try:
            param_name = SSM_AMI_PATHS[os_choice]
            resp = ssm.get_parameter(Name=param_name)
            return resp["Parameter"]["Value"]
        except Exception:
            print(f"⚠️ SSM parameter not found for {os_choice}, falling back to describe_images...")

    # Fallback: use describe_images
    if os_choice == "ubuntu-24.04":
        owner = "099720109477"  # Canonical
        name_filter = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
    elif os_choice == "debian-12":
        owner = "136693071363"  # Debian official
        name_filter = "debian-12-amd64-*"
    else:
        return None

    try:
        resp = ec2_client.describe_images(
            Owners=[owner],
            Filters=[
                {"Name": "name", "Values": [name_filter]},
                {"Name": "state", "Values": ["available"]},
            ],
        )
        images = resp.get("Images", [])
        if not images:
            return None
        images.sort(key=lambda x: x["CreationDate"], reverse=True)
        return images[0]["ImageId"]
    except Exception as e:
        print(f"❌ Failed to find AMI for {os_choice}: {e}")
        return None


def select_os():
    print("Select OS:")
    print("1) Debian 12")
    print("2) Ubuntu Server 24.04 LTS")
    print("3) Windows Server 2022 Base")
    choice = input("Enter choice [1-3]: ").strip()
    mapping = {"1": "debian-12", "2": "ubuntu-24.04", "3": "windows-2022"}
    return mapping.get(choice)


def print_instance_info(desc):
    iid = desc["InstanceId"]
    state = desc["State"]["Name"]
    public_ip = desc.get("PublicIpAddress")
    private_ip = desc.get("PrivateIpAddress")
    print("\n✅ Instance created:")
    print(f"  ID: {iid}")
    print(f"  State: {state}")
    print(f"  Public IP: {public_ip}")
    print(f"  Private IP: {private_ip}")


def main():
    args = parse_args()

    # Create boto3 session and clients
    session = create_session(args.region)
    ec2_client = session.client("ec2")
    ec2_resource = session.resource("ec2")

    ami = args.ami
    if not ami:
        os_choice = select_os()
        if not os_choice:
            sys.exit("❌ Invalid OS choice.")
        print(f"🔍 Fetching latest AMI for {os_choice}...")
        ami = get_latest_ami(session, os_choice)
        if not ami:
            sys.exit("❌ Could not resolve AMI ID. Try providing --ami manually.")

    name = args.name or input("Enter instance name: ").strip()
    if not name:
        sys.exit("❌ Instance name cannot be empty.")

    try:
        instances = ec2_resource.create_instances(
            ImageId=ami,
            InstanceType=args.instance_type,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": name}],
            }],
        )
        instance = instances[0]
        print(f"🚀 Instance launching: {instance.id}")
    except ClientError as e:
        sys.exit(f"❌ Failed to create instance: {e}")

    if args.wait:
        print("⏳ Waiting for instance to enter running state...")
        instance.wait_until_running()
        instance.reload()

    # Fetch latest description
    desc = ec2_client.describe_instances(InstanceIds=[instance.id])["Reservations"][0]["Instances"][0]
    print_instance_info(desc)


if __name__ == "__main__":
    main()