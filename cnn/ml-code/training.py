import os
import datetime
import requests
import numpy as np
import matplotlib
import json
matplotlib.use('Agg')  # Use a non-interactive backend for headless environments
import matplotlib.pyplot as plt
from io import BytesIO
import logging

import tensorflow as tf
from tensorflow.keras.utils import load_img, img_to_array, image_dataset_from_directory
from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras import layers, models, optimizers, metrics, Sequential

from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# tf.debugging.set_log_device_placement(True) # Enable to test if GPU is assigned to perform operations

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
    filename='training.log',
    filemode='a',  # Append mode
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.info("Training script started. Initializing setup...")

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
root_training_directory = config["root_training_directory"]
fire_directory = config["fire_directory"]
nofire_directory = config["nofire_directory"]

logging.info("Initializing BlobServiceClient with the retrieved connection string.")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

# ---------------------------
# Helper Functions
# ---------------------------
imageNumber = {}

def fetch_and_store_images_from_azure(directory, target_directory):
    """
    Fetch all image blobs from a given directory prefix in the Azure container and store them in the specified local directory.

    Args:
        directory (str): The prefix directory in the Azure container.
        target_directory (str): The local directory to save the fetched images.
    """
    logging.info(f"Fetching and storing images from directory: {directory} to {target_directory}")
    # Ensure target directory exists
    if not os.path.exists(target_directory):
        os.makedirs(target_directory)
    image_paths = []
    blobs = container_client.list_blobs(name_starts_with=directory)
    
    for blob in blobs:
        blob_name = blob.name
        logging.debug(f"Processing blob: {blob_name}")
        # Fetch blob data
        blob_client = container_client.get_blob_client(blob_name)
        blob_data = blob_client.download_blob()
        image_bytes = blob_data.readall()
        # Save blob as file in the target directory
        file_path = os.path.join(target_directory, os.path.basename(blob_name))
        with open(file_path, 'wb') as file:
            file.write(image_bytes)
        logging.info(f"Saved image to {file_path}")
        image_paths.append(file_path)
    logging.info(f"Successfully fetched and stored {len(image_paths)} images from {directory}.")
    imageNumber[target_directory] = len(image_paths)
    return image_paths

def create_model():
    """Create a ResNet50-based model."""
    logging.info("Creating ResNet50-based model.")
    base_model = ResNet50(input_shape=(224, 224, 3),
                          include_top=False,
                          weights='imagenet')
    base_model.trainable = True

    model = models.Sequential([
        base_model,
        layers.GlobalAveragePooling2D(),
        layers.BatchNormalization(),
        layers.Dense(512, activation='relu'),
        layers.BatchNormalization(),
        layers.Dropout(0.5),
        layers.Dense(1, activation='sigmoid')
    ])
    model.compile(
        optimizer=optimizers.Adam(learning_rate=0.00001),
        loss='binary_crossentropy',
        metrics=['accuracy', metrics.Precision(name='precision'), metrics.Recall(name='recall')]
    )
    logging.info("Model created and compiled successfully.")
    return model

def get_vm_size():
    """Retrieve the VM size from Azure Instance Metadata Service."""
    logging.info("Fetching VM size from Azure Instance Metadata Service.")
    try:
        response = requests.get(
            "http://169.254.169.254/metadata/instance/size?api-version=2021-02-01",
            headers={"Metadata": "true"}
        )
        if response.status_code == 200:
            vm_size = response.json().get("size", "unknown_size")
            logging.info(f"VM size retrieved: {vm_size}")
            return vm_size
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching VM size: {e}")
    return "unknown_size"

def save_model_to_azure(model, epoch):
    """Save the model to Azure Blob Storage at specified epoch using the .keras format."""
    if epoch == 10:
        logging.info("10th epoch reached. Saving model to Azure.")
        # Get the current date and VM size
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        vm_size = get_vm_size()

        # Define the filename
        model_filename = f"{date_str}-GPU-{vm_size}.keras"

        # Save the model locally in .keras format
        model_filepath = f"{save_dir}/{model_filename}"
        model.save(model_filepath)  # This will create a .keras file
        logging.info(f"Model saved locally at {model_filepath}")

        # Upload the model to Azure Blob Storage
        model_blob_client = blob_service_client.get_blob_client(container=model_container_name, blob=model_filename)
        with open(model_filepath, "rb") as data:
            model_blob_client.upload_blob(data, overwrite=True)

        logging.info(f"Model uploaded to Azure Blob Storage as {model_filename}")

