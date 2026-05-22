import torch
import sys

print('=' * 50)
print('GPU Diagnostic Test')
print('=' * 50)

print(f'\nPyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')

if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'Device capability: {torch.cuda.get_device_capability(0)}')
    
    props = torch.cuda.get_device_properties(0)
    print(f'Total memory: {props.total_memory / 1024**3:.1f} GB')
    print(f'Multi-processor count: {props.multi_processor_count}')

print('\n--- Test 1: Simple GPU tensor ---')
try:
    x = torch.randn(1000, 1000, device='cuda')
    print(f'Tensor created on GPU: {x.shape}')
    print(f'Device: {x.device}')
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)

print('\n--- Test 2: GPU matrix multiplication ---')
try:
    y = torch.randn(1000, 1000, device='cuda')
    z = torch.matmul(x, y)
    print(f'Matrix multiply OK: {z.shape}')
    torch.cuda.synchronize()
    print('Synchronize OK')
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)

print('\n--- Test 3: Multiple GPU operations ---')
try:
    for i in range(5):
        a = torch.randn(500, 500, device='cuda')
        b = torch.randn(500, 500, device='cuda')
        c = torch.matmul(a, b)
    torch.cuda.synchronize()
    print('Multiple ops OK')
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)

print('\n--- Test 4: Cleanup ---')
try:
    del x, y, z
    torch.cuda.empty_cache()
    print('Cleanup OK')
except Exception as e:
    print(f'FAILED: {e}')

print('\n' + '=' * 50)
print('All GPU tests passed!')
print('=' * 50)
