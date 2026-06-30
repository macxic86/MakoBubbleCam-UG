# MakoBubbleCam-UG
Camera-control and image-acquisition software for bubble–mineral interaction studies using Allied Vision Mako cameras.
# MakoBubbleCam-UG

Camera-control and image-acquisition software for bubble–mineral interaction studies using Allied Vision Mako cameras.

## Description

MakoBubbleCam-UG is a camera-control and image-acquisition software developed at Universidad de Guanajuato for bubble–mineral interaction experiments. The software was designed to operate Allied Vision Mako cameras during synchronized force–image measurements.

The software allows the user to visualize the bubble in real time, select the recording frame rate, superimpose a horizontal reference line, calibrate the image scale, and estimate the bubble diameter before or during an experiment.

The tool was developed as part of an integrated force–image methodology for studying bubble adhesion, retraction, and detachment on mineral surfaces under flotation-relevant conditions.

## Main features


- Camera control for Allied Vision Mako U-029B USB3 Vision cameras.
- Capture profiles with predefined resolution, frame rate, and exposure time.
- Real-time grayscale image visualization.
- Horizontal reference lines for bubble–surface alignment.
- Pixel-to-micrometer calibration.
- Bubble diameter estimation using an interactive circle tool.
- Image and video acquisition during bubble–mineral interaction experiments.
- Automatic frame saving as BMP images.
- Timestamp export in CSV format for synchronization with force measurements.
- Automatic preview video generation after recording.
- Support for transmitted-light shadow imaging.

## Running the software on Windows

1. Install Python 3.
2. Install Allied Vision Vimba X and verify that the Mako camera is detected.
3. Install the Python dependencies:

```bash
pip install -r requirements.txt

4. Run the software using:

run_mako_bubble_cam.bat

## Camera and acquisition configuration

The software was developed for a Mako U-029B USB3 Vision camera from Allied Vision. The optical system was configured in transmitted-light mode, with the light source placed opposite to the camera so that the bubble appeared as a dark silhouette.

## Acquisition profiles

The software includes predefined acquisition profiles for the Mako U-029B camera:

| Profile | Resolution | Nominal frame rate | Exposure time |
|---|---:|---:|---:|
| Velocity 1 | 640 × 480 px | 30 fps | 10000 µs |
| Velocity 2 | 640 × 480 px | 100 fps | 3000 µs |
| Velocity 3 | 640 × 480 px | 200 fps | 1000 µs |
| Wide ROI | 480 × 360 px | 400 fps | 500 µs |

The actual frame rate depends on camera configuration, exposure time, computer performance, and data transfer conditions.

## Requirements

This software requires:

- Python 3.x
- OpenCV
- NumPy
- VmbPy
- Allied Vision Vimba X SDK
- Allied Vision Mako U-029B USB3 Vision camera

The camera must be recognized by Vimba X before running the software.

## Research context

This software was developed to support synchronized force–image experiments in which a bubble is displaced toward or away from a mineral surface mounted on a piezoelectric bimorph force sensor.

## Related software

Dynamic contact angle and triple-phase contact line analysis can be performed using the companion software:

BubbleLab-ContactAngle

## Suggested citation

If you use this software in academic work, please cite the corresponding software release and the related publication.

## Authors

Mario Alberto Corona Arroyo  
Universidad de Guanajuato

## License

License information will be added in a future release.
