import pyttsx3
import random
import time

# Initialize the text-to-speech engine
engine = pyttsx3.init()

# Function to announce a number
def announce_number(number):
    print(number)
    engine.say(str(number))
    engine.runAndWait()

# Function to announce reset
def announce_reset():
    print("reset")
    engine.say("reset")
    engine.runAndWait()

def main():
    # Generate a list of numbers from 1 to 27
    numbers = list(range(1, 28))
    
    while True:
        # Shuffle the numbers to get a random order
        random.shuffle(numbers)
        
        # Announce each number in the shuffled list
        for number in numbers:
            announce_number(number)
            time.sleep(5)  # Wait 5 seconds between number announcements
            announce_reset()
            time.sleep(5)  # Wait 5 seconds after reset before next number

if __name__ == "__main__":
    main()
