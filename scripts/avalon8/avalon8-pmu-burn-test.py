#!/usr/bin/env python2
# coding: utf-8


from __future__ import division
from serial import Serial
import argparse
import binascii
import sys
import time
import math
import subprocess
import save_chip_data

parser = argparse.ArgumentParser(description="Avalon8 PMU test script.")
parser.add_argument("-s", action='store', dest="serial_port", default="/dev/ttyUSB0", help='Serial port')
parser.add_argument("-c", action='store', dest="is_rig", default="0", help='0 Is For Rig Testing, 1 Is For Test Polling')
parser.add_argument("-t", action='store', dest="pmu_type", default="PMU851", help='PMU type')
parser = parser.parse_args()

ser = None
try:
    ser = Serial(parser.serial_port, 115200, 8, timeout=0.2) # 1 second
except Exception as e:
    print str(e)

PMU8_VER = ( '8C' )
PMU8_PG  = { 'pg_good': '0001', 'pg_bad': '0002' }
PMU8_LED = { 'led_close': '0000', 'led_green': '0001', 'led_red': '0002' }
# ntc: check the table(Thick Film Chip NTC Thermistor Devices_CMFA103J3500HANT.pdf)
# v12_l/h(Vin) equation: x * 3.3 / 4095 = (11~14) * 5.62 / 25.62
# PMU841: vcore_l/h(Vout) equation: x * 3.3 / 4095 = (8.49 * (1 +/-2%)) * 20 / 63
# PMU851: vcore_l/h(Vout) equation: x * 3.3 / 4095 = (8.97 * (1 -/+2%)) * 20 / 72.3
PMU841_ADC = { 'ntc_l': 524, 'ntc_h': 9615, 'v12_l':2994, 'v12_h': 3810, 'vcore_l': 3230, 'vcore_h': 3427}
PMU851_ADC = { 'ntc_l': 524, 'ntc_h': 9615, 'v12_l':2994, 'v12_h': 3810, 'vcore_l': 3020, 'vcore_h': 3158}

error_message = {
    'serial_port': 'Connection failed.',
    'ntc_1': 'NTC_1 value error.',
    'ntc_2': 'NTC_2 value error.',
    'v12': 'V12 value error.',
    'vcore_1': 'VCORE1 value error.',
    'vcore_2': 'VCORE2 value error.',
    'pg_1' : 'PG1 value error.',
    'pg_2' : 'PG2 value error.' ,
    'led_1': 'LED1 status error.',
    'led_2': 'LED2 status error.'
}

def CRC16(message):
    #CRC-16-CITT poly, the CRC sheme used by ymodem protocol
    poly = 0x1021
    #16bit operation register, initialized to zeros
    reg = 0x0000
    #pad the end of the message with the size of the poly
    message += '\x00\x00'
    #for each bit in the message
    for byte in message:
        mask = 0x80
        while(mask > 0):
            #left shift by one
            reg<<=1
            #input the next bit from the message into the right hand side of the op reg
            if ord(byte) & mask:
                reg += 1
            mask>>=1
            #if a one popped out the left of the reg, xor reg w/poly
            if reg > 0xffff:
                #eliminate any one that popped out the left
                reg &= 0xffff
                #xor with the poly, this is the remainder
                reg ^= poly
    return reg

def mm_package(cmd_type, idx = "01", cnt = "01", module_id = None, pdata = '0'):
    if module_id == None:
        data = pdata.ljust(64, '0')
    else:
        data = pdata.ljust(60, '0') + module_id.rjust(4, '0')
    crc = CRC16(data.decode("hex"))
    return "434E" + cmd_type + "00" + idx + cnt + data + hex(crc)[2:].rjust(4, '0')

def show_help():
    print("\
h: Help\n\
1: Detect The PMU Version\n\
2: Set	  The PMU Output Voltage\n\
          |-----------------|---------------------|\n\
          |   008088018088  |       8.97V         |\n\
          |-----------------|---------------------|\n\
3: Set    The PMU Led State\n\
          |---------------------------------------|\n\
          |     Setting     |      Led state      |\n\
          |-----------------|---------------------|\n\
          |   000000010000  |   All   Led Off     |\n\
          |-----------------|---------------------|\n\
          |   000101010101  |   Green Led On      |\n\
          |-----------------|---------------------|\n\
          |   000202010202  |   Red   Led On      |\n\
          |-----------------|---------------------|\n\
          |   000404010404  |   Green Led Blink   |\n\
          |-----------------|---------------------|\n\
          |   000808010808  |   Red   Led Blink   |\n\
          |-----------------|---------------------|\n\
4: Get    The PMU State\n\
q: Quit\n")

