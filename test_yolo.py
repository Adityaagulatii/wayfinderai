"""
Quick YOLO-World shelf test.
Usage:
    python test_yolo.py --image path/to/aisle.jpg --product chips
    python test_yolo.py --camera --product chips
"""
import sys, cv2, argparse
import numpy as np
from ultralytics import YOLO

def test(image_path: str, product: str):
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Could not load image: {image_path}")
        return

    h, w = frame.shape[:2]
    print(f"\nImage: {image_path}  ({w}x{h})")
    print(f"Looking for: '{product}'\n")

    model = YOLO("yolov8s-worldv2.pt")
    model.set_classes([product.lower()])

    results = model(frame, conf=0.20, verbose=False)
    boxes   = results[0].boxes

    if not boxes or len(boxes) == 0:
        print("YOLO: nothing detected above threshold.")
        print("Tips: try a clearer photo, better lighting, or a different product name.")
    else:
        print(f"YOLO: {len(boxes)} detection(s)\n")
        detections = sorted(boxes, key=lambda b: float(b.conf[0]), reverse=True)

        for i, box in enumerate(detections):
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

            side  = "left side"   if cx < w * 0.33 else ("right side"  if cx > w * 0.66 else "center")
            shelf = "top shelf"   if cy < h * 0.33 else ("bottom shelf" if cy > h * 0.66 else "middle shelf")

            print(f"  [{i+1}] conf={conf:.2f}  |  {shelf}, {side}")
            print(f"       box: ({x1},{y1}) → ({x2},{y2})")

            # Draw box
            color = (0, int(255 * conf), 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            label = f"{product} {conf:.0%}"
            cv2.putText(frame, label, (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            # Position tag
            pos_label = f"{shelf}, {side}"
            cv2.putText(frame, pos_label, (x1, y2 + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

        # Best result spoken summary
        best = detections[0]
        x1, y1, x2, y2 = map(int, best.xyxy[0])
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        side  = "left side"   if cx < w * 0.33 else ("right side"  if cx > w * 0.66 else "center")
        shelf = "top shelf"   if cy < h * 0.33 else ("bottom shelf" if cy > h * 0.66 else "middle shelf")
        print(f"\nResult: {product} found — {shelf}, {side}  (conf={float(best.conf[0]):.0%})")

    # Show annotated image
    cv2.imshow(f"YOLO — {product}", frame)
    print("\nPress any key to close.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def live(product: str):
    print(f"\nLive camera — looking for: '{product}'")
    print("Press Q to quit.\n")

    # YOLO-World works better with multiple descriptive synonyms
    SYNONYMS = {
        "chips":    ["potato chips bag", "snack chips", "chip bag", "lays chips", "crisp bag"],
        "milk":     ["milk carton", "milk jug", "dairy milk bottle"],
        "eggs":     ["egg carton", "eggs box"],
        "bread":    ["bread loaf", "bread bag"],
        "water":    ["water bottle", "plastic water bottle"],
        "soda":     ["soda can", "cola can", "soft drink can"],
        "pasta":    ["pasta box", "spaghetti box", "noodles"],
        "rice":     ["rice bag", "rice box"],
        "cereal":   ["cereal box", "breakfast cereal"],
        "coffee":   ["coffee bag", "coffee can", "coffee box"],
    }
    classes = SYNONYMS.get(product.lower(), [product.lower(), f"{product} bag", f"{product} box", f"packaged {product}"])
    print(f"  Searching with classes: {classes}")

    model = YOLO("yolov8s-worldv2.pt")
    model.set_classes(classes)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        print("Cannot open camera!"); return

    last_boxes = []
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret: break
        h, w = frame.shape[:2]
        frame_count += 1

        # Run YOLO every 3 frames on half-resolution
        if frame_count % 3 == 0:
            small = cv2.resize(frame, (320, 240))
            results = model(small, conf=0.10, verbose=False, imgsz=320)
            raw = results[0].boxes
            # Scale boxes back up to full resolution
            last_boxes = []
            if raw and len(raw) > 0:
                for box in raw:
                    x1, y1, x2, y2 = box.xyxy[0]
                    cls_name = classes[int(box.cls[0])] if int(box.cls[0]) < len(classes) else product
                    last_boxes.append({
                        "xyxy": (int(x1*2), int(y1*2), int(x2*2), int(y2*2)),
                        "conf": float(box.conf[0]),
                        "cls":  cls_name,
                    })

        # Draw last known boxes on every frame
        if last_boxes:
            best = max(last_boxes, key=lambda b: b["conf"])
            x1, y1, x2, y2 = best["xyxy"]
            conf = best["conf"]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            side  = "left"   if cx < w * 0.33 else ("right"  if cx > w * 0.66 else "center")
            shelf = "top"    if cy < h * 0.33 else ("bottom" if cy > h * 0.66 else "middle")

            color = (0, int(255 * conf), 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            cls_name = best.get("cls", product)
            cv2.putText(frame, f"{cls_name} {conf:.0%}", (x1, max(y1-10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(frame, f"{shelf} shelf, {side}", (x1, y2 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)
            print(f"\r  FOUND: {cls_name} {conf:.0%} | {shelf} shelf, {side}        ", end="")
        else:
            cv2.putText(frame, f"Looking for: {product}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 140, 255), 2)
            print(f"\r  searching...                        ", end="")

        cv2.imshow(f"YOLO Live — {product}", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image",   help="Path to aisle photo")
    parser.add_argument("--camera",  action="store_true", help="Use live webcam")
    parser.add_argument("--product", required=True, help="Product to find, e.g. chips")
    args = parser.parse_args()

    if args.camera:
        live(args.product)
    elif args.image:
        test(args.image, args.product)
    else:
        print("Provide --image or --camera")
