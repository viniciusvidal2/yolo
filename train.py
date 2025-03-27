from ultralytics import YOLO
from ultralytics.utils import SETTINGS
import os


def main():
    # Load YOLOv11 model
    print("Loading YOLOv11 model for segmentation task...")
    yolo = YOLO("yolo11m-seg.pt", verbose=False)

    # Set the dataset subfolder in the settings
    dataset_subfolder = "full_train_set"
    SETTINGS['datasets_dir'] = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), dataset_subfolder)
    print(f"Dataset subfolder set to: {SETTINGS['datasets_dir']}")

    # Train the model
    print("Training YOLOv11 model with the training set...")
    data_path = os.path.join(dataset_subfolder, "data.yaml")
    results = yolo.train(data=data_path, epochs=1000,
                         batch=16, device="cpu", optimizer="adam", patience=0, lrf=0.0001)


if __name__ == "__main__":
    main()