def detect_version(pmu_type):
    global PMU_ADC
    global PMU_LED
    global PMU_PG
    global PMU_DNA
    global PMU_VER

    input_str = mm_package("10", module_id = None)
    ser.flushInput()
    ser.write(input_str.decode('hex'))
    res = ser.readall()
    if res == "":
        print (error_message['serial_port'])
        return False
    PMU_DNA = binascii.hexlify(res[6:14])
    if res[14:16] == PMU8_VER:
        PMU_VER = res[14:29]
        PMU_LED = PMU8_LED
        PMU_PG  = PMU8_PG
        if (pmu_type == 'PMU841'):
            PMU_ADC = PMU841_ADC
        elif (pmu_type == 'PMU851'):
            PMU_ADC = PMU851_ADC
    else:
        print(res[14:29])
        print("Invalid PMU version")
        return False

    print(pmu_type + " VER:" + PMU_VER)
    print(pmu_type + " DNA:" + PMU_DNA)
    return True

def judge_vol_range(vol):
    if len(vol) != 12:
        return False
    if (vol[0:2] != "00") and (vol[6:8] != "01"):
        return False

    return True

def judge_led_range(led):
    if len(led) != 12:
        return False
    if (led[0:2] != "00") and (led[6:8] != "01"):
        return False

    return True

def set_vol_value(vol_value):
    if judge_vol_range(vol_value) == True:
        input_str = mm_package("22", idx = vol_value[0:2], module_id = None, pdata = vol_value[2:6]);
        ser.flushInput()
        ser.write(input_str.decode('hex'))
        input_str = mm_package("22", idx = vol_value[6:8], module_id = None, pdata = vol_value[8:12]);
        ser.flushInput()
        ser.write(input_str.decode('hex'))
    else:
        print("Bad voltage vaule!")

def set_led_state(led):
    if judge_led_range(led) == True:
        input_str = mm_package("24", idx = led[0:2], module_id = None, pdata = led[2:6]);
        ser.flushInput()
        ser.write(input_str.decode('hex'))
        input_str = mm_package("24", idx = led[6:8], module_id = None, pdata = led[8:12]);
        ser.flushInput()
        ser.write(input_str.decode('hex'))
    else:
        print("Bad led's state vaule!")

def get_result():
    input_str = mm_package("30", module_id = None);
    ser.flushInput()
    ser.write(input_str.decode('hex'))
    res = ser.readall()
    if res == "":
        print("\033[1;31m%s\033[0m" % error_message['serial_port'])
        return False
    a = int(binascii.hexlify(res[6:8]), 16)
    if (a < PMU_ADC['ntc_l']) or (a > PMU_ADC['ntc_h']):
        print("\033[1;31m%s\033[0m" % error_message['ntc_1'])
        return False
    a = int(binascii.hexlify(res[8:10]), 16)
    if (a < PMU_ADC['ntc_l']) or (a > PMU_ADC['ntc_h']):
        print("\033[1;31m%s\033[0m" % error_message['ntc_2'])
        return False
    a = int(binascii.hexlify(res[10:12]), 16)
    if (a < PMU_ADC['v12_l']) or (a > PMU_ADC['v12_h']):
        print("\033[1;31m%s\033[0m" % error_message['v12'])
        return False
    a = int(binascii.hexlify(res[12:14]), 16)
    if (a < PMU_ADC['vcore_l']) or (a > PMU_ADC['vcore_h']):
        print("\033[1;31m%s\033[0m" % error_message['vcore_1'])
        return False
    a = int(binascii.hexlify(res[14:16]), 16)
    if (a < PMU_ADC['vcore_l']) or (a > PMU_ADC['vcore_h']):
        print("\033[1;31m%s\033[0m" % error_message['vcore_2'])
        return False
    a = binascii.hexlify(res[16:18])
    if (a != PMU_PG['pg_good']):
        print("\033[1;31m%s\033[0m" % error_message['pg_1'])
        return False
    a = binascii.hexlify(res[18:20])
    if (a != PMU_PG['pg_good']):
        print("\033[1;31m%s\033[0m" % error_message['pg_2'])
        return False
    a = binascii.hexlify(res[20:22])
    if (a != PMU_LED['led_close']):
        print("\033[1;31m%s\033[0m" % error_message['led_1'])
        return False
    a = binascii.hexlify(res[22:24])
    if (a != PMU_LED['led_close']):
        print("\033[1;31m%s\033[0m" % error_message['led_2'])
        return False
    return True

