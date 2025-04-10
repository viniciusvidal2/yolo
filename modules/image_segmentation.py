from ultralytics import YOLO
import os
from typing import Tuple
from PIL import Image
import numpy as np
from matplotlib import colormaps


class ImageSegmentation:
    def __init__(self, model_path: str):
        """This class is used to perform image segmentation using a YOLOv11 model.

        Args:
            model_path (str): path to the trained YOLOv11 model
        """
        self.model = YOLO(model_path)
        self.detections_by_class_dict = dict()
        self.image_detections_mask = None  # All the classes for each pixel
        self.masked_original_image = None
        # Class codes from the model, can be used in other modules
        self.image_class_mask_codes = dict()
        self.image_class_mask_codes["background"] = 0

    def segment_classes(self, image: np.ndarray) -> bool:
        """Predicts the segmentation masks, classes and boxes for the given image.

        Args:
            image_path (np.ndarray): original image

        Returns:
            bool: True if masks and boxes were detected, False otherwise
        """
        # Start the masked image with the original one
        self.masked_original_image = image.copy()

        # Load the image to get the dimensions
        resized_image_pil = Image.fromarray(image)
        image_width, image_height = resized_image_pil.size
        # If image is not 640x640, resize it
        if image_width != 640 or image_height != 640:
            resized_image_pil = resized_image_pil.resize(
                (640, 640), Image.Resampling.LANCZOS)

        # Initialize the global mask
        self.image_detections_mask = np.zeros(
            (image_height, image_width), dtype=np.uint8)

        # Predict detections in the image
        results = self.model.predict(source=resized_image_pil, show=False, save=False, conf=0.2,
                                     line_width=1, save_crop=False, save_txt=False,
                                     show_labels=False, show_conf=False)

        # Check if the model has detected any masks or boxes
        if results[0].masks is None or results[0].boxes is None:
            print("No masks or boxes detected.")
            return False

        # Build the class codes dictionary from the names
        for i, name in enumerate(results[0].names.values()):
            self.image_class_mask_codes[name] = i + 1

        # Create colormap from the class codes
        classes_colormap = self.create_colormap(
            class_ids=self.image_class_mask_codes, colormap="viridis")

        # Iterate through the results and store the masks, boxes and confidences
        for result in results:
            for i in range(len(result.boxes)):
                # Extract info
                box = result.boxes[i].xyxy[0].tolist()
                conf = result.boxes[i].conf[0].item()
                mask = result.masks.data[i].cpu().numpy()

                # Resize the mask to the original image size
                mask = np.array(Image.fromarray(mask).resize(
                    (image_width, image_height), Image.Resampling.NEAREST))
                # Resize the box to the original image size
                box[0] = int(box[0] * image_width / 640)
                box[1] = int(box[1] * image_height / 640)
                box[2] = int(box[2] * image_width / 640)
                box[3] = int(box[3] * image_height / 640)

                # Store in dictionary
                cls_id = int(result.boxes[i].cls[0].item())
                class_name = result.names[cls_id]
                if class_name not in self.detections_by_class_dict:
                    self.detections_by_class_dict[class_name] = {
                        "masks": [], "boxes": [], "confidences": []}
                self.detections_by_class_dict[class_name]["masks"].append(mask)
                self.detections_by_class_dict[class_name]["boxes"].append(box)
                self.detections_by_class_dict[class_name]["confidences"].append(
                    conf)

                # Save the mask in the global mask with the proper detection code
                self.draw_detection_in_global_mask(mask, class_name)
                self.draw_detection_in_original_image(
                    mask, class_name, classes_colormap, 0.5)
        return True

    def draw_detection_in_original_image(self, mask: np.ndarray, class_name: str, colors: list, color_weight: float) -> None:
        """Draw the masks on top of the original image

        Args:
            img (np.ndarray): original image
            masks (np.ndarray): the list of masks
            ids (list): list of class ids for each mask
            colors (list): list of colors for each class
            color_weight (float): the weight we should use to average each class color
        """
        # Avoid classes that are not our interest
        if class_name == "barragem" or class_name == "coluna":
            return
        # Output image with masks
        masked_image = self.masked_original_image.astype(np.float32).copy()
        mask_region = mask.astype(bool)
        # Defines the colored mask with the colormap for the class id
        colored_mask = np.zeros_like(masked_image)
        class_id = self.image_class_mask_codes[class_name]
        colored_mask[mask_region] = colors[class_id]
        # Weighted sum to draw the class mask
        masked_image[mask_region] = masked_image[mask_region] * (1 - color_weight) \
            + colored_mask[mask_region] * color_weight
        # Save the masked image
        self.masked_original_image = masked_image.astype(np.uint8)

    def create_colormap(self, class_ids: dict, colormap: str) -> list:
        """Creates a colormap based on the input colormap and the number of classes

        Args:
            classes (dict): input classes with "names": id
            colormap (str): colormap to create with

        Returns:
            list: RGB colors (np.ndarrays) for each class 
        """
        mock_class_intensity = np.arange(len(class_ids))/len(class_ids)
        cmap = colormaps.get_cmap(colormap)
        colors = cmap(mock_class_intensity)[:, :3] * 255
        return colors.astype(np.uint8)

    def draw_detection_in_global_mask(self, mask: np.ndarray, class_name: str) -> None:
        """Draws a single detection in the global mask.
        Args:
            mask (np.ndarray): mask of the detection
            class_name (str): name of the class
        """
        mask_region = mask.astype(bool)
        class_code = self.image_class_mask_codes[class_name]
        for i in range(mask.shape[0]):
            for j in range(mask.shape[1]):
                # If the pixel is already marked as sedimento or macrofita, skip it
                if self.image_detections_mask[i, j] == self.image_class_mask_codes["sedimento"] or self.image_detections_mask[i, j] == self.image_class_mask_codes["macrofita"]:
                    continue
                # If the pixel is part of the mask, set it to the class code
                if mask_region[i, j]:
                    self.image_detections_mask[i, j] = class_code

    def get_detections_by_class(self, class_name: str) -> Tuple[list, list]:
        """Returns the detections for a specific class.

        Args:
            class_name (str): name of the class

        Returns:
            Tuple[list, list]: boxes and confidences for the specified class
        """
        if class_name in self.detections_by_class_dict:
            boxes = self.detections_by_class_dict[class_name]["boxes"]
            confidences = self.detections_by_class_dict[class_name]["confidences"]
            return boxes, confidences
        else:
            print(f"No such class in the model definitions: {class_name}")
            return [], []

    def get_detections_codes(self) -> dict:
        """Returns the class codes dictionary.

        Returns:
            dict: class codes dictionary
        """
        return self.image_class_mask_codes

    def get_detections_mask(self) -> np.ndarray:
        """Returns the global detections mask.

        Returns:
            np.ndarray: global detections mask
        """
        return self.image_detections_mask

    def get_masked_image(self) -> np.ndarray:
        """Returns the masked image.

        Returns:
            np.ndarray: masked image
        """
        if self.masked_original_image is None:
            print("No masked image available.")
            return None
        return self.masked_original_image

    def reset_detections(self) -> None:
        """Resets the detections dictionary.
        """
        self.detections_by_class_dict = dict()
        self.image_class_mask_codes = dict()
        self.image_class_mask_codes["background"] = 0
        self.image_detections_mask = None


