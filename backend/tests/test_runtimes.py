#!/usr/bin/env python
"""测试所有 runtime 的完整导入"""
import sys
import os
import traceback

sys.path.insert(0, '.')

os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'mock:9092'
os.environ['REDIS_URL'] = 'redis://mock:6379/0'
os.environ['EXECUTION_MOCK'] = 'true'

print('Testing all runtime imports...')
print('=' * 60)

errors = []

runtimes = [
    ('ingestion_runtime', 'runtime.ingestion_runtime.runtime'),
    ('signal_runtime', 'runtime.signal_runtime.runtime'),
    ('execution_runtime', 'runtime.execution_runtime.runtime'),
    ('projection_runtime', 'runtime.projection_runtime.runtime'),
    ('correlation_runtime', 'runtime.correlation_runtime.runtime'),
    ('replay_runtime', 'runtime.replay_runtime.runtime'),
    ('narrative_runtime', 'runtime.narrative_runtime.runtime'),
    ('monitoring_runtime', 'runtime.monitoring_runtime.runtime'),
    ('scheduler_runtime', 'runtime.scheduler_runtime.runtime'),
]

for name, module_path in runtimes:
    try:
        mod = __import__(module_path, fromlist=['main'])
        main_func = getattr(mod, 'main', None)
        if main_func:
            print(f'✓ {name}: import OK, main() found')
        else:
            print(f'✓ {name}: import OK (no main())')
    except Exception as e:
        print(f'✗ {name}: {type(e).__name__}: {e}')
        errors.append((name, e))
        traceback.print_exc()

print()
print('=' * 60)
if errors:
    print(f'Found {len(errors)} errors:')
    for mod, err in errors:
        print(f'  - {mod}: {err}')
else:
    print('All runtime imports passed!')
