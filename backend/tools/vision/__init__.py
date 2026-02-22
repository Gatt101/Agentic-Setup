from tools.vision.annotator import annotate_xray_image
from tools.vision.body_part_detector import detect_body_part
from tools.vision.hand_detector import detect_hand_fracture
from tools.vision.leg_detector import detect_leg_fracture
from tools.vision.uploader import upload_image_to_storage

VISION_TOOLS = [
    detect_body_part,
    detect_hand_fracture,
    detect_leg_fracture,
    annotate_xray_image,
    upload_image_to_storage,
]

__all__ = ["VISION_TOOLS"]