if __name__ == "__main__":
    # Sample usage
    model_path = "runs/segment/train_colunas/weights/best.pt"
    image_path = os.path.join(os.getenv(
        "HOME"), "sae-sam/full_train_set/train/images/snp0206251005_png.rf.a8bbdfbc64967838a2a76b632c711c7c.jpg")
    image = np.array(Image.open(image_path))

    segmentation_model = ImageSegmentation(model_path)
    if segmentation_model.segment_classes(image):
        class_name = "sedimento"
        boxes, confidences = segmentation_model.get_detections_by_class(
            class_name)
        print(f"Detected {len(boxes)} boxes for class {class_name}.")
        print(f"Confidences: {confidences}")
        # Get the class codes
        class_codes = segmentation_model.get_detections_codes()
        print(f"Class codes: {class_codes}")
        # Get the global detections mask
        classes_mask = segmentation_model.get_detections_mask().astype(np.float32)
        # Convert the mask to PIL, apply scale to 255 and show
        mask_image_pil = Image.fromarray(
            (classes_mask * 255/np.max(classes_mask)).astype(np.uint8))
        mask_image_pil.show()
        # Get the masked image and show
        masked_image = segmentation_model.get_masked_image()
        masked_image_pil = Image.fromarray(masked_image)
        masked_image_pil.show()
        # Optionally, reset detections
        segmentation_model.reset_detections()
    else:
        print("Failed to find detections in the image.")
