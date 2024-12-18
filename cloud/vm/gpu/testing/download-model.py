import os
import json
import logging

from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# ---------------------------
# Config Setup
# ---------------------------
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
# Logging Setup
# ---------------------------
logging.basicConfig(
    filename='testing.log',
    filemode='a',  # Append mode
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.info("Started downloading model...")

# ---------------------------
# Configuration & Key Vault Setup
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
# Azure Storage configuration
# ---------------------------
container_name = config["container_name"]
model_container_name = config["model_container_name"]
dataset_archive = config["dataset_archive"]
model_name = config["model_name"]

blob_service_client = BlobServiceClient.from_connection_string(connection_string)
model_blob_client = blob_service_client.get_container_client(model_container_name)

# ---------------------------
# Fetch and Load Model
# ---------------------------
def fetch_model_from_azure(model_name):
    """Fetch the model from Azure Blob Storage."""
    logging.info(f"Fetching model: {model_name} from Azure Blob Storage.")
    local_model_path = f"models/{model_name}"
    if not os.path.exists("models"):
        os.makedirs("models")

    blob_client = model_blob_client.get_blob_client(model_name)
    with open(local_model_path, "wb") as file:
        file.write(blob_client.download_blob().readall())
    logging.info(f"Model saved locally at {local_model_path}")
    return local_model_path

model_path = fetch_model_from_azure(model_name)
print(model_path)