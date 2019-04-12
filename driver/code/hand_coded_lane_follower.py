import cv2
import numpy as np
import logging
import matplotlib.pyplot as plt
import math
import datetime

_SHOW_IMAGE = True

class HandCodedLaneFollower(object):

    def __init__(self, car = None, debug = False):
        ''' Init camera and wheels'''
        logging.info('Creating a HandCodedLaneFollower...')
        self.car = car
        self.prev_steering_angle = 90

    def follow_lane(self, frame):
        logging.debug('detecting lanes...')
        show_image("orig", frame)
        
        lanes, frame = self.detect_lane(frame)

        logging.debug('steering...')
        final_frame = self.steer(frame, lanes)
        
        return final_frame

    def detect_lane(self, frame):
        canny_image = canny(frame)
        show_image('edges', canny_image)
        
        cropped_canny = region_of_interest(canny_image)
        show_image('edges cropped', cropped_canny)
        
        # detect line segments
        # tuning min_threshold, minLineLength, maxLineGap is a trial and error process by hand
        rho = 1 # precision in pixel, i.e. 1 pixel
        angle = np.pi/180 # degree in radian, i.e. 1 degree
        min_threshold = 10 # minimal of votes
        lines = cv2.HoughLinesP(cropped_canny, rho, angle, min_threshold, np.array([]), minLineLength=15, maxLineGap=4)
        
        if lines is not None:
            for line in lines :
                logging.debug('detected line segments:')
                logging.debug( "%s of length %s" % (line, lenth_of_line_segment( line[0] )))
        if _SHOW_IMAGE:
            line_image = display_lines(frame, lines)
            line_image = cv2.addWeighted(frame, 0.8, line_image, 1, 1)
            show_image("line segments", line_image)  
        
        averaged_lines = average_slope_intercept(frame, lines)
        
        logging.debug('lane lines: %s' % averaged_lines)  # [[[316, 720, 484, 432]], [[1009, 720, 718, 432]]]
        
        line_image = display_lines(frame, averaged_lines)
        combo_image = cv2.addWeighted(frame, 0.8, line_image, 1, 1)
        
        return averaged_lines, combo_image
    
    def steer(self, frame, lanes):
        if lanes is None:
            logging.error('No lane lines detected, nothing to do.')
            return frame
        
        steering_angle, frame = compute_steering_angle(frame, lanes)
        #cv2.
        if abs(self.prev_steering_angle - steering_angle) <= 10:
            self.prev_steering_angle = steering_angle
            if self.car != None:
                self.car.front_wheels.turn(steering_angle)
        else :
            logging.error('ignoring errornous turning decision')
        
        return frame
        
def lenth_of_line_segment( line ):
    x1, y1, x2, y2 = line
    return math.sqrt( (x2-x1)**2 + (y2-y1)**2)
    
def show_image(title, image, show = _SHOW_IMAGE):
    if show :
        cv2.imshow(title, image)

def compute_steering_angle(frame, lanes):
    ''' Find the steeing angle based on lane line coordinate
        We assume that camera is calibrated to point to dead center
    '''
    height, width, _ = frame.shape
    left_line, right_line = lanes
    
    # find end of center line
    x2 = int((left_line[0][2]+right_line[0][2])/2)
    y2 = int((left_line[0][3]+right_line[0][3])/2)
    
    #import pdb; pdb.set_trace()
    # find the steering angle, which is angle between navigation direction to end of center line 
    x_offset = x2 - width/2
    y_offset = height - y2
    
    lines = [[[int(width/2), height, x2, y2]]]        
    line_image = display_lines(frame, lines)
    line_image = cv2.addWeighted(frame, 0.8, line_image, 1, 1)
    show_image("heading", line_image)
            
    angle_to_mid = int(math.atan(x_offset / y_offset) * 180.0 / math.pi) # angle (in degrees) to center vertical line
    steering_angle = angle_to_mid + 90 # this is the steering angle needed by picar front wheel
    
    logging.info('steering angle: %s' % steering_angle)
    return steering_angle, line_image
    