# ---------------------------
# Load data and prepare class weights
# ---------------------------
logging.info("Loading and preparing data.")
fetch_and_store_images_from_azure(fire_directory, fire_directory)
fetch_and_store_images_from_azure(nofire_directory, nofire_directory)

num_fire_images = imageNumber[fire_directory]
num_nofire_images = imageNumber[nofire_directory]

total_images = num_fire_images + num_nofire_images

if num_fire_images == 0 or num_nofire_images == 0:
    logging.warning("One of the classes has zero images. This will cause issues with training and class weights.")
    raise ValueError("One of the classes (fire or nofire) has zero images. Cannot compute class weights.")

weight_for_fire = (1 / num_fire_images) * (total_images) / 2.0
weight_for_nofire = (1 / num_nofire_images) * (total_images) / 2.0
class_weights = {0: weight_for_nofire, 1: weight_for_fire}

print(f"Class weights calculated: no fire={class_weights[0]}, fire={class_weights[1]}")

# ---------------------------
# Split Data into Training and Validation
# ---------------------------
print("Splitting data into training and validation sets.")

fire_directory_absolute = os.path.abspath(f"./{root_training_directory}")  # Convert to absolute path
print(fire_directory_absolute)
train_generator = image_dataset_from_directory(
    fire_directory_absolute,
    image_size=(224, 224),
    batch_size=32,
    subset='training',
    class_names=['fire', 'nofire'],
    validation_split=0.2,
    seed=481,
    shuffle=True
)

nofire_directory_absolute = os.path.abspath(f"./{root_training_directory}")  # Convert to absolute path
print(nofire_directory_absolute)
validation_generator = image_dataset_from_directory(
    nofire_directory_absolute,
    image_size=(224, 224),
    batch_size=32,
    class_names=['fire', 'nofire'],
    validation_split=0.2,
    subset='validation',
    seed=481,
    shuffle=False
)

data_augmentation = Sequential([
    layers.Rescaling(1./255),
    layers.RandomRotation(0.1),
    layers.RandomZoom(0.2),
    layers.RandomFlip("horizontal")
])

train_generator = train_generator.map(
    lambda x, y: (data_augmentation(x, training=True), y)
)

validation_generator = validation_generator.map(
    lambda x, y: (layers.Rescaling(1./255)(x), y)
)

# ---------------------------
# Create local directory to save models per epoch
# ---------------------------
save_dir = 'saved_models_per_epoch'
if not os.path.exists(save_dir):
    os.makedirs(save_dir)
    logging.info(f"Directory {save_dir} created for saving models.")

# ---------------------------
# Build and Train Model
# ---------------------------
model = create_model()

checkpoint = ModelCheckpoint(
    filepath=f"{save_dir}/model_epoch_1_{{epoch:02d}}.keras",
    save_best_only=False,
    save_weights_only=False,
    verbose=1
)

logging.info("Starting model training.")
history = model.fit(
    train_generator,
    epochs=10,
    validation_data=validation_generator,
    class_weight=class_weights,
    callbacks=[checkpoint]
)
logging.info("Model training completed.")

# ---------------------------
# Save Model after 10th epoch
# ---------------------------
save_model_to_azure(model, epoch=10)

# ---------------------------
# Plot Training History
# ---------------------------
logging.info("Plotting training history.")
epochs_range = range(1, 11)

plt.figure(figsize=(20, 8))

plt.subplot(1, 3, 1)
plt.plot(epochs_range, history.history['accuracy'], label='Training Accuracy')
plt.plot(epochs_range, history.history['val_accuracy'], label='Validation Accuracy')
plt.legend(loc='lower right')
plt.title('Training and Validation Accuracy')

plt.subplot(1, 3, 2)
plt.plot(epochs_range, history.history['precision'], label='Training Precision')
plt.plot(epochs_range, history.history['val_precision'], label='Validation Precision')
plt.legend(loc='lower right')
plt.title('Training and Validation Precision')

plt.subplot(1, 3, 3)
plt.plot(epochs_range, history.history['recall'], label='Training Recall')
plt.plot(epochs_range, history.history['val_recall'], label='Validation Recall')
plt.legend(loc='lower right')
plt.title('Training and Validation Recall')

plt.tight_layout()
plot_path = f"{save_dir}/overall_training_metrics2.png"
plt.savefig(plot_path, format="png", dpi=300)
logging.info(f"Training metrics plot saved at {plot_path}")

logging.info("Script execution completed.")