pmu_state_name = (
    'NTC1:   ',
    'NTC2:   ',
    'V12:    ',
    'VCORE1: ',
    'VCORE2: '
)

pmu_pg_state  = {
    '0001': 'Good',
    '0002': 'Bad'
}

pmu_led_state = {
    '0000': 'All Led Off',
    '0001': 'Green Led On',
    '0002': 'Red Led On',
    '0004': 'Green Led Blink',
    '0008': 'Red Led Blink'
}

def convert_to_vin(adc):
    return adc * 3.3 / 4095

def convert_to_vcore(vin):
    return vin / 20 * (20 + 43)

def convert_to_vcc(vin):
    return vin / 5.62 * (5.62 + 20)

SERIESRESISTOR=820
THERMISTORNOMINAL=10000
BCOEFFICIENT=3500
TEMPERATURENOMINAL=25
def convert_to_temp(adc):
    resistance = 4095 / adc - 1
    resistance = SERIESRESISTOR / resistance
    ret = resistance / THERMISTORNOMINAL
    ret = math.log(ret)
    ret /= BCOEFFICIENT
    ret += 1.0 / (TEMPERATURENOMINAL + 273.15)
    ret = 1.0 / ret
    ret -= 273.15

    return ret

def get_state():
    input_str = mm_package("30", module_id = None);
    ser.flushInput()
    ser.write(input_str.decode('hex'))
    res = ser.readall()
    if res == "":
        print (error_message['serial_port'])
        return False
    for index in range(len(pmu_state_name)):
        a = int(binascii.hexlify(res[(index * 2 + 6):(index * 2 + 8)]), 16)
        if (index < 2):
            print(pmu_state_name[index] + '%d' %a + '(%f' %convert_to_temp(a) + 'C)')
        elif (index == 2):
            print(pmu_state_name[index] + '%d' %a + '(%f' %convert_to_vcc(convert_to_vin(a)) + 'V)')
        else:
            print(pmu_state_name[index] + '%d' %a + '(%f' %convert_to_vcore(convert_to_vin(a)) + 'V)')

    a = binascii.hexlify(res[16:18])
    pmu_pg_state_key = pmu_pg_state.keys()
    for index in range(len(pmu_pg_state_key)):
        if a == pmu_pg_state_key[index]:
            print("PG1:    " + pmu_pg_state.get(pmu_pg_state_key[index]))
    a = binascii.hexlify(res[18:20])
    pmu_pg_state_key = pmu_pg_state.keys()
    for index in range(len(pmu_pg_state_key)):
        if a == pmu_pg_state_key[index]:
            print("PG2:    " + pmu_pg_state.get(pmu_pg_state_key[index]))
    a = binascii.hexlify(res[20:22])
    pmu_led_state_key = pmu_led_state.keys()
    for index in range(len(pmu_led_state_key)):
        if a == pmu_led_state_key[index]:
            print("LED1:   " + pmu_led_state.get(pmu_led_state_key[index]))
    a = binascii.hexlify(res[22:24])
    pmu_led_state_key = pmu_led_state.keys()
    for index in range(len(pmu_led_state_key)):
        if a == pmu_led_state_key[index]:
            print("LED2:   " + pmu_led_state.get(pmu_led_state_key[index]))
    return True

