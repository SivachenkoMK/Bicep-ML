# This version is not verified and to be optimized to Azure Cloud
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import matplotlib.pyplot as plt
import os

test_datagen = ImageDataGenerator(rescale=1./255)
test_generator = test_datagen.flow_from_directory(
    'Testing',
    target_size=(224, 224),
    batch_size=32,
    class_mode='binary',
    shuffle=True
)

best_model_path = 'saved_models_per_epoch/model_epoch_1_10.h5'

model = tf.keras.models.load_model(best_model_path)

test_loss, test_accuracy, test_precision, test_recall = model.evaluate(
    test_generator,
    steps=test_generator.samples // test_generator.batch_size,
    verbose=1
)

print(f"Test results for model:")
print(f"Loss: {test_loss:.4f}")
print(f"Accuracy: {test_accuracy:.4f}")
print(f"Precision: {test_precision:.4f}")
print(f"Recall: {test_recall:.4f}")

metrics = ['Loss', 'Accuracy', 'Precision', 'Recall']
values = [test_loss, test_accuracy, test_precision, test_recall]

plt.figure(figsize=(10, 6))
plt.bar(metrics, values, color='skyblue')
plt.title('Results based on testing data')
plt.ylabel('Value')
plt.savefig(f"saved_models_per_epoch/testing_metrics.png", format="png", dpi=300)
plt.show()