#!/usr/bin/env python
# coding: Latin-1

'''
Implements a udpServer to connect to JoystickRC4DiddyBorg app (see www.pikoder.com)

Version: 1.0
Date:    20220731

Copyright July 2022 Gregor Schlechtriem
Released under MIT license
'''

# Load library functions we want
import time
import os
import sys
import socket
import struct

# Load library for ThunderBorg
import ThunderBorg3

# Settings for the joystick
axisUpDown = 1                          # Joystick axis to read for up / down position
axisUpDownInverted = False              # Set this to True if up and down appear to be swapped
axisLeftRight = 2                       # Joystick axis to read for left / right position
axisLeftRightInverted = False           # Set this to True if left and right appear to be swapped
buttonSlow = 8                          # Joystick button number for driving slowly whilst held (L2)
slowFactor = 0.5                        # Speed to slow to when the drive slowly button is held, e.g. 0.5 would be half speed
buttonFastTurn = 9                      # Joystick button number for turning fast (R2)
interval = 0.00                         # Time between updates in seconds, smaller responds faster but uses more processor time

# Power settings
voltageIn = 12.0                        # Total battery voltage to the ThunderBorg
voltageOut = 12.0 * 0.95                # Maximum motor voltage, we limit it to 95% to allow the RPi to get uninterrupted power

# Setting for switch function
switchOnMin = 1750                      # Minimum pwm signal to indicate switch is on
buttonFastTurn = 3                      # fast turn assigned assigned to channel 3
buttonSlow = 4                          # slow move assigned to channel 4

# functions
def buttonPushed(channelNumber):
    if ppmFrame[channelNumber-1] > switchOnMin:
        return True
    return False    

# Re-direct our output to standard error, we need to ignore standard out to hide some nasty print statements from pygame
sys.stdout = sys.stderr

# Setup the ThunderBorg
TB = ThunderBorg3.ThunderBorg()
#TB.i2cAddress = 0x15                  # Uncomment and change the value if you have changed the board address
TB.Init()
if not TB.foundChip:
    boards = ThunderBorg.ScanForThunderBorg()
    if len(boards) == 0:
        print ("No ThunderBorg found, check you are attached :")
    else:
        print ("No ThunderBorg at address %02X, but we did find boards:" % (TB.i2cAddress))
        for board in boards:
            print ("    %02X (%d)" % (board, board))
        print ("If you need to change the I²C address change the setup line so it is correct, e.g.")
        print ("TB.i2cAddress = 0x%02X" % (boards[0]))
    sys.exit()

# Ensure the communications failsafe has been enabled!
failsafe = False
for i in range(5):
    TB.SetCommsFailsafe(True)
    failsafe = TB.GetCommsFailsafe()
    if failsafe:
        break
    if not failsafe:
        print ("Board %02X failed to report in failsafe mode!' % (TB.i2cAddress)")
        sys.exit()

# Setup the power limits
if voltageOut > voltageIn:
    maxPower = 1.0
else:
    maxPower = voltageOut / float(voltageIn)

# Setup TB
TB.MotorsOff()
TB.SetLedShowBattery(False)
TB.SetLeds(0,0,1)
os.environ["SDL_VIDEODRIVER"] = "dummy" # Removes the need to have a GUI window
TB.SetLedShowBattery(True)
ledBatteryMode = True

#setup udpSocket
host = ''
rx_port = 12001
tx_port = 12000
bufsize = 1024  # 1 kByte
UDPSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) # UDP
UDPSock.bind((host,rx_port))


try:
    print ("Real time command interface ready ... (press CTRL+C to abort)")
    driveLeft = 0.0
    driveRight = 0.0
    running = True
    hadEvent = False
    upDown = 0.0
    leftRight = 0.0
    # Loop indefinitely
    while running:
        # Get the latest events from the system
        hadEvent = False
        (data, addr) = UDPSock.recvfrom(bufsize)
        # print ('received %s bytes from %s:%d' % (len(data), addr[0], addr[1]))
        # print (data)
        # Handle each event individually
        if data == b'?':
            UDPSock.sendto(b"T=Diddyborg", (addr[0], tx_port))
            hadEvent = False
        else:
            if data == b'0':    
                UDPSock.sendto(b"1.0", (addr[0], tx_port))
                hadEvent = False
            else:
                hadEvent = True
        # Process commands 
        if hadEvent:

            # unpack struct
            ppmFrame = struct.unpack('xxHHHHHHHH', data)

            # Read axis positions (-1 to +1)
            if axisLeftRightInverted:
                leftRight = (-float(ppmFrame[0]) + 1500) / 500
            else:
                leftRight = (float(ppmFrame[0]) - 1500) / 500               
            if axisUpDownInverted:
                upDown = (-float(ppmFrame[1]) + 1500) / 500
            else:
                upDown = (float(ppmFrame[1]) - 1500) / 500

            # Apply steering speeds
            if not buttonPushed(buttonFastTurn):
                leftRight *= 0.5
            
            # Determine the drive power levels
            driveLeft = -upDown
            driveRight = -upDown
            if leftRight < -0.05:
                # Turning left
                driveLeft *= 1.0 + (2.0 * leftRight)
            elif leftRight > 0.05:
                # Turning right
                driveRight *= 1.0 - (2.0 * leftRight)
            
            # Check for button presses
            if buttonPushed(buttonSlow):
                driveLeft *= slowFactor
                driveRight *= slowFactor
            
            # Set the motors to the new speeds
            TB.SetMotor1(driveLeft  * maxPower)
            TB.SetMotor2(driveRight * maxPower)
            
            # Change LEDs to purple to show motor faults
            if TB.GetDriveFault1() or TB.GetDriveFault2():
                if ledBatteryMode:
                    TB.SetLedShowBattery(False)
                    TB.SetLeds(1,0,1)
                    ledBatteryMode = False
            else:
                if not ledBatteryMode:
                    TB.SetLedShowBattery(True)
                    ledBatteryMode = True
except KeyboardInterrupt:
    # CTRL+C exit
    print ("\nUser shutdown")
finally:
    # Disable all drives
    TB.MotorsOff()
    TB.SetCommsFailsafe(False)
    TB.SetLedShowBattery(False)
    TB.SetLeds(0,0,0)
    print
