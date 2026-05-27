"""
Test script for the new feature system
"""

import sys
sys.path.insert(0, 'e:\\00_crypto\\00_code')

print('Testing feature registry...')
from backend.domain.feature import (
    FEATURE_REGISTRY,
    normalize_feature_name,
    get_feature_def,
    is_feature_registered,
    list_all_feature_names,
    FeatureCategory
)

print(f'Total registered features: {len(FEATURE_REGISTRY)}')
print(f'Sample feature names: {list(FEATURE_REGISTRY.keys())[:10]}')

# Test normalize_feature_name
print(f'normalize_feature_name("rsi"): {normalize_feature_name("rsi")}')
print(f'normalize_feature_name("open_interest"): {normalize_feature_name("open_interest")}')

# Test get_feature_def
feat = get_feature_def('rsi_14')
print(f'get_feature_def("rsi_14"): {feat}')
print(f'  name: {feat.name}')
print(f'  category: {feat.category}')
print(f'  value_type: {feat.value_type}')

# Test is_feature_registered
print(f'is_feature_registered("rsi_14"): {is_feature_registered("rsi_14")}')
print(f'is_feature_registered("non_existent"): {is_feature_registered("non_existent")}')

print('\nTesting feature map validation...')
try:
    from backend.engines.compute.context.feature_map import (
        CONTEXT_FEATURE_MAP,
        get_required_features,
        validate_context_path
    )
    print('✓ CONTEXT_FEATURE_MAP loaded successfully!')
    print(f'  Number of context paths: {len(CONTEXT_FEATURE_MAP)}')
    print(f'  Sample context path: {list(CONTEXT_FEATURE_MAP.keys())[0]}')
    
    # Test get_required_features
    req_feats = get_required_features(['derivatives.oi'])
    print(f'  get_required_features(["derivatives.oi"]): {req_feats}')
except Exception as e:
    print(f'✗ Error loading feature map: {e}')

print('\nAll tests completed! ✓')
