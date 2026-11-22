import cv2 as cv
from pathlib import Path
import argparse

# extract arguments
parser = argparse.ArgumentParser(description="Detect faces in an image")
parser.add_argument("input_image", type=Path, help="Image to analyze")
parser.add_argument("output_dir", type=Path, help="Output folder")
args = parser.parse_args()

# solving and setting paths
folder_script = Path(__file__).resolve().parent
model_folder = folder_script.parent / "models"
path_image = args.input_image
output_dir = args.output_dir

if not output_dir.is_dir():
    parser.error(f"Output directory does not exist: {output_dir}")

image = cv.imread(str(path_image))

if image is not None:

    # image = cv.resize(image, None, fx=0.25, fy=0.25)
    height, width = image.shape[:2]

    detector = cv.FaceDetectorYN.create(
        model=str(model_folder / "face_detection_yunet_2023mar.onnx"),
        config="",
        # input_size=(640, 480),
        input_size=(width, height),
        score_threshold=0.6
    )
    # detector.setInputSize((640, 480))
    
    status, faces = detector.detect(image)

    images = []

    if faces is None:
        print("No face detected")
    else:
        print(f"Found {faces.shape[0]} faces.")
        annotated_image = image.copy()
        for face in faces:
            x, y, larghezza, altezza = face[:4]
            # print(f"First angle: [{x:.2f},{y:.2f}]\tSecond angle: [{(x+larghezza):.2f},{(y+altezza):.2f}]")
            # print(f"Score: {face[14]:.2f}")
            
            int_x = max(0, min(width, int(x)))
            int_y = max(0, min(height, int(y)))
            int_x_end = max(0, min(width, int(x+larghezza)))
            int_y_end = max(0, min(height, int(y+altezza)))
            
            first_angle = (int_x, int_y)
            second_angle = (int_x_end, int_y_end)
            
            if int_x_end > int_x and int_y_end > int_y:
                images.append(image[int_y:int_y_end, int_x:int_x_end].copy())
                cv.rectangle(annotated_image, first_angle, second_angle,(0,255,0),2)
            else:
                print("No valid coordinates")
        
        if image is not None:
            # Display calls require a graphical environment and a GUI-enabled OpenCV build.
            # cv.imshow("YuNet detections", annotated_image)
            for index, ritaglio in enumerate(images):
                # cv.imshow(f"Face {index+1}", ritaglio)
                saved = cv.imwrite(str(output_dir / f"face_{index+1}.jpg"), ritaglio)
                if saved is False:
                    print(f"Error while saving face_{index+1}.jpg")
                    raise SystemExit(1)

            # cv.waitKey(0)
            # cv.destroyAllWindows()
            saved = cv.imwrite(str(output_dir / "yunet_result.jpg"), annotated_image)
            if saved is False:
                print("Error while saving yunet_result.jpg")
                raise SystemExit(1)

else:
    print(f"Cannot read image: {path_image}")
    raise SystemExit(1)
