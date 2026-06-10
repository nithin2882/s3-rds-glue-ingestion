import os
import boto3
import pandas as pd
from io import StringIO
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import text

load_dotenv()

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

bucket = os.getenv("S3_BUCKET_NAME")

engine = create_engine(
    f"mysql+pymysql://{os.getenv('RDS_USER')}:"
    f"{os.getenv('RDS_PASSWORD')}@"
    f"{os.getenv('RDS_HOST')}:"
    f"{os.getenv('RDS_PORT')}/"
    f"{os.getenv('RDS_DATABASE')}"
)

response = s3.list_objects_v2(
    Bucket=bucket,
    Prefix="fallback/"
)

files = response.get("Contents", [])

csv_files = [
    obj["Key"]
    for obj in files
    if obj["Key"].endswith(".csv")
]

if not csv_files:
    print("No failed files found in fallback folder.")
    exit()

print([obj["Key"] for obj in files]) 

for file in files:

    key = file["Key"]

    if not key.endswith(".csv"):
        continue

    print(f"Processing {key}")

    obj = s3.get_object(
        Bucket=bucket,
        Key=key
    )

    content = obj["Body"].read().decode("utf-8")

    if not content.strip():
        print(f"Skipping empty file: {key}")
        continue

    df = pd.read_csv(StringIO(content))

    try:

        with engine.begin() as conn:

            for _, row in df.iterrows():

                conn.execute(
                    text("""
                        INSERT INTO users (
                            user_id,
                            first_name,
                            last_name,
                            email,
                            phone,
                            date_of_birth,
                            gender,
                            city,
                            state,
                            country,
                            signup_date,
                            last_login,
                            status,
                            is_premium,
                            total_orders,
                            total_spent
                        )
                        VALUES (
                            :user_id,
                            :first_name,
                            :last_name,
                            :email,
                            :phone,
                            :date_of_birth,
                            :gender,
                            :city,
                            :state,
                            :country,
                            :signup_date,
                            :last_login,
                            :status,
                            :is_premium,
                            :total_orders,
                            :total_spent
                        )
                        ON DUPLICATE KEY UPDATE
                            first_name = VALUES(first_name),
                            last_name = VALUES(last_name),
                            email = VALUES(email),
                            phone = VALUES(phone),
                            status = VALUES(status),
                            total_orders = VALUES(total_orders),
                            total_spent = VALUES(total_spent)
                    """),
                    row.to_dict()
                )

        print(f"Loaded {key} into RDS")

        s3.delete_object(
            Bucket=bucket,
            Key=key
        )

        print(f"Deleted {key}")

    except Exception as e:

        print(f"Replay failed for {key}: {e}")