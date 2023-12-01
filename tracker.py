from itertools import filterfalse
from utils import getOrientation
from os import path, mkdir, sep
from tqdm import tqdm
import numpy as np
import cv2 as cv
import argparse
import json

def parser_args():
    parser = argparse.ArgumentParser(
        description='Tracks mice.'
    )

    parser.add_argument(
        'video', type=str,
        help='Path to the video file to be processed.'
    )

    parser.add_argument(
        'frame_rate', type=int,
        help='Frame rate of the video file to be processed.'
    )

    parser.add_argument(
        '--draw-rois', action='store_true',
        help='User inputed Regions of interest.'
    )

    parser.add_argument(
        '--draw-axis', action='store_true',
        help='Draw both PCA axis.'
    )

    parser.add_argument(
        '--save-video', action='store_true',
        help='Create a video file with the analysis result.'
    )

    parser.add_argument(
        '--color-mask', action='store_true',
        help='Draw a colored mask over the detection.'
    )

    parser.add_argument(
        '--log-position', action='store_true',
        help='Logs the position of the center of mass to file.'
    )

    parser.add_argument(
        '--log-stats', action='store_true',
        help='Logs the statistics of the mice moviment.'
    )

    parser.add_argument(
        '--log-speed', action='store_true',
        help='Logs the speed of the center of mass to file.'
    )

    return parser.parse_args()

