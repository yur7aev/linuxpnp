#!/bin/bash

v4l2-ctl -d0 -c white_balance_temperature_auto=0
echo 1
v4l2-ctl -d0 -c white_balance_temperature=4200
echo 2
v4l2-ctl -d0 -c exposure_auto=1
echo 3
v4l2-ctl -d0 -c exposure_absolute=18
echo 4
v4l2-ctl -d2 -c white_balance_temperature_auto=0
echo 5
v4l2-ctl -d2 -c white_balance_temperature=6500
echo 6


#                     brightness 0x00980900 (int)    : min=-64 max=64 step=1 default=0 value=0
#                       contrast 0x00980901 (int)    : min=0 max=64 step=1 default=32 value=32
#                     saturation 0x00980902 (int)    : min=0 max=128 step=1 default=60 value=60
#                            hue 0x00980903 (int)    : min=-40 max=40 step=1 default=0 value=0
# white_balance_temperature_auto 0x0098090c (bool)   : default=1 value=1
#                          gamma 0x00980910 (int)    : min=72 max=500 step=1 default=100 value=100
#                           gain 0x00980913 (int)    : min=0 max=100 step=1 default=0 value=0
#           power_line_frequency 0x00980918 (menu)   : min=0 max=2 default=1 value=1
#      white_balance_temperature 0x0098091a (int)    : min=2800 max=6500 step=1 default=4600 value=6500 flags=inactive
#                      sharpness 0x0098091b (int)    : min=0 max=6 step=1 default=2 value=2
#         backlight_compensation 0x0098091c (int)    : min=0 max=2 step=1 default=1 value=0
#                  exposure_auto 0x009a0901 (menu)   : min=0 max=3 default=3 value=1
#              exposure_absolute 0x009a0902 (int)    : min=1 max=5000 step=1 default=157 value=18
#         exposure_auto_priority 0x009a0903 (bool)   : default=0 value=0
#
#                     brightness 0x00980900 (int)    : min=0 max=255 step=1 default=128 value=128
#                       contrast 0x00980901 (int)    : min=0 max=127 step=1 default=36 value=36
#                     saturation 0x00980902 (int)    : min=0 max=127 step=1 default=38 value=38
#                            hue 0x00980903 (int)    : min=-15 max=15 step=1 default=0 value=0
# white_balance_temperature_auto 0x0098090c (bool)   : default=1 value=0
#                          gamma 0x00980910 (int)    : min=1 max=5 step=1 default=3 value=5
#           power_line_frequency 0x00980918 (menu)   : min=0 max=2 default=1 value=1
#      white_balance_temperature 0x0098091a (int)    : min=2800 max=6500 step=1 default=6500 value=6500
#                      sharpness 0x0098091b (int)    : min=0 max=4 step=1 default=1 value=1
#         backlight_compensation 0x0098091c (int)    : min=0 max=1 step=1 default=1 value=0
#         exposure_auto_priority 0x009a0903 (bool)   : default=0 value=0
