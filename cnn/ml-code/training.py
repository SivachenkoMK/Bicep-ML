import os
import datetime
import requests
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import logging

import tensorflow as tf
from tensorflow.keras.preprocessing.image import img_to_array, load_img
from tensorflow.keras import layers, models, optimizers
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.callbacks import ModelCheckpoint
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

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
key_vault_name = "cnn-secrets"        # e.g. "mykeyvault"
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
container_name = "datasets"
model_container_name = "models"
fire_directory = "training/fire"
nofire_directory = "training/nofire"

logging.info("Initializing BlobServiceClient with the retrieved connection string.")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

# ---------------------------
# Helper Functions
# ---------------------------
def fetch_images_from_azure(directory):
    """Fetch blob names (images) from a given directory prefix in the container."""
    logging.info(f"Fetching images from directory: {directory}")
    image_paths = []
    blobs = container_client.list_blobs(name_starts_with=directory)
    for blob in blobs:
        image_paths.append(blob.name)
    logging.info(f"Found {len(image_paths)} images in {directory}")
    return image_paths

def load_image_from_azure(blob_name):
    """Load a single image blob from Azure Storage and return a processed numpy array."""
    logging.debug(f"Loading image from blob: {blob_name}")
    blob_client = container_client.get_blob_client(blob_name)
    blob_data = blob_client.download_blob()
    image_bytes = blob_data.readall()
    image = load_img(BytesIO(image_bytes), target_size=(224, 224))
    image_array = img_to_array(image) / 255.0  # Rescale
    return image_array

class AzureImageDataGenerator:
    """A custom generator to load images and labels on-the-fly from Azure Blob Storage."""
    def __init__(self, image_paths, batch_size, class_mode='binary', shuffle=True):
        self.image_paths = image_paths
        self.batch_size = batch_size
        self.class_mode = class_mode
        self.shuffle = shuffle
        self.index = 0
        self.num_samples = len(image_paths)
        self.on_epoch_end()  # Shuffle initially if required
        logging.info(f"AzureImageDataGenerator created: {self.num_samples} samples, batch_size={self.batch_size}")

    def __len__(self):
        return int(np.floor(self.num_samples / self.batch_size))

    def __getitem__(self, index):
        logging.debug(f"Fetching batch index {index}")
        batch_paths = self.image_paths[index * self.batch_size: (index + 1) * self.batch_size]
        images = np.array([load_image_from_azure(p) for p in batch_paths])
        labels = np.array([1 if 'fire' in p else 0 for p in batch_paths])
        return images, labels

    def on_epoch_end(self):
        if self.shuffle:
            np.random.shuffle(self.image_paths)
            logging.debug("Shuffled dataset at end of epoch.")

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
    model.compile(optimizer=optimizers.Adam(learning_rate=0.00001),
                  loss='binary_crossentropy',
                  metrics=['accuracy',
                           tf.keras.metrics.Precision(name='precision'),
                           tf.keras.metrics.Recall(name='recall')])
    logging.info("Model created and compiled successfully.")
    return model

def get_vm_size():
    """Retrieve the VM size from Azure Instance Metadata Service."""
    logging.info("Fetching VM size from Azure Instance Metadata Service.")
    try:
        response = requests.get("http://169.254.169.254/metadata/instance/size?api-version=2021-02-01",
                                headers={"Metadata": "true"})
        if response.status_code == 200:
            vm_size = response.json().get("size", "unknown_size")
            logging.info(f"VM size retrieved: {vm_size}")
            return vm_size
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching VM size: {e}")
    return "unknown_size"

def save_model_to_azure(model, epoch):
    """Save the model to Azure Blob Storage at specified epoch."""
    if epoch == 10:
        logging.info("10th epoch reached. Saving model to Azure.")
        # Get the current date and VM size
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        vm_size = get_vm_size()

        # Define the filename
        model_filename = f"{date_str}-GPU-{vm_size}.h5"

        # Save the model locally
        model_filepath = f"{save_dir}/{model_filename}"
        model.save(model_filepath)
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
fire_images = fetch_images_from_azure(fire_directory)
nofire_images = fetch_images_from_azure(nofire_directory)

num_fire_images = len(fire_images)
num_nofire_images = len(nofire_images)
total_images = num_fire_images + num_nofire_images

weight_for_fire = (1 / num_fire_images) * (total_images) / 2.0
weight_for_nofire = (1 / num_nofire_images) * (total_images) / 2.0
class_weights = {0: weight_for_nofire, 1: weight_for_fire}

logging.info(f"Class weights calculated: no fire={class_weights[0]}, fire={class_weights[1]}")

# ---------------------------
# Split Data into Training and Validation
# ---------------------------
logging.info("Splitting data into training and validation sets.")
train_fire = fire_images[:int(0.8 * len(fire_images))]
val_fire = fire_images[int(0.8 * len(fire_images)):]
train_nofire = nofire_images[:int(0.8 * len(nofire_images))]
val_nofire = nofire_images[int(0.8 * len(nofire_images)):]

train_images = train_fire + train_nofire
val_images = val_fire + val_nofire

train_generator = AzureImageDataGenerator(train_images, batch_size=32, class_mode='binary')
validation_generator = AzureImageDataGenerator(val_images, batch_size=32, class_mode='binary')

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
    filepath=f"{save_dir}/model_epoch_1_{{epoch:02d}}.h5",
    save_best_only=False
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
plt.show()
logging.info(f"Training metrics plot saved at {plot_path}")

logging.info("Script execution completed.")