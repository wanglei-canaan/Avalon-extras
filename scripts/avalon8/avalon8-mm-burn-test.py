#!/usr/bin/env python2
# coding: utf-8

#  bridge format: length[1] + transId[1] + sesId[1] + req[1] + data[60]
#  length: 4 + len(data)
#  transId: 0
#  sesId: 0
#  req:
#        a0:RESET
#        a1:INIT
#        a2:DEINIT
#        a3:WRITE
#        a4:READ
#        a5:XFER
#        a6:XFER
#  data: the actual payload
#        clockRate[4] + reserved[4] + payload[52] when init
#
#        xparam[4] + payload[56] when write
#            xparam: txSz[1]+rxSz[1]+options[1]+slaveAddr[1]
#
#        payload[60] when read
#


from optparse import OptionParser
import binascii
import usb.core
import usb.util
import sys
import time
import os

auc_vid = 0x29f1
auc_pid = 0x33f2
TYPE_DETECT = "10"
DATA_OFFSET = 6
parser = OptionParser(version="%prog ver: 20180726")
# TODO: Add voltage control
#       Add miner support
#       Add frequency support
(options, args) = parser.parse_args()
parser.print_version()

def CRC16(message):
    # CRC-16-CITT poly, the CRC sheme used by ymodem protocol
    poly = 0x1021
    # 16bit operation register, initialized to zeros
    reg = 0x0000
    # pad the end of the message with the size of the poly
    message += '\x00\x00'
    # for each bit in the message
    for byte in message:
        mask = 0x80
        while(mask > 0):
            # left shift by one
            reg <<= 1
            # input the next bit from the message into the right hand side
            # of the op reg
            if ord(byte) & mask:
                reg += 1
            mask >>= 1
            # if a one popped out the left of the reg, xor reg w/poly
            if reg > 0xffff:
                # eliminate any one that popped out the left
                reg &= 0xffff
            # xor with the poly, this is the remainder
                reg ^= poly
    return reg

def enum_usbdev(vendor_id, product_id):
    # Find device
    usbdev = usb.core.find(idVendor=vendor_id, idProduct=product_id)

    if not usbdev:
        return None, None, None

    try:
        # usbdev[iConfiguration][(bInterfaceNumber,bAlternateSetting)]
        for endp in usbdev[0][(1, 0)]:
            if endp.bEndpointAddress & 0x80:
                endpin = endp.bEndpointAddress
            else:
                endpout = endp.bEndpointAddress

    except usb.core.USBError as e:
        sys.exit("Could not set configuration: %s" % str(e))

    return usbdev, endpin, endpout

# addr : iic slaveaddr
# req : see bridge format
# data: 40 bytes payload
def auc_req(usbdev, endpin, endpout, addr, req, data):
    req = req.rjust(2, '0')

    if req == 'a1':
        data = data.ljust(120, '0')
        datalen = 12
        txdat = hex(datalen)[2:].rjust(2, '0') + "0000" + req + data
        usbdev.write(endpout, txdat.decode("hex"))

    if req == 'a5':
            datalen = 8 + (len(data) / 2)
            data = data.ljust(112, '0')
            txdat = hex(datalen)[2:].rjust(2, '0') + "0000" + \
                "a5" + "280000" + addr.rjust(2, '0') + data
            usbdev.write(endpout, txdat.decode("hex"))
            usbdev.read(endpin, 64)

            datalen = 8
            txdat = hex(datalen)[2:].rjust(
                2, '0') + "0000" + "a5" + "002800" + \
                addr.rjust(2, '0') + "0".ljust(112, '0')
            usbdev.write(endpout, txdat.decode("hex"))

def auc_read(usbdev, endpin):
    ret = usbdev.read(endpin, 64)
    if ret[0] > 4:
        return ret[4:ret[0]]
    else:
        return None

def auc_xfer(usbdev, endpin, endpout, addr, req, data):
    auc_req(usbdev, endpin, endpout, addr, req, data)
    return auc_read(usbdev, endpin)

def mm_package(cmd_type, idx="01", cnt="01", module_id=None, pdata='0'):
    if module_id is None:
        data = pdata.ljust(64, '0')
    else:
        data = pdata.ljust(60, '0') + module_id.rjust(4, '0')

    crc = CRC16(data.decode("hex"))

    return "434e" + cmd_type + "00" + idx + \
        cnt + data + hex(crc)[2:].rjust(4, '0')

