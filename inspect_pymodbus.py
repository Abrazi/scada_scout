
import inspect
try:
    from pymodbus.datastore import ModbusServerContext
    print("ModbusServerContext found")
    print(inspect.signature(ModbusServerContext.__init__))
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