def test_polling(pmu_type):
    while (True):
        h = raw_input("Please input(1-4), h for help:")
        if (h == 'h') or (h == 'H'):
            show_help()
        elif (h == 'q') or (h == 'Q'):
            sys.exit(0)
        elif h == '1':
            detect_version(pmu_type)
        elif h == '2':
            vol = raw_input("Please input the voltage:")
            set_vol_value(vol)
        elif h == '3':
            led = raw_input("Please input the led state:")
            set_led_state(led)
        elif h == '4':
            if (get_state() == False):
                sys.exit(0)
        else:
            show_help()

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

def show_ok(pmu_type):
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")
    print("\n")
    print("\033[1;32m%s烧写完成\033[0m" % pmu_type)
    print("\n")
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")
    print("\033[1;32m--------------------------------------------------------------------------------------\033[0m")

def burn_pmu(pmu_type):
    # PMU821, PMU841, PMU851 firmware is the same
    ret = subprocess.call("make -C /home/factory/Avalon-extras/scripts/factory reflash_ulink2 MCU_PLATFORM=pmu821", shell=True)
    if (ret != 0):
        show_error()
        return 2
    else:
        show_ok(pmu_type)
        time.sleep(1)

        set_led_state("000101010101") # Light Green leds
        print("\033[1;33m请检测是否亮绿灯, 绿灯为正常, 否则不正常\033[0m")
        while (True):
            key = raw_input("\033[1;33m如点灯正常请输入空格继续%s测试，否则请输入0键并回车退出测试: \033[0m" % pmu_type)
            if (key == '0'):
                return 1
            elif (key.isspace()):
                return 0

def test_pmu(pmu_type):
    set_led_state("000000010000")
    set_vol_value("008088018088")
    if detect_version(pmu_type) == False:
        sys.exit(0)
    # Wait 3 seconds at least for power good
    time.sleep(3)
    if get_result() == False:
        show_error()
        return 2
    else:
        set_vol_value("000000010000") # Close output voltage
        print("\033[1;32m%s\033[0m" % (pmu_type + " test pass"))

        set_led_state("000202010202") # Light Red leds
        print("\033[1;33m请检测是否亮红灯, 红灯为正常, 否则不正常\033[0m")
        while (True):
            key = raw_input("\033[1;33m如点灯正常请输入空格继续%s数据保存，否则请输入0键并回车退出数据保存: \033[0m" % pmu_type)
            if (key == '0'):
                return 1
            elif (key.isspace()):
                return 0

if __name__ == '__main__':
    pmu_type = sys.argv[2]

    while (True):
        if parser.is_rig == '0':
            # Step 1: Burn PMU
            burn = burn_pmu(pmu_type) # Burn status: 0, normal; 1, leds error; 2, burn failed
            if (burn == 0):
                # Step 2: Test PMU
                test = test_pmu(pmu_type) # Test status: 0, normal; 1, leds error; 2, test failed
                if (test == 0):
                    # Step 3: Save PMU board messages
                    save_chip_data.save_data(PMU_DNA, PMU_VER, pmu_type, test)
                    while (True):
                        key = raw_input("\033[1;33m请输入回车键继续%s烧写、测试和扫描: \033[0m" % pmu_type)
                        if (len(key) == 0):
                            break
                elif (test == 1):
                    while (True):
                        key = raw_input("\033[1;33m点红灯失败，请输入回车键继续%s烧写、测试和扫描: \033[0m" % pmu_type)
                        if (len(key) == 0):
                            break
                elif (test == 2):
                    while (True):
                        key = raw_input("\033[1;33m测试失败，请输入回车键继续%s烧写、测试和扫描: \033[0m" % pmu_type)
                        if (len(key) == 0):
                            break
            elif (burn == 1):
                while (True):
                    key = raw_input("\033[1;33m点绿灯失败，请输入回车键继续%s烧写、测试和扫描: \033[0m" % pmu_type)
                    if (len(key) == 0):
                        break
            elif (burn == 2):
                while (True):
                    key = raw_input("\033[1;33m烧写失败，请输入回车键继续%s烧写、测试和扫描: \033[0m" % pmu_type)
                    if (len(key) == 0):
                        break
        elif parser.is_rig == '1':
            test_polling()
        else:
            print("Input option wrong, please try again")
            sys.exit(0)
