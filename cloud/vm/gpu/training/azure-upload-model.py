import os
import logging
import datetime
import json
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        filename='model_upload.log',
        filemode='a',  # Append mode
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

setup_logging()
logging.info("Starting model upload script.")

def load_config(file_path='config.json'):
    """Load configuration from a JSON file."""
    try:
        with open(file_path, 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {file_path}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON configuration file: {e}")
        raise

config = load_config()

# ---------------------------
# Key Vault Setup
# ---------------------------
key_vault_name = config["key_vault_name"]        # e.g. "mykeyvault"
storage_connection_string_secret_name = "AzureStorageConnectionString"

KVUri = f"https://{key_vault_name}.vault.azure.net/"
credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url=KVUri, credential=credential)

logging.info("Attempting to retrieve Azure Storage connection string from Key Vault.")
connection_string_secret = secret_client.get_secret(storage_connection_string_secret_name)
connection_string = connection_string_secret.value

if not connection_string:
    logging.error("Azure Storage connection string not found or empty.")
    raise ValueError("Azure Storage connection string not found or empty.")
else:
    logging.info("Successfully retrieved Azure Storage connection string.")

# ---------------------------
# Azure Blob Storage Setup
# ---------------------------
model_container_name = config["model_container_name"]
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

logging.info("BlobServiceClient initialized.")

def upload_model_to_blob(model_filepath, vm_size):
    """Upload a model to Azure Blob Storage."""
    if not os.path.exists(model_filepath):
        logging.error(f"Model file not found: {model_filepath}")
        raise FileNotFoundError(f"Model file not found: {model_filepath}")

    # Get the current date
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # Define the blob name
    model_filename = os.path.basename(model_filepath)
    blob_name = f"{date_str}-GPU-{vm_size}-{model_filename}"

    logging.info(f"Uploading {model_filepath} to Azure Blob Storage as {blob_name}.")

    # Upload the model to Azure Blob Storage
    model_blob_client = blob_service_client.get_blob_client(container=model_container_name, blob=blob_name)
    with open(model_filepath, "rb") as data:
        model_blob_client.upload_blob(data, overwrite=True)

    logging.info(f"Model successfully uploaded to Azure Blob Storage: {blob_name}")

# ---------------------------
# Main Logic
# ---------------------------
if __name__ == "__main__":
    model_filepath = "/mnt/data/saved_models_per_epoch/model_epoch_1_07.keras"
    vm_size = config.get("vm_size", "Unknown_VM")

    try:
        upload_model_to_blob(model_filepath, vm_size)
    except Exception as e:
        logging.error(f"An error occurred during the model upload: {e}")
        raise