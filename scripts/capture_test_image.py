import _bootstrap  # noqa: F401

from app.camera.mock_camera import MockCamera
from app.camera.usb_camera import USBCamera
from app.core.config import load_config


def main() -> None:
    config = load_config()
    camera_config = config["camera"]
    if camera_config["mode"] == "mock":
        camera = MockCamera(camera_config["test_image_dir"], camera_config["image_save_dir"])
    else:
        camera = USBCamera(
            camera_config["device_index"],
            camera_config["image_save_dir"],
            camera_config["width"],
            camera_config["height"],
        )
    print(camera.capture())


if __name__ == "__main__":
    main()
