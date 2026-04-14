from lock_logic import GnomeLock
import os

if __name__ == "__main__":
    lock = GnomeLock()
    print("Executing Emergency Unlock...")
    lock.unlock()
    print("System Restored.")
