import sys
sys.path.insert(0, '.')

print("Testing imports...")

try:
    from services.data_service.main import app
    print("main.py: OK")
except Exception as e:
    print(f"main.py ERROR: {e}")

try:
    from services.data_service.tdp_adapter import TDPAdapter
    print("tdp_adapter.py: OK")
except Exception as e:
    print(f"tdp_adapter.py ERROR: {e}")

try:
    from services.data_service.cache import DataServiceCache
    print("cache.py: OK")
except Exception as e:
    print(f"cache.py ERROR: {e}")

try:
    from services.data_service.storage import DataStorage
    print("storage.py: OK")
except Exception as e:
    print(f"storage.py ERROR: {e}")

print("Done")
