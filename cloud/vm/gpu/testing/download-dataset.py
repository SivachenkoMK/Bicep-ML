import os
import json
import logging
import zipfile

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

logging.info("Testing script started. Initializing setup...")

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

fire_directory = 'fire'
nofire_directory = 'nofire'
data_dir = "/mnt/data/testing"

fire_path = os.path.join(data_dir, fire_directory)
nofire_path = os.path.join(data_dir, nofire_directory)

logging.info("Initializing BlobServiceClient with the retrieved connection string.")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

imageNumber = {}

def prepare_dataset():
    # 0. Create data directory if doesn't exist
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    
    # Make sure directories exist (creating them if they don't)
    if not os.path.exists(fire_path):
        os.makedirs(fire_path, exist_ok=True)
    if not os.path.exists(nofire_path):
        os.makedirs(nofire_path, exist_ok=True)
    
    # 1. Instead of fetching images from Azure directly, 
    # we first try to count images already present in /mnt/data.
    def count_images_in_dir(dir_path):
        # Count how many files appear to be images. 
        # We'll assume all files are images for simplicity.
        if not os.path.exists(dir_path):
            return 0
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        return len(files)
    
    imageNumber[fire_path] = count_images_in_dir(fire_path)
    imageNumber[nofire_path] = count_images_in_dir(nofire_path)

    # 2. If none of the image numbers are 0, we skip downloading.
    if imageNumber[fire_path] == 0 or imageNumber[nofire_path] == 0:
        logging.info("At least one directory is empty. Attempting to download and extract the dataset archive.")

        # 2.1. Download the archive from blob storage if we haven't got images locally
        archive_local_path = os.path.join(data_dir, dataset_archive)
        
        # Download the archive
        logging.info(f"Downloading dataset archive {dataset_archive} from container {container_name}.")
        blob_client = container_client.get_blob_client(dataset_archive)
        with open(archive_local_path, 'wb') as f:
            stream = blob_client.download_blob()
            for chunk in stream.chunks():
                f.write(chunk)
        logging.info("Download completed in chunks.")
        
        # 2.2. Extract the content (should contain fire_directory and nofire_directory)
        logging.info(f"Extracting archive {archive_local_path} to {data_dir}.")
        with zipfile.ZipFile(archive_local_path, 'r') as zip_ref:
            zip_ref.extractall(data_dir)
        
        # After extraction, we recalculate the image numbers
        imageNumber[fire_path] = count_images_in_dir(fire_path)
        imageNumber[nofire_path] = count_images_in_dir(nofire_path)

        # If after extraction at least one is still 0, exit with error
        if imageNumber[fire_path] == 0 or imageNumber[nofire_path] == 0:
            logging.error("Failed to populate both directories with images after extraction.")
            raise SystemExit("No images found after extraction. Exiting.")
    else:
        logging.info("Both directories already contain images. No download necessary.")

prepare_dataset()