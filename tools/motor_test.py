import RPi.GPIO as GPIO
import time

# Define GPIO pin assignments
motors = {
    "Mouth": (22, 23),
    "Head": (14, 4),
    "Torso": (17, 18)
}

def setup_pins():
    GPIO.setmode(GPIO.BCM)
    for in1, in2 in motors.values():
        GPIO.setup(in1, GPIO.OUT)
        GPIO.setup(in2, GPIO.OUT)

def motor_forward(in1, in2):
    GPIO.output(in1, GPIO.HIGH)
    GPIO.output(in2, GPIO.LOW)

def motor_reverse(in1, in2):
    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.HIGH)

def motor_stop(in1, in2):
    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.LOW)

def test_motor(name, in1, in2):
    print(f"\nTesting {name} Motor - FORWARD")
    motor_forward(in1, in2)
    time.sleep(2)

    print(f"Stopping {name} Motor")
    motor_stop(in1, in2)
    time.sleep(1)

    print(f"Testing {name} Motor - REVERSE")
    motor_reverse(in1, in2)
    time.sleep(2)

    print(f"Stopping {name} Motor")
    motor_stop(in1, in2)
    time.sleep(1)

def main():
    setup_pins()
    try:
        for name, (in1, in2) in motors.items():
            test_motor(name, in1, in2)
    finally:
        print("\nCleaning up GPIO...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()
