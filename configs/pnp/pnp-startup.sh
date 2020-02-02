#!/bin/bash

# servo power
halcmd setp nyx.0.out-00 1

# wait until sscii module is ready
for a in `seq 1 10` ; do
	if [ X`halcmd 2>/dev/null getp nyx.0.ready` == "XTRUE" ] ; then
		break
	fi
	sleep 0.5
done

# home all except X which is full-closed
for a in 1 2 3 4 ; do
	# check if the amp doesn't have an alarm, then home its axis
        if [ X`halcmd getp nyx.0.servo-0$a.alarm` == "XFALSE" ]
        then
                halcmd setp halui.joint.$a.set-homed 1
        fi
done
sleep 1
for a in 1 2 3 4 ; do
        halcmd setp halui.joint.$a.set-homed 0
done

# vision

while [ X`halcmd 2>/dev/null getp cv.debug` != "X0" ] ; do
	sleep 1
done

halcmd -f pnp-cv.hal

echo pnp-startup.sh ready