def run_detect(usbdev, endpin, endpout, cmd):
    res_s = auc_xfer(usbdev, endpin, endpout, "00", "a5", cmd)
    if not res_s:
        return None
    else:
        dna = res_s[DATA_OFFSET+0:DATA_OFFSET+8]
        return list(dna)

def show_error():
    print("\n\n")
    print("\033[1;31m--------------------------------------------------------------------------------------\033[0m")
    print("\033[1;31m--------------------------------------------------------------------------------------\033[0m")
    print("\033[1;31m+++++  +++++  +++++    +++++    +++++\033[0m")
    print("\033[1;31m+      +   +  +   +   +     +   +   +\033[0m")
    print("\033[1;31m+++++  +++++  +++++  +       +  +++++\033[0m")
    print("\033[1;31m+      +++    +++     +     +   +++  \033[0m")
    print("\033[1;31m+++++  +  ++  +  ++    +++++    +  ++\033[0m")
    print("\033[1;31m--------------------------------------------------------------------------------------\033[0m")
    print("\033[1;31m--------------------------------------------------------------------------------------\033[0m")
    print("\n\n")

def show_ok(mm_type):
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")
    print("\n")
    print("\033[1;32m%s烧写完成\033[0m" % mm_type)
    print("\n")
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")

def burn_mm(mm_type):
    if (mm_type == 'MM841'):
        ret = os.system("make -C /home/factory/Avalon-extras/scripts/factory isedir=/home/Xilinx/14.6/ISE_DS reflash MM_PLATFORM=MM841")
    elif (mm_type == 'MM851'):
        ret = os.system("make -C /home/factory/Avalon-extras/scripts/factory isedir=/home/Xilinx/14.6/ISE_DS reflash MM_PLATFORM=MM851")
    else:
        print("MM type: %s" % mm_type)
        ret = 1

    if (ret != 0):
        show_error()
        return 0
    else:
        show_ok(mm_type)
        time.sleep(10)
        return 1

def test_mm(usbdev, endpin, endpout, mm_type):
    global MM_DNA

    tmp = run_detect(usbdev, endpin, endpout, mm_package(TYPE_DETECT))
    if tmp is None:
        print("Something is wrong or modular id not correct")
        return 0

    dna = '{:x}'.format(tmp[0]) + \
            '{:x}'.format(tmp[1]) + \
            '{:x}'.format(tmp[2]) + \
            '{:x}'.format(tmp[3]) + \
            '{:x}'.format(tmp[4]) + \
            '{:x}'.format(tmp[5]) + \
            '{:x}'.format(tmp[6]) + \
            '{:x}'.format(tmp[7])

    MM_DNA = dna.zfill(16)
    print("%s DNA: %s" % (mm_type, MM_DNA))
    return 1

if __name__ == '__main__':
    mm_type = sys.argv[1]

    # Find AUC
    usbdev, endpin, endpout = enum_usbdev(auc_vid, auc_pid)
    try:
        if usbdev:
            ret = auc_xfer(usbdev, endpin, endpout, "00", "a1", "801A0600")
            if ret:
                print "AUC ver: " + ''.join([chr(x) for x in ret])
            else:
                print "AUC ver: null"
                sys.exit(1)

        if usbdev is None:
            print "No Avalon USB Converter or compatible device can be found!"
            sys.exit(1)
    except:
        sys.exit(1)

    # MM burn and test
    while (True):
        if (burn_mm(mm_type) == 1):
            while (True):
                print("\033[1;31m请等待黄灯亮后再进行测试! \033[0m")
                space_key = raw_input("\033[1;33m请输入空格键并回车进行MM测试: \033[0m")
                if (space_key.isspace()):
                    ret = test_mm(usbdev, endpin, endpout, mm_type)
                    if (ret):
                        print("\033[1;32m%s\033[0m" % (mm_type + " test pass"))
                    else:
                        show_error()

                while (True):
                    enter = raw_input("\033[1;33m请按回车键继续进行MM烧写和测试: \033[0m")
                    if (len(enter) == 0):
                        break
                break
        else:
            while (True):
                zero = raw_input("\033[1;33m请输入0键并回车继续测试: \033[0m")
                if (zero == '0'):
                    break
