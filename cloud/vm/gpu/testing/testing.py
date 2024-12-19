import os
import logging
import json
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# ---------------------------
# Logging Setup
# ---------------------------
logging.basicConfig(
    filename='model_testing.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.info("Testing script started. Initializing setup...")

# ---------------------------
# Load Configuration
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
# Azure Key Vault and Blob Storage Setup
# ---------------------------
key_vault_name = config["key_vault_name"]
container_name = config["container_name"]
model_container_name = config["model_container_name"]
model_name = config["model_name"]

fire_directory = 'fire'
nofire_directory = 'nofire'
data_dir = "/mnt/data/testing"

fire_path = os.path.join(data_dir, fire_directory)
nofire_path = os.path.join(data_dir, nofire_directory)

KVUri = f"https://{key_vault_name}.vault.azure.net/"
credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url=KVUri, credential=credential)

logging.info("Attempting to retrieve Azure Storage connection string from Key Vault.")

model_path = f"models/{model_name}"

model = tf.keras.models.load_model(model_path)
logging.info(f"Successfully loaded model from {model_path}")

# ---------------------------
# Test Data Preparation
# ---------------------------
test_datagen = ImageDataGenerator(rescale=1.0 / 255)
test_generator = test_datagen.flow_from_directory(
    data_dir,
    target_size=(224, 224),
    batch_size=32,
    class_mode='binary',
    shuffle=True
)

# ---------------------------
# Model Evaluation
# ---------------------------
logging.info("Starting model evaluation.")
test_loss, test_accuracy, test_precision, test_recall = model.evaluate(
    test_generator,
    steps=test_generator.samples // test_generator.batch_size,
    verbose=1
)

logging.info(f"Model Evaluation Results: Loss={test_loss:.4f}, Accuracy={test_accuracy:.4f}, Precision={test_precision:.4f}, Recall={test_recall:.4f}")

logging.info("Testing script completed.")