if __name__ == '__main__':
    args = parser_args()
    
    cap = cv.VideoCapture(args.video)
    frameWidth = int(cap.get(3)) 
    frameHeight = int(cap.get(4))

    frame_rate = args.frame_rate

    if (not cap.isOpened()):
        print('Error opening video stream')
        exit()

    # First frame as the background image
    ret, bg_img = cap.read()
        
    if(not ret):
        print('Error readning video stream')
        exit()

    # Selection of the ROIs
    if(args.draw_rois): 
        ret, frame = cap.read()

        if(not ret):
            print('Error readning video stream')
            exit()

        roi_win = 'ROI Selection'
        cv.namedWindow(roi_win, cv.WINDOW_KEEPRATIO)
        cv.resizeWindow(roi_win, 1438, 896)

        rois = cv.selectROIs(roi_win, frame, False)
        cv.destroyWindow(roi_win)

        rois = { f'Area {idx}': roi for idx, roi in zip(range(len(rois)), rois)}

        print(rois)
        
    else:
        # Manual definition of the ROIs
        rois = json.load(open(f"{args.video.split('.')[0]}.json", 'r'))

    if(args.save_video):
        resultFileName = f"{args.video.split(sep)[-1].split('.')[0]}_result.avi"

        outWriter = cv.VideoWriter(
            resultFileName,
            cv.VideoWriter_fourcc('M', 'J', 'P', 'G'),
            frame_rate, (frameWidth, frameHeight)
        )
    
    # Check whether it's necessary to create a logs directory
    if(args.log_stats or args.log_position or args.log_speed):
        if(not path.exists('logs/')):
            mkdir('logs/')

    # Create file for stats loging
    statsLogFile = f"{args.video.split('/')[-1].split('.')[0]}_stats.json"
    if(args.log_stats):
        with open(statsLogFile, 'w') as log_file:
            log_file.write('')

        # Create file for position loging
    posLogFile = f"{args.video.split('/')[-1].split('.')[0]}_pos.csv"
    if(args.log_position):        
        with open(posLogFile, 'w') as log_file:
            log_file.write('region,x,y\n')

    # Create file for speed loging 
    speedLogFile = f"{args.video.split('/')[-1].split('.')[0]}_speed.csv"
    if(args.log_speed):        
        with open(speedLogFile, 'w') as log_file:
            log_file.write('time,speed\n')

    result_win = 'Tracker'
    cv.namedWindow(result_win, cv.WINDOW_KEEPRATIO)
    cv.resizeWindow(result_win, 1245, 725)
    cv.moveWindow(result_win, 290, 79)

    probe_win = 'Probe'
    cv.namedWindow(probe_win, cv.WINDOW_KEEPRATIO)
    cv.resizeWindow(probe_win, 855, 516)

    # Counter for each selected region    
    rois_counter = { f'Area {idx}': 0 for idx in range(len(rois)) }

    entires_counter = { f'Area {idx}': 0 for idx in range(len(rois)) }

    # Color range of the mice un the subtracted image
    lower_white = np.array([140, 140, 140])
    upper_white = np.array([250, 250, 250])

    # Varibles fo tracking the mice's position
    previous_pos = (0, 0)
    current_pos = (0, 0)

    previous_zone = 'center'
    current_zone = 'center'

    frameIndex = 0
    traveledDistance = 0

    num_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
    pbar = tqdm(total=num_frames)

    while(cap.isOpened()):
        ret, frame = cap.read()
        pbar.update(1)

        if(not ret):
            pbar.close()
            exit()

        sub_frame = cv.absdiff(frame, bg_img)
        
        filtered_frame = cv.inRange(sub_frame, lower_white, upper_white)

        cv.imshow(probe_win, filtered_frame)
        
        # Kernel for morphological operation opening
        kernel3 = cv.getStructuringElement(
            cv.MORPH_ELLIPSE,
            (3, 3),
            (-1, -1)
        )

        kernel20 = cv.getStructuringElement(
            cv.MORPH_ELLIPSE,
            (20, 20),
            (-1, -1)
        )

        # Morphological opening
        mask = cv.dilate(cv.erode(filtered_frame, kernel3), kernel20)
        
        # Find all the contours in the mask
        returns = cv.findContours(mask, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)
        
        # Check what findContours returned
        contours = []
        if(len(returns) == 3):
            contours = returns[1]
        else:
            contours = returns[0]
        
        if(len(contours) != 0):
            # find the biggest countour by the area
            contour = max(contours, key = cv.contourArea)
            cv.drawContours(frame, [contour], 0, (255, 0, 255), 2)

            # Find the orientation of each shape
            current_pos, _ = getOrientation(contour, frame, args.draw_axis)


        speed = np.sqrt(
            (previous_pos[0] - current_pos[0])**2 + 
            (previous_pos[1] - current_pos[1])**2
        )

        traveledDistance += speed
        previous_pos = current_pos


        if(args.log_speed):
            if(current_pos[0] > 50 and current_pos[1] > 50):        
                with open(speedLogFile, 'a') as log_file:
                    log_file.write(f'{frameIndex * (1/float(frame_rate)):.3f},{speed:.3f}\n')
        
        # Draw ROI and check if the mice is inside 
        if(rois is not None):                   

            for label, roi in rois.items():
                x, y, w, h = roi
                
                if(any(current_pos)):
                    if(x <= current_pos[0] <= x+w and y <= current_pos[1] <= y+h):
                        # Save position to file
                        if(args.log_position):
                            with open(posLogFile, 'a') as log_file:
                                # Changes the coordinates' center to the bottom left for later plotting
                                log_file.write(f'{label},{current_pos[0]},{frameHeight - current_pos[1]}\n')

                        cv.rectangle(
                            frame, (x, y),
                            (x + w, y + h),
                            (128, 244, 66), 2
                        )

                        rois_counter[label] += 1
                        
                        # Conting the entires in each arm of the maze
                        current_zone = label
                        if(previous_zone == 'center' and current_zone != 'center' and speed > 1):
                            entires_counter[label] += 1

                        previous_zone = label

                        cv.putText(
                            frame, f'{label}: {rois_counter[label]}', (x, y - 5),
                            cv.FONT_HERSHEY_COMPLEX,
                            0.5, (255, 255, 255)
                        )

                    else:
                        cv.rectangle(
                            frame, (x, y),
                            (x + w, y + h),
                            (80, 80, 80), 2
                        )

                        cv.putText(
                            frame, f'{label}: {rois_counter[label]}', (x, y - 5),
                            cv.FONT_HERSHEY_COMPLEX,
                            0.5, (255, 255, 255)
                        )
                else:
                    cv.rectangle(
                        frame, (x, y),
                        (x + w, y + h),
                        (80, 80, 80), 2
                    )

                    cv.putText(
                        frame, f'{label}: {rois_counter[label]}', (x, y - 5),
                        cv.FONT_HERSHEY_COMPLEX,
                        0.5, (255, 255, 255)
                    )

                # Show the entires counters 
                cv.putText(
                    frame,
                    'Entries',
                    (40, 40), cv.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), lineType=cv.LINE_AA
                )
                for idx, entry in enumerate(entires_counter):
                    cv.putText(
                        frame,
                        f'{entry}: {entires_counter[entry]}',
                        (40, 40 * idx + 80), cv.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), lineType=cv.LINE_AA
                    )

            if(args.log_stats):
                # Saves the rois counter to file
                with open(statsLogFile, 'w') as log_file:

                    stats = {
                        'traveled_distance': traveledDistance,
                        'time_in_regions': {region: rois_counter[region] * (1/float(frame_rate)) for region in rois_counter},
                        'entries': {region: entires_counter[region] for region in entires_counter}
                    }

                    json.dump(stats, log_file, indent=4)
                    
                    # log_file.write(f'\tCounters for the regions considering {frame_rate}fps video\n')
                    # log_file.write(f'\n- Traveled distance: {traveledDistance:.3f} pixels\n')

                    # log_file.write('\n- Time in spent in each region:\n')
                    # for region in rois_counter:
                    #     log_file.write(f'\tRegion {region}:\t{rois_counter[region]} frames')
                    #     log_file.write(f', {rois_counter[region] * (1/float(frame_rate)):.3f}s\n')


                    # log_file.write('\n- Entries in each region:\n')
                    # for region in entires_counter:
                    #     log_file.write(f'\t{region}:\t{entires_counter[region]} entires\n')
                    
        if(args.color_mask):
            # Change the color of the mask
            colored_mask = cv.cvtColor(mask, cv.COLOR_GRAY2BGR)
            colored_mask[np.where((colored_mask == [255, 255, 255]).all(axis = 2))] = [222, 70, 222]

            # Apply the mask
            frame = cv.add(frame, colored_mask)

        cv.imshow(result_win, frame)
        frameIndex += 1

        if(args.save_video):
            outWriter.write(frame)

        key = cv.waitKey(10)
        if(key == 27 or key == 113):
            cv.destroyAllWindows()
            cap.release()
            pbar.close()

            if(args.save_video):
                outWriter.release()

            exit()

        if(key == 32):
            while True:

                cv.imshow(result_win, frame)
                
                key2 = cv.waitKey(5)
                if(key2 == 32):
                    break
                elif(key2 == 27 or key == 113):
                    cv.destroyAllWindows()
                    cap.release()
                    pbar.close()

                    if(args.save_video):
                        outWriter.release()

                    exit()