def make_points(image, line):
    height, width, _ = image.shape
    slope, intercept = line
    y1 = height # bottom of the image
    y2 = int(y1 * 1/2)         # make points from middle of the image down
    
    # bound the coordinates within the image
    x1 = max(-width, min(2*width, int((y1 - intercept)/slope)))   
    x2 = max(-width, min(2*width, int((y2 - intercept)/slope)))
    return [[x1, y1, x2, y2]]
 
def average_slope_intercept(image, lines):
    height, width, _ = image.shape
    left_fit    = []
    right_fit   = []
    if lines is None:
        return None
    
    for line in lines:
        import pdb; pdb.set_trace()
        for x1, y1, x2, y2 in line:
            fit = np.polyfit((x1,x2), (y1,y2), 1)
            slope = fit[0]
            intercept = fit[1]
            if slope < 0: # y is reversed in image
                left_fit.append((slope, intercept))
            else:
                right_fit.append((slope, intercept))
    
    # add more weight to longer lines
    #import pdb; pdb.set_trace()
    left_fit_average  = np.average(left_fit, axis=0)
    if len(left_fit) == 0 :
        left_line = [[0, height, 0, int(height / 2)]]
    else:
        left_line = make_points(image, left_fit_average)
        
    right_fit_average = np.average(right_fit, axis=0)
    if len(right_fit) == 0 :
        right_line = [[width, height, width, int(height / 2)]]
    else:
        right_line = make_points(image, right_fit_average)
    
    averaged_lines = [left_line, right_line]
    return averaged_lines
 
def canny(img):
    # filter for blue lane lines
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    show_image("hsv", hsv)
    lower_blue = np.array([90,50,50]) 
    upper_blue = np.array([150,255,255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    show_image("blue mask", mask)
    
    # detect edges
    canny = cv2.Canny(mask, 200, 400)
    
    return canny
 
def display_lines(img,lines):
    line_image = np.zeros_like(img)
    if lines is not None:
        for line in lines:
            for x1, y1, x2, y2 in line:
                cv2.line(line_image,(x1,y1),(x2,y2),(0,255,0),10)
    return line_image
 
def region_of_interest(canny):
    height, width = canny.shape
    mask = np.zeros_like(canny)
 
    # only focus bottom half of the screen 
    polygon = np.array([[
    (0, height * 1/2),
    #(width / 2, height * 1/3),
    (width, height * 1/2),
    (width, height),
    (0, height),
    ]], np.int32)
 
    cv2.fillPoly(mask, polygon, 255)
    show_image("mask", mask)
    masked_image = cv2.bitwise_and(canny, mask)
    return masked_image

def test_photo(file):
    land_follower = HandCodedLaneFollower()
    frame = cv2.imread(file)
    combo_image = land_follower.follow_lane(frame)
    show_image('final', combo_image, True)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
def test_video(video_file):
    land_follower = HandCodedLaneFollower()
    cap = cv2.VideoCapture(video_file+'.avi')
    
    # skip first second of video.
    for i in range(3):
        _, frame = cap.read()
        
    try:
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        datestr = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
        video_overlay = cv2.VideoWriter("%s_overlay_%s.avi" % (video_file,datestr),fourcc, 20.0, (320,240))
        i = 0
        while(cap.isOpened()):
            _, frame = cap.read()
            cv2.imwrite("%s_%03d.png" % (video_file,i), frame)
            
            combo_image = land_follower.follow_lane(frame)
            cv2.imwrite("%s_overlay_%03d.png" % (video_file,i), combo_image)
            video_overlay.write(combo_image)
            
            cv2.imshow("Road with Lane line", combo_image)
            
            i += 1
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        video_overlay.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    #test_video('/home/pi/DeepPiCar/driver/data/car_video_orig_190411_111646/car_video_orig_190411_111646')
    test_photo('/home/pi/DeepPiCar/driver/data/car_video_orig_190411_111646/car_video_orig_190411_111646_045.png')    