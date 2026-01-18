# # test_buzzer_send.py
# import time, serial
# port = "COM7"          # match your config
# baud = 9600
# with serial.Serial(port, baud, timeout=1) as ser:
#     for payload in ("B:200,200,200\n", "B:500\n", "B:80,80,300,80\n"):
#         print("Sending", payload.strip())
#         ser.write(payload.encode())
#         time.sleep(1.5)
import time, serial
port = "COM7"
baud = 9600
with serial.Serial(port, baud, timeout=1) as ser:
    time.sleep(2)                    # let Arduino reboot
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    for payload in ("B:200,200,200\n", "B:500\n", "B:80,80,300,80\n"):
        print("Sending", payload.strip())
        ser.write(payload.encode())
        time.sleep(1.5)
