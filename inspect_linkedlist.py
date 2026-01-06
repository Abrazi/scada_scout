
from pyiec61850 import iec61850

print("Checking LinkedList functions:")
functions = [x for x in dir(iec61850) if "LinkedList" in x]
for f in functions:
    print(f)
