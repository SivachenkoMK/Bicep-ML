import os
import datetime
import json
import logging
import zipfile

from tensorflow.keras.utils import image_dataset_from_directory
from tensorflow.keras.applications.resnet50 import ResNet50
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
dataset_archive = config["dataset_archive"]
vm_size = config["vm_size"]

fire_directory = 'fire'
nofire_directory = 'nofire'
data_dir = "/mnt/data/training"

fire_path = os.path.join(data_dir, fire_directory)
nofire_path = os.path.join(data_dir, nofire_directory)

logging.info("Initializing BlobServiceClient with the retrieved connection string.")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

# ---------------------------
# Helper Functions
# ---------------------------
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

    # 4. Return the imageNumber dictionary
    logging.info(f"Image counts: {imageNumber}")
    return imageNumber

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

def save_model_to_azure(model, epoch):
    """Save the model to Azure Blob Storage at specified epoch using the .keras format."""
    if epoch == 5:
        logging.info("5th epoch reached. Saving model to Azure.")
        # Get the current date and VM size
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        # Define the filename
        model_filename = f"{date_str}-GPU-{vm_size}-epoch-{epoch}.keras"

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
prepare_dataset()

print(imageNumber)

num_fire_images = imageNumber[fire_path]
num_nofire_images = imageNumber[nofire_path]

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

train_generator = image_dataset_from_directory(
    data_dir,
    image_size=(224, 224),
    batch_size=32,
    subset='training',
    class_names=['fire', 'nofire'],
    validation_split=0.2,
    seed=481,
    shuffle=True
)

validation_generator = image_dataset_from_directory(
    data_dir,
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
save_dir = '/mnt/data/saved_models_per_epoch'
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
    epochs=5,
    validation_data=validation_generator,
    class_weight=class_weights,
    callbacks=[checkpoint]
)
logging.info("Model training completed.")

# ---------------------------
# Save Model after 5th epoch
# ---------------------------
save_model_to_azure(model, epoch=5)

logging.info("Script execution completed.")