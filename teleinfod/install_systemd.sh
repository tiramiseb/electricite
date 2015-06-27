#!/bin/sh
#
# Install the teleinformation daemon with systemctl

mkdir -p /usr/local/bin
mkdir -p /usr/local/etc
cp teleinfod.py /usr/local/bin/
cp teleinfod.conf /usr/local/etc/
cp teleinfod.service /etc/systemd/system/

systemctl enable teleinfod.service

echo "========================================================================="
echo "Please configure /usr/local/etc/teleinfod.conf."
echo "Note that you need *NOT TO* activate the DAEMON option with the provided"
echo "systemctl service file."
echo ""
echo "After configuring /usr/local/etc/teleinfod.conf, use the following"
echo "command to start the teleinformation daemon:"
echo "    systemctl start teleinfod.service"
echo ""
echo "DO NOT REBOOT before configuration: the service will be started"
echo "on the next reboot!"
echo ""
