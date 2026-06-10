import os
import boto3
import pandas as pd
from io import StringIO
from dotenv import load_dotenv
from sqlalchemy import create_engine
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")

FILE_NAME = "users.csv"

logging.info("Reading file from S3")

def validate_data(df):
    print("\nStarting data validation...")

    print(f"Rows: {len(df)}")

    null_count = df.isnull().sum().sum()
    print(f"Null Values: {null_count}")

    duplicate_ids = df["user_id"].duplicated().sum()
    print(f"Duplicate User IDs: {duplicate_ids}")

    invalid_emails = (
        ~df["email"].astype(str)
        .str.contains(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
                      regex=True)
    ).sum()

    print(f"Invalid Emails: {invalid_emails}")

    if duplicate_ids > 0:
        raise Exception("Duplicate user_id detected")

    logging.info("Validation successful")

def register_glue_table(s3_key):

    try:

        glue.create_table(
            DatabaseName=os.getenv("GLUE_DATABASE"),
            TableInput={
                "Name": "users_fallback",
                "StorageDescriptor": {
                    "Columns": [
                        {"Name": "user_id", "Type": "int"},
                        {"Name": "first_name", "Type": "string"},
                        {"Name": "last_name", "Type": "string"},
                        {"Name": "email", "Type": "string"},
                        {"Name": "phone", "Type": "string"},
                        {"Name": "date_of_birth", "Type": "date"},
                        {"Name": "gender", "Type": "string"},
                        {"Name": "city", "Type": "string"},
                        {"Name": "state", "Type": "string"},
                        {"Name": "country", "Type": "string"},
                        {"Name": "signup_date", "Type": "timestamp"},
                        {"Name": "last_login", "Type": "timestamp"},
                        {"Name": "status", "Type": "string"},
                        {"Name": "is_premium", "Type": "boolean"},
                        {"Name": "total_orders", "Type": "int"},
                        {"Name": "total_spent", "Type": "double"}
                    ],
                    "Location": f"s3://{S3_BUCKET}/{s3_key}",
                    "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                    "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
                },
                "TableType": "EXTERNAL_TABLE"
            }
        )

        print("Glue table registered successfully")

    except glue.exceptions.AlreadyExistsException:
        print("Glue table already exists")


def fallback_to_s3(df):
    print("Saving failed records to S3 fallback zone...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    fallback_key = f"fallback/users_failed_{timestamp}.csv"

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=fallback_key,
        Body=csv_buffer.getvalue()
    )

    print(f"Fallback file saved: {fallback_key}")

    return fallback_key

engine = create_engine(
    f"mysql+pymysql://{os.getenv('RDS_USER')}:"
    f"{os.getenv('RDS_PASSWORD')}@"
    f"{os.getenv('RDS_HOST')}:"
    f"{os.getenv('RDS_PORT')}/"
    f"{os.getenv('RDS_DATABASE')}"
)

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

glue = boto3.client(
    "glue",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

response = s3.get_object(
    Bucket=S3_BUCKET,
    Key=FILE_NAME
)

csv_content = response["Body"].read().decode("utf-8")

df = pd.read_csv(StringIO(csv_content))

validate_data(df)

print("\nFile loaded successfully")
print(f"Total Rows: {len(df)}")
print("\nColumns:")
print(df.columns.tolist())

print("\nFirst 5 Records:")
print(df.head())


try:
    df.to_sql(
        "users",
        con=engine,
        if_exists="append",
        index=False
    )

    logging.info("Data inserted into RDS")

except Exception as e:

    print(f"RDS Load Failed: {e}")

    fallback_file = fallback_to_s3(df)

    register_glue_table(fallback_file)