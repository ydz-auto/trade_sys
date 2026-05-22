import os
os.environ['TORCH_DEVICE'] = 'cuda'

import sys
sys.path.insert(0, r'E:\00_crypto\00_code\backend')

import torch
import time

print('=' * 50)
print('GPU Crash Diagnostic Test')
print('=' * 50)

print('\n--- Step 1: Basic PyTorch ---')
try:
    print(f'PyTorch: {torch.__version__}')
    print(f'CUDA available: {torch.cuda.is_available()}')
    print(f'GPU: {torch.cuda.get_device_name(0)}')
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)

print('\n--- Step 2: Import shared.acceleration ---')
try:
    from shared.acceleration import is_gpu_available, get_accelerator_info, device
    info = get_accelerator_info()
    print(f'Device type: {info["device_type"]}')
    print(f'Is GPU: {info["is_gpu"]}')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 3: Import TorchFeatureCalculator ---')
try:
    from domain.feature.torch_calculator import TorchFeatureCalculator
    calc = TorchFeatureCalculator()
    print('TorchFeatureCalculator created OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 4: Import OptimizationBacktestEngine ---')
try:
    from application.optimization_service.engine import OptimizationBacktestEngine, BacktestConfig
    config = BacktestConfig()
    print(f'BacktestConfig created: {config}')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 5: Create OptimizationBacktestEngine ---')
try:
    engine = OptimizationBacktestEngine(config)
    print(f'OptimizationBacktestEngine created: {engine}')
    print(f'GPU available: {engine._gpu_available}')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 6: Import RuntimeBus ---')
try:
    from runtime.bus.runtime_bus import get_runtime_bus
    bus = get_runtime_bus()
    print('RuntimeBus created OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 7: Import get_replay_runtime ---')
try:
    from runtime.replay_runtime.runtime import get_replay_runtime
    print('get_replay_runtime imported OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 8: Call get_replay_runtime ---')
try:
    runtime = get_replay_runtime()
    print('get_replay_runtime() OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 9: Import OptimizationService ---')
try:
    from application.optimization_service.service import OptimizationService
    print('OptimizationService imported OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 10: Create OptimizationService ---')
try:
    service = OptimizationService()
    print('OptimizationService created OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 11: Import OptimizationConfig ---')
try:
    from application.optimization_service.models import OptimizationConfig
    print('OptimizationConfig imported OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 12: Create OptimizationConfig ---')
try:
    config = OptimizationConfig(
        initial_capital=10000,
        commission=0.0005,
        slippage=0.0002,
        position_size=0.3,
        optimization_start="2023-04-01",
        optimization_end="2023-04-30",
        method="grid_search",
        metric="sharpe_ratio",
        param_grid={
            "fast": [5, 10],
            "slow": [30],
        },
        stop_loss=0.02,
        take_profit=0.04,
    )
    print(f'OptimizationConfig created OK')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n--- Step 13: Create task ---')
try:
    import asyncio
    async def test():
        task = await service.create_task(strategy_id="sma_cross", symbol="BTCUSDT", config=config)
        print(f'Task created: {task.task_id}')
    asyncio.run(test())
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n' + '=' * 50)
print('All import tests passed!')
print('=' * 50)
